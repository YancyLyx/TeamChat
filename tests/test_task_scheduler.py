"""
Unit tests for TaskScheduler + ResultRelay (ADR-003 中枢模式, Phase 4.0 PR1).

Uses mocks — no real CLI spawns. Verifies the collaboration loop:
  - TaskScheduler dispatches unblocked tasks, marks running (NOT done), hands to ResultRelay
  - ResultRelay queues when cici咪 busy, spawns review when idle, builds review prompt
  - Engine never marks done/failed (cici咪's job)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.config import AGENT_CICI, AGENT_COCO, Config
from engine.result_relay import ResultRelay
from engine.runner import AgentResult
from engine.task_scheduler import TaskScheduler
from engine.task_table import TaskTable


@pytest.fixture
def config(tmp_path):
    return Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )


@pytest.fixture
def task_table(config):
    from engine.session_store import SessionStore
    ss = SessionStore(config)
    ss.init()  # creates teamchat_sessions table + default session (FK target)
    tt = TaskTable(config)
    tt.init()
    yield tt
    tt.close()
    ss.close()


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner._run = AsyncMock()
    return runner


def _make_result(agent_name="coco咪", output="done", exit_code=0):
    return AgentResult(
        agent_name=agent_name, task_prompt="x", output=output,
        exit_code=exit_code, duration_ms=100,
        started_at="t1", finished_at="t2", cli_session_id="sid",
    )


# ---- TaskScheduler ----


class TestTaskScheduler:
    async def test_dispatch_marks_running_not_done(self, task_table, mock_runner):
        """铁律: Engine dispatches but does NOT mark done — that's cici咪's job."""
        task = task_table.create(agent="coco咪", title="加按钮", description="实现按钮")
        mock_runner._run.return_value = _make_result()
        result_relay = AsyncMock()
        router = MagicMock()
        router.is_busy.return_value = False
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        updated = task_table.get(task.id)
        assert updated.status == "running"  # NOT done — cici咪 reviews first
        result_relay.relay.assert_awaited_once()

    async def test_dispatch_calls_spawn_and_relay(self, task_table, mock_runner):
        task = task_table.create(agent="coco咪", title="t", description="d")
        mock_runner._run.return_value = _make_result()
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        mock_runner._run.assert_awaited_once()
        result_relay.relay.assert_awaited_once()
        store.log.assert_called_once()  # agent_calls logged

    async def test_dispatch_unknown_agent_marks_failed(self, task_table, mock_runner):
        task = task_table.create(agent="unknown咪", title="t", description="d")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        updated = task_table.get(task.id)
        assert updated.status == "failed"
        mock_runner._run.assert_not_called()
        result_relay.relay.assert_not_called()

    async def test_dispatch_spawn_error_still_relays(self, task_table, mock_runner):
        """If spawn throws, Engine builds an error result and still hands to cici咪."""
        task = task_table.create(agent="coco咪", title="t", description="d")
        mock_runner._run.side_effect = RuntimeError("boom")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        result_relay.relay.assert_awaited_once()
        relayed_result = result_relay.relay.await_args.args[1]
        assert relayed_result.success is False

    async def test_retry_transient_failure(self, task_table, mock_runner, monkeypatch):
        """First failure is retried; success on second attempt reaches cici咪 with retries=1."""
        import engine.task_scheduler as ts
        monkeypatch.setattr(ts, "RETRY_DELAYS", (0, 0, 0))
        task = task_table.create(agent="coco咪", title="t", description="d")
        mock_runner._run.side_effect = [
            _make_result(exit_code=1, output="fail once"),
            _make_result(exit_code=0, output="ok"),
        ]
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        assert mock_runner._run.await_count == 2  # 1 attempt + 1 retry
        relayed = result_relay.relay.await_args
        assert relayed.args[1].success is True
        assert relayed.kwargs.get("retries") == 1

    async def test_retry_exhausted_still_relays_failure(self, task_table, mock_runner, monkeypatch):
        """After MAX_RETRIES failures, the final failed result still reaches cici咪."""
        import engine.task_scheduler as ts
        monkeypatch.setattr(ts, "RETRY_DELAYS", (0, 0, 0))
        task = task_table.create(agent="coco咪", title="t", description="d")
        mock_runner._run.return_value = _make_result(exit_code=1, output="always fails")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        assert mock_runner._run.await_count == 4  # 1 + 3 retries
        relayed = result_relay.relay.await_args
        assert relayed.args[1].success is False
        assert relayed.kwargs.get("retries") == 3


# ---- ResultRelay ----


class TestResultRelay:
    async def test_relay_queues_when_cici_busy(self, task_table, mock_runner):
        router = MagicMock()
        router.is_busy.return_value = True  # cici咪 busy
        session_store = MagicMock()

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="coco咪", title="t", description="d")

        await relay.relay(task, _make_result())

        assert len(relay._pending) == 1
        mock_runner._run.assert_not_called()  # no review spawn while busy

    async def test_relay_spawns_review_when_cici_idle(self, task_table, mock_runner):
        router = MagicMock()
        router.is_busy.return_value = False
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.return_value = _make_result(agent_name="cici咪", output="审核通过")

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="coco咪", title="t", description="d")

        await relay.relay(task, _make_result())

        assert len(relay._pending) == 0
        mock_runner._run.assert_awaited_once()  # cici咪 review spawned

    async def test_relay_cici_own_result_not_reviewed(self, task_table, mock_runner):
        """cici咪's own task results are not pushed back to cici咪."""
        router = MagicMock()
        router.is_busy.return_value = False
        session_store = MagicMock()

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="cici咪", title="cici task", description="d")

        await relay.relay(task, _make_result(agent_name="cici咪"))

        assert len(relay._pending) == 0
        mock_runner._run.assert_not_called()

    async def test_relay_batches_multiple_queued_results(self, task_table, mock_runner):
        """When cici咪 goes idle, all queued results are reviewed in one spawn."""
        router = MagicMock()
        router.is_busy.return_value = True  # busy first
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.return_value = _make_result(agent_name="cici咪", output="ok")

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        t1 = task_table.create(agent="coco咪", title="t1", description="d")
        t2 = task_table.create(agent="soso咪", title="t2", description="d")

        await relay.relay(t1, _make_result(agent_name="coco咪"))
        await relay.relay(t2, _make_result(agent_name="soso咪"))
        assert len(relay._pending) == 2

        # Now cici咪 goes idle
        router.is_busy.return_value = False
        await relay.drain_if_idle()

        assert len(relay._pending) == 0
        mock_runner._run.assert_awaited_once()  # one batched review spawn

    def test_build_review_prompt_includes_mcp_instructions(self, task_table):
        relay = ResultRelay(MagicMock(), MagicMock(), MagicMock(), task_table)
        task = task_table.create(agent="coco咪", title="加刷新按钮", description="d")
        result = _make_result(output="按钮已添加")

        prompt = relay._build_review_prompt([(task, result, 0)])

        assert "mcp__teamchat__update_task" in prompt
        assert "mcp__teamchat__create_task" in prompt
        assert "加刷新按钮" in prompt
        assert "按钮已添加" in prompt

    async def test_review_spawn_failure_requeues_batch(self, task_table, mock_runner):
        """If the review spawn fails, results are re-queued, not lost (soso咪 review 备注1)."""
        router = MagicMock()
        router.is_busy.return_value = False
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.side_effect = RuntimeError("review spawn boom")

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="coco咪", title="t", description="d")

        await relay.relay(task, _make_result())

        # batch re-queued for a later retry — nothing lost
        assert len(relay._pending) == 1
        assert relay._pending[0][0].id == task.id

    def test_build_review_prompt_marks_failed_result(self, task_table):
        relay = ResultRelay(MagicMock(), MagicMock(), MagicMock(), task_table)
        task = task_table.create(agent="coco咪", title="t", description="d")
        result = _make_result(output="error", exit_code=1)

        prompt = relay._build_review_prompt([(task, result, 3)])

        assert "失败" in prompt
        assert "重试 3 次" in prompt  # retry info surfaced to cici咪

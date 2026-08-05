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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
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
        task = task_table.create(agent="unknown咪", title="t", description="implement feature and verify result")
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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
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

    async def test_retry_records_count_and_error(self, task_table, mock_runner, monkeypatch):
        """Phase 4.5: 重试耗尽后任务记录 retry_count + last_error（cici咪 决策依据）。"""
        import engine.task_scheduler as ts
        monkeypatch.setattr(ts, "RETRY_DELAYS", (0, 0, 0))
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        mock_runner._run.return_value = _make_result(exit_code=1, output="always broken")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        updated = task_table.get(task.id)
        assert updated.retry_count == 3  # MAX_RETRIES
        assert "always broken" in updated.last_error

    async def test_relay_receives_refreshed_task(self, task_table, mock_runner, monkeypatch):
        """soso咪 Bug 1: relay 前刷新 task，last_error 在生产路径可见。"""
        import engine.task_scheduler as ts
        monkeypatch.setattr(ts, "RETRY_DELAYS", (0, 0, 0))
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        mock_runner._run.return_value = _make_result(exit_code=1, output="boom error")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        relayed_task = result_relay.relay.await_args.args[0]
        assert relayed_task.last_error != ""  # 刷新后的 task 带 last_error

    async def test_reassigned_task_dispatches_to_new_agent(self, task_table, mock_runner):
        """soso咪 备注4: 转派后（agent 改）TaskScheduler 派发给新 agent。"""
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        task_table.update(task.id, agent="soso咪", status="pending")  # cici咪 转派

        unblocked = task_table.unblocked_tasks()
        assert unblocked and unblocked[0].agent == "soso咪"

        mock_runner._run.return_value = _make_result(agent_name="soso咪")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(unblocked[0])

        agent_arg = mock_runner._run.await_args.args[0]
        assert agent_arg.name == "soso咪"  # 派发给新 agent

    async def test_retry_attempts_are_audited(self, task_table, mock_runner, monkeypatch):
        """Every retried attempt is written to agent_calls (soso咪 备注, PR #95)."""
        import engine.task_scheduler as ts
        monkeypatch.setattr(ts, "RETRY_DELAYS", (0, 0, 0))
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        mock_runner._run.side_effect = [
            _make_result(exit_code=1, output="fail 1"),
            _make_result(exit_code=1, output="fail 2"),
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

        # 2 retried attempts logged as scheduled_task_retry + final as scheduled_task
        retry_logs = [c for c in store.log.call_args_list
                      if c.kwargs.get("task_type") == "scheduled_task_retry"]
        final_logs = [c for c in store.log.call_args_list
                      if c.kwargs.get("task_type") == "scheduled_task"]
        assert len(retry_logs) == 2
        assert len(final_logs) == 1


    async def test_watchdog_broadcasts_task_table_changes(self, task_table, mock_runner):
        """Diff watchdog: broadcast task_table_updated for changed rows —
        covers cross-process MCP create/update_task; first pass = baseline."""
        ws_manager = AsyncMock()
        scheduler = TaskScheduler(
            mock_runner, MagicMock(), task_table, MagicMock(), MagicMock(),
            AsyncMock(), ws_manager=ws_manager,
        )
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")

        # first pass: baseline only, no broadcast
        await scheduler._broadcast_task_changes()
        ws_manager.broadcast.assert_not_called()

        # status change (as MCP update_task would write, cross-process)
        task_table.update(task.id, status="running")
        await scheduler._broadcast_task_changes()
        calls = [c.args[0] for c in ws_manager.broadcast.call_args_list]
        assert any(
            c.get("type") == "task_table_updated" and c.get("data", {}).get("id") == task.id
            for c in calls
        )

        # unchanged second pass: no new broadcast
        ws_manager.broadcast.reset_mock()
        await scheduler._broadcast_task_changes()
        ws_manager.broadcast.assert_not_called()


    async def test_cici_task_no_auto_done(self, task_table, mock_runner):
        """#97 — cici咪 任务不再自动收尾：走 relay 排队进审核（不直接 done）。"""
        task = task_table.create(agent="cici咪", title="引擎修复", description="implement feature and verify result")
        mock_runner._run.return_value = _make_result(agent_name="cici咪")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        updated = task_table.get(task.id)
        assert updated.status == "running"  # 不自动 done——等 cici咪 审核（#97）
        result_relay.relay.assert_awaited_once()  # 结果进审核队列（自我编排模式）

    async def test_cici_task_failure_no_auto_failed(self, task_table, mock_runner):
        """#97 — cici咪 任务失败也不自动标 failed：走 relay，由 cici咪 审核决策。"""
        task = task_table.create(agent="cici咪", title="t", description="implement feature and verify result")
        mock_runner._run.return_value = _make_result(agent_name="cici咪", exit_code=1)
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        assert task_table.get(task.id).status == "running"  # 引擎不标 failed（铁律 + #97）
        result_relay.relay.assert_awaited_once()


    async def test_dispatch_logs_result_tool_calls(self, task_table, mock_runner):
        """#28 — result.tool_calls must flow into store.log (agent_calls)."""
        from unittest.mock import AsyncMock, MagicMock

        from engine.runner import AgentResult
        from engine.task_scheduler import TaskScheduler

        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        result = AgentResult(
            agent_name="coco咪", task_prompt="x", output="done", exit_code=0,
            duration_ms=100, started_at="s", finished_at="f",
            tool_calls=[{"name": "mcp__teamchat__create_task", "input": {"agent": "soso咪"}}],
        )
        mock_runner._run.return_value = result
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

        kwargs = store.log.call_args_list[-1].kwargs
        assert kwargs["tool_calls"] == result.tool_calls


    async def test_dispatch_logs_tool_calls(self, task_table, mock_runner):
        """#28 — AgentResult.tool_calls flow into store.log → agent_calls."""
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        result = _make_result()
        result.tool_calls = [{"name": "create_task", "input": {"title": "x"}}]
        mock_runner._run.return_value = result
        result_relay = AsyncMock()
        store = MagicMock()
        scheduler = TaskScheduler(
            mock_runner, MagicMock(), task_table, MagicMock(), store, result_relay,
        )
        await scheduler._dispatch(task)
        store.log.assert_called()
        logged = store.log.call_args.kwargs
        assert logged.get("tool_calls") == result.tool_calls


class TestDeferredDispatch:
    """cici咪 busy 期间创建的任务延迟派发（用户报告的顺序问题）。"""

    def _make_scheduler(self, task_table, router):
        return TaskScheduler(
            MagicMock(), router, task_table, MagicMock(), MagicMock(), AsyncMock(),
        )

    def test_defer_when_created_during_cici_busy(self, task_table):
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        router = MagicMock()

        def is_busy(agent):
            return agent.name == "cici咪"  # cici咪 busy（分析中）
        router.is_busy.side_effect = is_busy
        router.busy_since.return_value = "2026-01-01T00:00:00+00:00"  # 早于任务创建

        scheduler = self._make_scheduler(task_table, router)
        assert scheduler._should_defer(task) is True

    def test_no_defer_when_cici_free(self, task_table):
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        router = MagicMock()
        router.is_busy.return_value = False

        scheduler = self._make_scheduler(task_table, router)
        assert scheduler._should_defer(task) is False

    def test_no_defer_for_cici_own_task(self, task_table):
        task = task_table.create(agent="cici咪", title="t", description="implement feature and verify result")
        router = MagicMock()
        router.is_busy.return_value = True  # cici咪 busy

        scheduler = self._make_scheduler(task_table, router)
        assert scheduler._should_defer(task) is False  # cici咪 自己的任务不受此限制


# ---- ResultRelay ----


class TestResultRelay:
    async def test_relay_queues_when_cici_busy(self, task_table, mock_runner):
        router = MagicMock()
        router.is_busy.return_value = True  # cici咪 busy
        session_store = MagicMock()

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")

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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")

        await relay.relay(task, _make_result())

        assert len(relay._pending) == 0
        mock_runner._run.assert_awaited_once()  # cici咪 review spawned

    async def test_relay_cici_own_result_queued(self, task_table, mock_runner):
        """#97 — cici咪's own task results now queue for review (self-orchestration mode)."""
        router = MagicMock()
        router.is_busy.return_value = False
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.return_value = _make_result(agent_name="cici咪", output="ok")

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        task = task_table.create(agent="cici咪", title="cici task", description="implement feature and verify result")

        await relay.relay(task, _make_result(agent_name="cici咪"))

        # cici咪 空闲 → drain 立即审核（结果已处理，不再"只 drain 不审核"）
        mock_runner._run.assert_awaited()
        prompt = mock_runner._run.await_args.args[1].prompt
        assert "类型=development" in prompt
        assert "创建 soso咪 的审查节点" in prompt  # 自我编排模式引导

    async def test_relay_batches_multiple_queued_results(self, task_table, mock_runner):
        """When cici咪 goes idle, all queued results are reviewed in one spawn."""
        router = MagicMock()
        router.is_busy.return_value = True  # busy first
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.return_value = _make_result(agent_name="cici咪", output="ok")

        relay = ResultRelay(mock_runner, router, session_store, task_table)
        t1 = task_table.create(agent="coco咪", title="t1", description="implement feature and verify result")
        t2 = task_table.create(agent="soso咪", title="t2", description="implement feature and verify result")

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
        task = task_table.create(agent="coco咪", title="加刷新按钮", description="implement feature and verify result")
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
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")

        await relay.relay(task, _make_result())

        # batch re-queued for a later retry — nothing lost
        assert len(relay._pending) == 1
        assert relay._pending[0][0].id == task.id

    def test_build_review_prompt_includes_healing_options(self, task_table):
        """Phase 4.5: 失败任务的审核 prompt 含三选项（重试/转派/放弃）+ last_error。"""
        relay = ResultRelay(MagicMock(), MagicMock(), MagicMock(), task_table)
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        task_table.update(task.id, retry_count=3, last_error="network timeout")
        task = task_table.get(task.id)  # 重新读取（含 last_error）
        result = _make_result(output="error", exit_code=1)

        prompt = relay._build_review_prompt([(task, result, 3)])

        assert "network timeout" in prompt  # last_error 显示
        assert "重试" in prompt and "转派" in prompt and "放弃" in prompt
        assert "update_task(task_id=<id>, agent=<另一位咪>" in prompt

    def test_build_review_prompt_marks_failed_result(self, task_table):
        relay = ResultRelay(MagicMock(), MagicMock(), MagicMock(), task_table)
        task = task_table.create(agent="coco咪", title="t", description="implement feature and verify result")
        result = _make_result(output="error", exit_code=1)

        prompt = relay._build_review_prompt([(task, result, 3)])

        assert "失败" in prompt
        assert "重试 3 次" in prompt  # retry info surfaced to cici咪


class TestPollutionGuard:
    """防测试污染：description ≤2 字符的任务不派发（soso咪 备注3 补单测）。"""

    async def test_short_description_not_dispatched(self, task_table, mock_runner):
        task = task_table.create(agent="coco咪", title="t", description="d")
        result_relay = AsyncMock()
        router = MagicMock()
        store = MagicMock()
        session_store = MagicMock()

        scheduler = TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )
        await scheduler._dispatch(task)

        assert task_table.get(task.id).status == "abandoned"
        mock_runner._run.assert_not_called()  # 不 spawn
        result_relay.relay.assert_not_called()  # 不 relay

    async def test_chinese_short_prompt_not_blocked(self, task_table, mock_runner):
        """中文短 prompt（'实现按钮'=4 字符）正常派发（soso咪 备注2）。"""
        task = task_table.create(agent="coco咪", title="t", description="实现按钮")
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

        assert task_table.get(task.id).status == "running"  # 正常派发
        mock_runner._run.assert_awaited_once()


class TestParallelDispatch:
    """ADR-006 #96 — 不同 agent 的独立任务并行派发。"""

    def _scheduler(self, task_table, mock_runner):
        from engine.router import Router
        result_relay = AsyncMock()
        router = Router()  # 真实 Router：mark_busy/mark_free 真实生效
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        return TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )

    async def test_different_agents_dispatch_in_parallel(self, task_table, mock_runner):
        """coco咪 + soso咪 各 1 个 unblocked 任务 → 同一轮并发启动。"""
        import asyncio

        started = []  # (agent_name, loop_time)
        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            started.append((agent.name, asyncio.get_running_loop().time()))
            await asyncio.sleep(0.05)  # 模拟执行时间
            return _make_result(agent_name=agent.name)

        mock_runner._run = fake_run
        task_table.create(agent="coco咪", title="A", description="并行任务A")
        task_table.create(agent="soso咪", title="B", description="并行任务B")

        scheduler = self._scheduler(task_table, mock_runner)
        await scheduler._poll_once()

        assert [a for a, _ in started] == ["coco咪", "soso咪"]
        # 并发证明：两个任务都在对方完成前启动（间隔 < 0.05s 执行时间）
        gap = abs(started[0][1] - started[1][1])
        assert gap < 0.05, f"两个任务未并行启动，间隔 {gap:.4f}s"

    async def test_same_agent_dispatched_serially(self, task_table, mock_runner):
        """同 agent 的 2 个任务：第一轮只派 1 个，完成后第二轮才派下一个。"""
        import asyncio

        started = []
        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            started.append(task.prompt)
            await asyncio.sleep(0.01)
            return _make_result(agent_name=agent.name)

        mock_runner._run = fake_run
        task_table.create(agent="coco咪", title="A1", description="同agent任务1")
        task_table.create(agent="coco咪", title="A2", description="同agent任务2")

        scheduler = self._scheduler(task_table, mock_runner)
        await scheduler._poll_once()
        assert started == ["同agent任务1"], "同 agent 两个任务不应在同一轮并行派发"

        # 第一个完成后（busy 已释放），下一轮派发第二个
        await scheduler._poll_once()
        assert started == ["同agent任务1", "同agent任务2"]

    async def test_one_failure_does_not_block_others(self, task_table, mock_runner):
        """一个任务 spawn 抛异常：同伴任务正常完成，_poll_once 不抛。"""
        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            if task.prompt == "BAD":
                raise RuntimeError("CLI 崩溃")
            return _make_result(agent_name=agent.name)

        mock_runner._run = fake_run
        task_table.create(agent="coco咪", title="BAD", description="BAD")
        task_table.create(agent="soso咪", title="OK", description="正常任务")

        scheduler = self._scheduler(task_table, mock_runner)
        await scheduler._poll_once()  # 不应抛异常

        ok_task = [t for t in task_table.list_tasks() if t.title == "OK"][0]
        # 失败任务重试耗尽也走 relay（给 cici咪 决策），故 2 次
        relayed_ids = [c.args[0].id for c in scheduler.result_relay.relay.await_args_list]
        assert len(relayed_ids) == 2
        assert ok_task.id in relayed_ids
        bad = [t for t in task_table.list_tasks() if t.title == "BAD"][0]
        # 铁律：引擎不标 done/failed，失败任务保持 running 等 cici咪 审核决策
        assert bad.status == "running"
        assert bad.retry_count == 3


class TestParallelDispatchCoverage:
    """soso咪 审查建议补充：#96 并行派发缺口覆盖。"""

    def _scheduler(self, task_table, mock_runner):
        from engine.router import Router
        result_relay = AsyncMock()
        router = Router()
        store = MagicMock()
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        return TaskScheduler(
            mock_runner, router, task_table, session_store, store, result_relay,
        )

    async def test_three_agents_same_poll(self, task_table, mock_runner):
        """三个 agent 各 1 个 unblocked 任务 → 同一轮全部并行启动。"""
        import asyncio

        started = []
        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            started.append(agent.name)
            await asyncio.sleep(0.02)
            return _make_result(agent_name=agent.name)

        mock_runner._run = fake_run
        from engine.config import AGENT_CICI
        task_table.create(agent="coco咪", title="A", description="任务A")
        task_table.create(agent="soso咪", title="B", description="任务B")
        task_table.create(agent="cici咪", title="C", description="任务C")

        scheduler = self._scheduler(task_table, mock_runner)
        await scheduler._poll_once()

        assert sorted(started) == ["cici咪", "coco咪", "soso咪"]

    async def test_dispatch_post_spawn_error_isolated(self, task_table, mock_runner):
        """_dispatch 在 spawn 之后抛错（store.log 异常）→ return_exceptions 吸收，_poll_once 不炸。"""
        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            return _make_result(agent_name=agent.name)

        mock_runner._run = fake_run
        scheduler = self._scheduler(task_table, mock_runner)

        def boom(*args, **kwargs):
            raise RuntimeError("store.log 崩溃")

        scheduler.store.log.side_effect = boom  # 所有任务的 store.log 都抛错
        task_table.create(agent="coco咪", title="BAD", description="BAD")
        task_table.create(agent="soso咪", title="OK", description="正常任务")

        await scheduler._poll_once()  # 不应抛异常——两个 _dispatch 的异常都被 gather 吸收

        # store.log 抛错发生在 relay 之前 → 两个任务都没 relay（异常被隔离，不吞不炸）
        assert scheduler.result_relay.relay.await_count == 0


class TestReviewClosure:
    """#97 — 审核双模式：按 task_type 引导（development→审查节点 / review→验收 / fix→复审）。"""

    def _relay(self, task_table, mock_runner, router_busy=False):
        router = MagicMock()
        router.is_busy.return_value = router_busy
        session_store = MagicMock()
        session_store.get_agent_session_id.return_value = "sid"
        mock_runner._run.return_value = _make_result(agent_name="cici咪", output="ok")
        return ResultRelay(mock_runner, router, session_store, task_table)

    def _last_prompt(self, mock_runner) -> str:
        return mock_runner._run.await_args.args[1].prompt

    async def test_development_prompt_guides_review_node(self, task_table, mock_runner):
        """development 任务（任何 agent）审核 prompt 引导创建 soso咪 审查节点。"""
        relay = self._relay(task_table, mock_runner)
        task = task_table.create(agent="coco咪", title="前端开发", description="实现看板 UI",
                                 task_type="development")
        await relay.relay(task, _make_result(agent_name="coco咪"))
        prompt = self._last_prompt(mock_runner)
        assert "类型=development" in prompt
        assert "创建 soso咪 的审查节点" in prompt
        assert "task_type='review'" in prompt

    async def test_review_prompt_accepts_conclusion(self, task_table, mock_runner):
        """review 节点（soso咪 的审查结论）不引导再建审查节点。"""
        relay = self._relay(task_table, mock_runner)
        task = task_table.create(agent="soso咪", title="审查B", description="审查B的开发",
                                 task_type="review")
        await relay.relay(task, _make_result(agent_name="soso咪"))
        prompt = self._last_prompt(mock_runner)
        assert "类型=review" in prompt
        assert "审查节点本身是验证环节" in prompt  # review 分支：验收结论，不再触发审查
        assert "不再为它创建审查节点" in prompt

    async def test_fix_prompt_guides_verify_node(self, task_table, mock_runner):
        """fix 节点审核 prompt 引导创建 soso咪 复审节点（verify）。"""
        relay = self._relay(task_table, mock_runner)
        task = task_table.create(agent="cici咪", title="修复C2问题", description="修复两处问题",
                                 task_type="fix")
        await relay.relay(task, _make_result(agent_name="cici咪"))
        prompt = self._last_prompt(mock_runner)
        assert "类型=fix" in prompt
        assert "创建 soso咪 的复审节点" in prompt
        assert "task_type='verify'" in prompt

    async def test_cici_dev_task_self_orchestration(self, task_table, mock_runner):
        """cici咪 自己的 development 任务：排队审核 + 自我编排模式引导。"""
        relay = self._relay(task_table, mock_runner)
        task = task_table.create(agent="cici咪", title="引擎开发", description="实现 stats API",
                                 task_type="development")
        await relay.relay(task, _make_result(agent_name="cici咪"))
        prompt = self._last_prompt(mock_runner)
        assert "类型=development" in prompt
        assert "含你自己的任务" in prompt  # 自我编排模式明示
        assert "创建 soso咪 的审查节点" in prompt


class TestFeatureTreeLinking:
    """#97 — 同一分析回合的并行分支归属一棵需求树（L2 一张拓扑图）。"""

    def test_parallel_branches_link_to_one_tree(self, task_table):
        from engine.task_planner import link_parallel_branches

        before = {t.id for t in task_table.list_tasks()}
        a = task_table.create(agent="cici咪", title="A", description="引擎开发")
        b = task_table.create(agent="coco咪", title="B", description="前端开发")
        assert a.feature_id == a.id  # A 是根
        assert b.feature_id == b.id  # B 独立根（两棵树）

        linked = link_parallel_branches(task_table, before)
        assert linked == 1
        assert task_table.get(b.id).feature_id == a.feature_id  # B 挂到 A 的树

    def test_depending_tasks_not_relinked(self, task_table):
        from engine.task_planner import link_parallel_branches

        before = {t.id for t in task_table.list_tasks()}
        a = task_table.create(agent="cici咪", title="A", description="引擎开发")
        c = task_table.create(agent="soso咪", title="C", description="测试A",
                              depends_on=[a.id])
        assert c.feature_id == a.feature_id  # 依赖任务已继承
        linked = link_parallel_branches(task_table, before)
        assert linked == 0  # 只有一个根，无需重挂

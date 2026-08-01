"""Tests for no-@mention routing + task dispatch (PR #82, ADR-003; updated for PR1 TaskScheduler)."""

from __future__ import annotations

import httpx
import pytest

from engine.config import Config, load_config
from engine.session_store import SessionStore as TeamChatSessionStore
from engine.task_table import TaskTable


@pytest.fixture
def task_table(tmp_path):
    base = load_config()
    config = Config(
        repo_owner=base.repo_owner,
        repo_name=base.repo_name,
        repo_url=base.repo_url,
        project_root=tmp_path,
    )
    ss = TeamChatSessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()
    yield tt
    tt.close()
    ss.close()


class TestUnblockedTasks:
    """task_table.unblocked_tasks() is what TaskScheduler polls (PR1)."""

    def test_returns_pending_with_no_deps(self, task_table):
        first = task_table.create("coco咪", "step1", description="first")
        to_run = task_table.unblocked_tasks()
        assert [t.id for t in to_run] == [first.id]

    def test_respects_dependency_order(self, task_table):
        first = task_table.create("coco咪", "step1", description="first")
        second = task_table.create("soso咪", "step2", description="second", depends_on=[first.id])

        to_run = task_table.unblocked_tasks()
        assert [t.id for t in to_run] == [first.id]  # second blocked

        task_table.update(first.id, status="done")
        to_run2 = task_table.unblocked_tasks()
        assert [t.id for t in to_run2] == [second.id]


def _seed_task_with_description(app, *, agent: str, title: str, description: str) -> int:
    import time
    holder: dict[str, int] = {}

    def _write() -> None:
        task = app.state.task_table.create(agent, title, description=description)
        holder["id"] = task.id

    app.state.loop.call_soon_threadsafe(_write)
    deadline = time.time() + 5
    while "id" not in holder and time.time() < deadline:
        time.sleep(0.05)
    if "id" not in holder:
        raise RuntimeError("Timed out seeding task")
    return holder["id"]


@pytest.mark.skip(
    reason="PR1 架构变更: chat.py 同步派发改为 TaskScheduler 后台轮询 + cici咪 审核。"
           "端到端验证在 PR2（失败重试 + E2E 测试）重写。"
)
class TestNoMentionAutoDispatchApi:
    def test_existing_pending_not_redispatched(self, e2e_servers, e2e_app):
        _seed_task_with_description(
            e2e_app, agent="coco咪", title="stale pending", description="SHOULD_NOT_RUN_STALE",
        )

        api_url = e2e_servers["api_url"]
        resp = httpx.post(
            f"{api_url}/api/chat",
            json={"content": "what is the project status?", "teamchat_session_id": 1},
            timeout=60.0,
        )
        resp.raise_for_status()
        assert resp.json()["status"] == "analyzed"

        sessions = httpx.get(f"{api_url}/api/sessions?limit=50", timeout=10.0).json()
        assert not any(s.get("prompt") == "SHOULD_NOT_RUN_STALE" for s in sessions)

    def test_new_task_gets_dispatched(self, e2e_servers, e2e_app):
        import time
        import api.routes.chat as chat_mod

        original_build = chat_mod.build_cici_analysis_prompt

        def patched_build(message: str) -> str:
            # chat_endpoint runs on the API event loop — safe to write synchronously here
            e2e_app.state.task_table.create(
                "coco咪", "auto dispatch", description="AUTO_DISPATCH_MARKER",
            )
            return original_build(message)

        chat_mod.build_cici_analysis_prompt = patched_build
        try:
            api_url = e2e_servers["api_url"]
            resp = httpx.post(
                f"{api_url}/api/chat",
                json={"content": "add refresh button please", "teamchat_session_id": 1},
                timeout=120.0,
            )
            resp.raise_for_status()
        finally:
            chat_mod.build_cici_analysis_prompt = original_build

        sessions = httpx.get(f"{api_url}/api/sessions?limit=50", timeout=10.0).json()
        assert any(s.get("prompt") == "AUTO_DISPATCH_MARKER" for s in sessions)

        holder: dict[str, object] = {}

        def _read_tasks() -> None:
            holder["tasks"] = e2e_app.state.task_table.list_tasks()

        e2e_app.state.loop.call_soon_threadsafe(_read_tasks)
        deadline = time.time() + 5
        while "tasks" not in holder and time.time() < deadline:
            time.sleep(0.05)
        tasks = holder.get("tasks", [])
        matches = [t for t in tasks if t.title == "auto dispatch"]
        assert matches and matches[0].status == "done"

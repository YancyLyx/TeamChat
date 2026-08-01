"""chat.py is_busy 排队路径测试（完善点⑥ — soso咪 指出的测试缺口）。

覆盖:
- @agent busy → 排队成任务（status=queued），不 spawn
- @agent idle → 直接 spawn（保持即时交互）
- 无 @mention cici咪 busy → 分析排队（status=queued_for_cici）
- greeting 时忙的 agent 跳过（不 spawn）
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import chat
from engine.config import Config
from engine.runner import AgentResult
from engine.session_store import SessionStore
from engine.task_table import TaskTable


@pytest.fixture
def client(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()  # seeds session id=1 (FK target)
    tt = TaskTable(config)
    tt.init()

    app = FastAPI()
    app.include_router(chat.router)
    app.state.ws_manager = AsyncMock()
    app.state.store = MagicMock()
    runner = MagicMock()
    runner._run = AsyncMock()
    app.state.runner = runner
    router = MagicMock()
    app.state.router = router
    app.state.session_store = MagicMock()
    app.state.task_table = tt
    app.state.result_relay = AsyncMock()

    yield TestClient(app), tt, router, runner
    tt.close()
    ss.close()


class TestDirectMentionQueuing:
    def test_busy_target_queues_task(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = True  # coco咪 busy (TaskScheduler 派发中)

        resp = c.post("/api/chat", json={
            "content": "@coco咪 排队测试", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        tasks = tt.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].agent == "coco咪"
        assert tasks[0].status == "pending"
        runner._run.assert_not_called()  # busy → 不直接 spawn

    def test_idle_target_spawns_directly(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = False
        runner._run.return_value = AgentResult(
            agent_name="coco咪", task_prompt="x", output="ok",
            exit_code=0, duration_ms=10,
        )

        resp = c.post("/api/chat", json={
            "content": "@coco咪 直接执行", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        runner._run.assert_called_once()  # idle → 直接 spawn
        assert len(tt.list_tasks()) == 0  # 无排队任务


class TestNoMentionQueuing:
    def test_cici_busy_queues_analysis(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = True  # cici咪 正在审核

        resp = c.post("/api/chat", json={
            "content": "分析这个需求", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "queued_for_cici"
        tasks = tt.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].agent == "cici咪"
        runner._run.assert_not_called()


class TestGreetingSkip:
    def test_busy_agents_skipped(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = True  # 三只猫都忙

        resp = c.post("/api/chat", json={
            "content": "大家好", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "greeting_broadcast"
        runner._run.assert_not_called()  # 忙的 agent 不 spawn

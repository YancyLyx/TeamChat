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


class TestChatStreaming:
    """聊天室气泡段落级流式：增量 chat_stream + done 完整事件（cici咪 2026-08-03）。"""

    @staticmethod
    def _stream_events(client_app):
        """从 ws_mgr.broadcast 调用记录里过滤 chat_stream 事件。"""
        calls = client_app.state.ws_manager.broadcast.await_args_list
        return [c.args[0] for c in calls if c.args[0].get("type") == "chat_stream"]

    def test_mention_reply_streams_chunks_then_done(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = False  # coco咪 空闲 → 直接 spawn 流式

        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            await on_stream("第一段")
            await on_stream("第二段")
            return AgentResult(
                agent_name=agent.name, task_prompt=task.full_prompt(),
                output="第一段\n第二段", exit_code=0, duration_ms=10,
            )

        runner._run = fake_run

        resp = c.post("/api/chat", json={
            "content": "@coco咪 流式测试", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        events = self._stream_events(c.app)
        assert len(events) == 3  # 2 增量 + 1 done
        mids = {e["data"]["mid"] for e in events}
        assert len(mids) == 1  # 同一 mid → 前端粘到同一气泡
        chunks = [e["data"]["content"] for e in events if not e["data"].get("done")]
        assert chunks == ["第一段", "第二段"]
        done = [e for e in events if e["data"].get("done")][0]
        assert done["data"]["content"] == "第一段\n第二段"  # 完整输出兜底

    def test_greeting_streams_each_agent(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = False

        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            await on_stream(f"{agent.name}回复")
            return AgentResult(
                agent_name=agent.name, task_prompt=task.full_prompt(),
                output=f"{agent.name}回复", exit_code=0, duration_ms=10,
            )

        runner._run = fake_run

        resp = c.post("/api/chat", json={
            "content": "大家好", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        events = self._stream_events(c.app)
        # 3 个 agent × (1 增量 + 1 done)
        done_events = [e for e in events if e["data"].get("done")]
        assert len(done_events) == 3
        agents = {e["data"]["agent"] for e in done_events}
        assert agents == {"cici咪", "coco咪", "soso咪"}

    def test_analysis_streams_cici_reply(self, client):
        c, tt, router, runner = client
        router.is_busy.return_value = False

        async def fake_run(agent, task, use_continue=False, session_id=None,
                           on_stream=None, **kwargs):
            await on_stream("分析中...")
            return AgentResult(
                agent_name=agent.name, task_prompt=task.full_prompt(),
                output="分析结论：建议创建 2 个任务", exit_code=0, duration_ms=10,
            )

        runner._run = fake_run

        resp = c.post("/api/chat", json={
            "content": "帮我看看这个需求", "teamchat_session_id": 1,
        })

        assert resp.status_code == 200
        events = self._stream_events(c.app)
        assert len(events) == 2  # 增量 + done
        done = [e for e in events if e["data"].get("done")][0]
        assert done["data"]["agent"] == "cici咪"
        assert done["data"]["content"] == "分析结论：建议创建 2 个任务"
        # 落库先于 done（数据完整性）
        log_call = c.app.state.store.log
        assert log_call.call_count >= 2  # human 消息 + cici咪 分析

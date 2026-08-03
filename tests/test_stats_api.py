"""GET /api/stats — L3 解放指标 API 单测 (#30 P1, ADR-005 Stats 面板优化)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import stats as stats_endpoint
from engine.config import Config
from engine.session_store import SessionStore
from engine.store import AgentCallStore
from engine.task_table import TaskTable


@pytest.fixture
def stats_client(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()
    store = AgentCallStore(config)
    store.init()
    tt = TaskTable(config)
    tt.init()

    app = FastAPI()
    app.add_api_route("/api/stats", stats_endpoint, methods=["GET"])
    app.state.store = store
    app.state.task_table = tt

    yield TestClient(app), store, tt
    tt.close()
    store.close()
    ss.close()


def _finish_task(tt: TaskTable, task_id: int, status: str, finished_at: str) -> None:
    """Set terminal status then finished_at (update() overwrites finished_at when status set)."""
    tt.update(task_id, status=status)
    tt.update(task_id, finished_at=finished_at)


class TestStatsL3Api:
    def test_stats_response_includes_l3_four_metrics(self, stats_client):
        """构造 store + task_table + approval 数据，API l3 与 store.l3_stats 一致。"""
        client, store, tt = stats_client
        msg_at = "2026-07-31T09:00:00+00:00"

        store.log(
            agent_name="human", prompt="做个功能", output="做个功能",
            exit_code=0, duration_ms=0, task_type="chat_message", tag="prod",
            teamchat_session_id=1, started_at=msg_at, finished_at=msg_at,
        )
        for _ in range(2):
            store.log(
                agent_name="human", prompt="approval:req", output="allow",
                exit_code=0, duration_ms=0, task_type="approval", tag="prod",
                teamchat_session_id=1, started_at=msg_at, finished_at=msg_at,
            )

        for finish_at in (
            "2026-07-31T09:10:00+00:00",
            "2026-07-31T09:12:00+00:00",
            "2026-07-31T09:14:00+00:00",
        ):
            t = tt.create(agent="coco咪", title="done task", description="d")
            _finish_task(tt, t.id, "done", finish_at)
        t_ab = tt.create(agent="coco咪", title="abandoned", description="d")
        _finish_task(tt, t_ab.id, "abandoned", "2026-07-31T09:15:00+00:00")

        expected = store.l3_stats(tt, teamchat_session_id=1)

        resp = client.get("/api/stats")
        assert resp.status_code == 200
        l3 = resp.json()["l3"]

        assert set(l3.keys()) >= {
            "automation_rate", "human_interventions", "approvals",
            "message_to_completion_ms",
        }
        assert l3 == expected
        assert l3["automation_rate"] == 0.75
        assert l3["human_interventions"] == 1
        assert l3["approvals"] == 2
        assert l3["message_to_completion_ms"] == 15 * 60 * 1000

    def test_stats_l3_message_to_completion_only(self, stats_client):
        """仅消息 + 两条 done 任务 → 15 min 消息→完成（max finished_at）。"""
        client, store, tt = stats_client
        msg_at = "2026-07-31T09:00:00+00:00"
        store.log(
            agent_name="human", prompt="msg", output="msg",
            exit_code=0, duration_ms=0, task_type="chat_message", tag="prod",
            teamchat_session_id=1, started_at=msg_at, finished_at=msg_at,
        )
        t1 = tt.create(agent="coco咪", title="a", description="d")
        _finish_task(tt, t1.id, "done", "2026-07-31T09:10:00+00:00")
        t2 = tt.create(agent="soso咪", title="b", description="d")
        _finish_task(tt, t2.id, "done", "2026-07-31T09:15:00+00:00")

        l3 = client.get("/api/stats").json()["l3"]
        assert l3["message_to_completion_ms"] == 15 * 60 * 1000
        assert l3["approvals"] == 0
        assert l3["human_interventions"] == 0

    def test_stats_l3_empty_session_defaults(self, stats_client):
        client, _, _ = stats_client

        l3 = client.get("/api/stats").json()["l3"]
        assert l3["automation_rate"] == 0.0
        assert l3["human_interventions"] == 0
        assert l3["approvals"] == 0
        assert l3["message_to_completion_ms"] is None

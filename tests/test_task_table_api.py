"""Task table REST API broadcasts create/update events to the dashboard."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import tasks
from engine.config import Config
from engine.session_store import SessionStore
from engine.task_table import TaskTable


@pytest.fixture
def client(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()

    app = FastAPI()
    app.include_router(tasks.router)
    app.state.task_table = tt
    app.state.ws_manager = AsyncMock()

    yield TestClient(app), app, tt
    tt.close()
    ss.close()


class TestTaskTableBroadcast:
    def test_create_broadcasts_task_table_updated(self, client):
        c, app, tt = client

        resp = c.post("/api/tasks/table", json={
            "agent": "coco咪",
            "title": "实现 Tasks 看板",
            "depends_on": [],
        })

        assert resp.status_code == 200
        task_id = resp.json()["id"]
        call = app.state.ws_manager.broadcast.await_args
        message = call.args[0]
        assert message["type"] == "task_table_updated"
        assert message["data"]["id"] == task_id
        assert tt.get(task_id).status == "pending"

    def test_update_broadcasts_refreshed_task(self, client):
        c, app, tt = client
        created = tt.create("soso咪", "审查看板")

        resp = c.patch(f"/api/tasks/table/{created.id}", json={"status": "done"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "done"
        call = app.state.ws_manager.broadcast.await_args
        message = call.args[0]
        assert message["type"] == "task_table_updated"
        assert message["data"]["status"] == "done"
        assert message["data"]["finished_at"]

    def test_missing_task_does_not_broadcast(self, client):
        c, app, _ = client

        resp = c.patch("/api/tasks/table/999", json={"status": "done"})

        assert resp.status_code == 404
        app.state.ws_manager.broadcast.assert_not_awaited()

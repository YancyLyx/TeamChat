"""Unit tests for engine/task_table.py (ADR-003 C1)."""

from __future__ import annotations

import pytest
import sqlite3

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


def test_create_and_get_task(task_table: TaskTable):
    task = task_table.create("coco咪", "Add refresh button", depends_on=[])
    assert task.id > 0
    assert task.agent == "coco咪"
    assert task.title == "Add refresh button"
    assert task.status == "pending"
    assert task.depends_on == []
    assert task.teamchat_session_id == 1

    loaded = task_table.get(task.id)
    assert loaded is not None
    assert loaded.title == "Add refresh button"
    assert loaded.depends_on == []


def test_dependency_blocks_until_done(task_table: TaskTable):
    first = task_table.create("coco咪", "Step 1")
    second = task_table.create("soso咪", "Step 2", depends_on=[first.id])

    assert task_table.ready_to_run(first.id) is True
    assert task_table.ready_to_run(second.id) is False
    assert second.id in [t.id for t in task_table.blocked_tasks()]

    task_table.update(first.id, status="done")
    assert task_table.ready_to_run(second.id) is True
    assert second.id in [t.id for t in task_table.unblocked_tasks()]


def test_update_sets_timestamps(task_table: TaskTable):
    task = task_table.create("cici咪", "Analyze")
    task_table.update(task.id, status="running")
    running = task_table.get(task.id)
    assert running.started_at

    task_table.update(task.id, status="done", output_summary="ok")
    done = task_table.get(task.id)
    assert done.status == "done"
    assert done.output_summary == "ok"
    assert done.finished_at


def test_retry_count_and_last_error_fields(task_table: TaskTable):
    """Phase 4.5: retry_count/last_error 字段（自愈机制记录）。"""
    task = task_table.create("coco咪", "Retry test")
    assert task.retry_count == 0
    assert task.last_error == ""

    task_table.update(task.id, retry_count=2, last_error="network timeout")
    updated = task_table.get(task.id)
    assert updated.retry_count == 2
    assert updated.last_error == "network timeout"

    # to_dict 包含新字段
    d = updated.to_dict()
    assert d["retry_count"] == 2
    assert d["last_error"] == "network timeout"


def test_reset_interrupted_running_to_pending(task_table: TaskTable):
    """重启恢复: running 任务重置为 pending（session resume 可续做）。"""
    t1 = task_table.create("coco咪", "A")
    t2 = task_table.create("soso咪", "B")
    task_table.update(t1.id, status="running")
    task_table.update(t2.id, status="done")

    recovered = task_table.reset_interrupted()

    assert recovered == 1
    assert task_table.get(t1.id).status == "pending"
    assert task_table.get(t2.id).status == "done"  # 非 running 不动

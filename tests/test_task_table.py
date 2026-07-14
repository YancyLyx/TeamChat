"""Unit tests for engine/task_table.py (ADR-003 C1)."""

from __future__ import annotations

import pytest

from engine.config import Config, load_config
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
    tt = TaskTable(config)
    tt.init()
    yield tt
    tt.close()


def test_create_and_get_task(task_table: TaskTable):
    task = task_table.create("coco咪", "Add refresh button", depends_on=[])
    assert task.id > 0
    assert task.agent == "coco咪"
    assert task.title == "Add refresh button"
    assert task.status == "pending"
    assert task.depends_on == []

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

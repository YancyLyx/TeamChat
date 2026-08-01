"""Unit tests for Task Planner (ADR-005 Phase 4.2): DAG validation + tree query."""

import pytest

from engine.config import Config
from engine.session_store import SessionStore
from engine.task_planner import dag_summary, detect_cycles, task_tree
from engine.task_table import TaskTable


@pytest.fixture
def task_table(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()
    yield tt
    tt.close()
    ss.close()


class TestDetectCycles:
    def test_linear_dag_no_cycles(self, task_table):
        a = task_table.create("coco咪", "A", "impl")
        b = task_table.create("soso咪", "B", "review", depends_on=[a.id])
        c = task_table.create("cici咪", "C", "merge", depends_on=[b.id])
        assert detect_cycles(task_table) == []

    def test_parallel_dag_no_cycles(self, task_table):
        a = task_table.create("coco咪", "A", "impl")
        b = task_table.create("coco咪", "B", "impl", depends_on=[a.id])
        c = task_table.create("coco咪", "C", "impl", depends_on=[a.id])
        d = task_table.create("soso咪", "D", "test", depends_on=[b.id, c.id])
        assert detect_cycles(task_table) == []

    def test_direct_cycle_detected(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        b = task_table.create("soso咪", "B", "y", depends_on=[a.id])
        # B → A → B cycle: make A depend on B
        task_table.update(a.id, depends_on=[b.id])
        cycles = detect_cycles(task_table)
        assert len(cycles) >= 1
        assert a.id in cycles[0] and b.id in cycles[0]

    def test_self_cycle_detected(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        task_table.update(a.id, depends_on=[a.id])  # A depends on itself
        cycles = detect_cycles(task_table)
        assert cycles and cycles[0] == [a.id, a.id]


class TestTaskTree:
    def test_tree_structure(self, task_table):
        a = task_table.create("coco咪", "A", "impl")
        b = task_table.create("soso咪", "B", "review", depends_on=[a.id])
        c = task_table.create("coco咪", "C", "impl", depends_on=[a.id])
        tree = task_tree(task_table, a.id)
        assert tree["id"] == a.id
        assert {ch["id"] for ch in tree["children"]} == {b.id, c.id}
        assert tree["children"][0]["children"] == []  # leaves

    def test_unknown_root_returns_empty(self, task_table):
        assert task_tree(task_table, 999) == {}


class TestDagSummary:
    def test_summary_counts_and_cycles(self, task_table):
        task_table.create("coco咪", "A", "x")
        task_table.create("soso咪", "B", "y")
        summary = dag_summary(task_table)
        assert summary["total"] == 2
        assert summary["by_status"].get("pending") == 2
        assert summary["cycles"] == []

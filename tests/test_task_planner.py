"""Unit tests for Task Planner (ADR-005 Phase 4.2): DAG validation + tree query."""

import pytest

from engine.config import Config
from engine.session_store import SessionStore
from engine.task_planner import (
    blocked_by_failure, dag_summary, detect_cycles, orphan_deps, task_tree,
)
from engine.task_table import TaskTable


@pytest.fixture
def stores(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()
    yield ss, tt
    tt.close()
    ss.close()


@pytest.fixture
def task_table(stores):
    return stores[1]


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

    def test_three_node_cycle_detected(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        b = task_table.create("soso咪", "B", "y", depends_on=[a.id])
        c = task_table.create("cici咪", "C", "z", depends_on=[b.id])
        task_table.update(a.id, depends_on=[c.id])  # A→B→C→A
        cycles = detect_cycles(task_table)
        assert cycles and {a.id, b.id, c.id} <= set(cycles[0])

    def test_two_disconnected_cycles_both_detected(self, task_table):
        a1 = task_table.create("coco咪", "A1", "x")
        b1 = task_table.create("soso咪", "B1", "y", depends_on=[a1.id])
        task_table.update(a1.id, depends_on=[b1.id])
        a2 = task_table.create("coco咪", "A2", "x")
        b2 = task_table.create("soso咪", "B2", "y", depends_on=[a2.id])
        task_table.update(a2.id, depends_on=[b2.id])
        cycles = detect_cycles(task_table)
        assert len(cycles) == 2


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
        assert summary["orphan_deps"] == []
        assert summary["blocked_by_failure"] == []

    def test_session_isolation(self, stores):
        """soso咪 Bug 1: cycles must be scoped to the same session as counts."""
        ss, tt = stores
        ss.create("会话2", "/tmp/t2")  # session 2

        # session 1: acyclic
        tt.create("coco咪", "S1-A", "x", teamchat_session_id=1)
        # session 2: cyclic
        a = tt.create("coco咪", "S2-A", "x", teamchat_session_id=2)
        b = tt.create("soso咪", "S2-B", "y", teamchat_session_id=2, depends_on=[a.id])
        tt.update(a.id, depends_on=[b.id])

        s1 = dag_summary(tt, teamchat_session_id=1)
        s2 = dag_summary(tt, teamchat_session_id=2)

        assert s1["total"] == 1
        assert s1["cycles"] == []  # session 1 must NOT see session 2's cycle
        assert s2["total"] == 2
        assert len(s2["cycles"]) == 1


class TestOrphanAndBlocked:
    def test_orphan_deps_detected(self, task_table):
        task = task_table.create("coco咪", "A", "x", depends_on=[999])
        orphans = orphan_deps(task_table)
        assert len(orphans) == 1
        assert orphans[0]["task_id"] == task.id
        assert orphans[0]["missing_deps"] == [999]

    def test_blocked_by_failure_detected(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        b = task_table.create("soso咪", "B", "y", depends_on=[a.id])
        task_table.update(a.id, status="failed")
        blocked = blocked_by_failure(task_table)
        assert len(blocked) == 1
        assert blocked[0]["task_id"] == b.id
        assert blocked[0]["blocked_by"] == [a.id]

    def test_blocked_by_abandoned_detected(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        b = task_table.create("soso咪", "B", "y", depends_on=[a.id])
        task_table.update(a.id, status="abandoned")
        blocked = blocked_by_failure(task_table)
        assert len(blocked) == 1

    def test_done_dependency_not_blocked(self, task_table):
        a = task_table.create("coco咪", "A", "x")
        b = task_table.create("soso咪", "B", "y", depends_on=[a.id])
        task_table.update(a.id, status="done")
        assert blocked_by_failure(task_table) == []

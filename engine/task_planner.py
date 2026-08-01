"""
Task Planner — DAG 建模辅助 (ADR-005 Phase 4.2).

中枢模式铁律: Engine 不决策（不判断该不该拆、不写 prompt）。
本模块只提供**确定性校验和查询**，辅助 cici咪 建模:
  - detect_cycles: 检测依赖图中的循环（cici咪 建任务时的防错）
  - task_tree: 以某任务为根的 DAG 子树（可视化/调试）

DAG 建模本身是 cici咪 的行为（create_task 带 depends_on），
Engine 只负责让错误的图（循环依赖）尽早暴露。
"""

import logging

from engine.task_table import TaskTable

logger = logging.getLogger(__name__)

_WHITE, _GRAY, _BLACK = 0, 1, 2  # DFS 三色标记


def detect_cycles(task_table: TaskTable) -> list[list[int]]:
    """Detect dependency cycles in the task DAG.

    Returns a list of cycles, each a list of task IDs, e.g. [[5, 6, 5]].
    Empty list = the DAG is acyclic.
    """
    tasks = task_table.list_tasks()
    graph: dict[int, list[int]] = {t.id: list(t.depends_on) for t in tasks}
    color: dict[int, int] = {tid: _WHITE for tid in graph}
    cycles: list[list[int]] = []
    stack: list[int] = []

    def dfs(node: int):
        color[node] = _GRAY
        stack.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:  # dependency on a deleted/unknown task
                continue
            if color[dep] == _GRAY:
                idx = stack.index(dep)
                cycle = stack[idx:] + [dep]
                if cycle not in cycles:
                    cycles.append(cycle)
            elif color[dep] == _WHITE:
                dfs(dep)
        stack.pop()
        color[node] = _BLACK

    for tid in graph:
        if color[tid] == _WHITE:
            dfs(tid)

    if cycles:
        logger.warning(f"⚠️  Dependency cycles detected: {cycles}")
    return cycles


def task_tree(task_table: TaskTable, root_id: int, _depth: int = 0) -> dict:
    """Build the DAG subtree rooted at task_id (children = tasks depending on it).

    Returns {"id", "title", "agent", "status", "children": [...]}.
    Depth-limited to avoid runaway on cyclic graphs.
    """
    if _depth > 10:
        return {"id": root_id, "truncated": True}
    task = task_table.get(root_id)
    if not task:
        return {}
    children = task_table.children_waiting_on(root_id)
    return {
        "id": task.id,
        "title": task.title,
        "agent": task.agent,
        "status": task.status,
        "children": [task_tree(task_table, c.id, _depth + 1) for c in children],
    }


def dag_summary(task_table: TaskTable, teamchat_session_id: int | None = None) -> dict:
    """High-level summary of the task DAG for dashboard/debugging."""
    tasks = task_table.list_tasks(teamchat_session_id=teamchat_session_id)
    by_status: dict[str, int] = {}
    for t in tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1
    return {
        "total": len(tasks),
        "by_status": by_status,
        "cycles": detect_cycles(task_table),
    }

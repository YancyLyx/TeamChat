"""
Task Table — structured task storage with dependency tracking.

Used by cici咪's MCP tools (create_task, update_task, list_tasks)
and by Engine's dispatch logic (dependency checking, queuing).
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from engine.config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_table (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    teamchat_session_id INTEGER NOT NULL DEFAULT 1,
    agent       TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'pending',
    depends_on  TEXT    NOT NULL DEFAULT '[]',
    github_issue TEXT   NOT NULL DEFAULT '',
    output_summary TEXT NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    started_at  TEXT    NOT NULL DEFAULT '',
    finished_at TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (teamchat_session_id) REFERENCES teamchat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_task_session ON task_table(teamchat_session_id);
CREATE INDEX IF NOT EXISTS idx_task_status ON task_table(status);
CREATE INDEX IF NOT EXISTS idx_task_agent ON task_table(agent);
"""


@dataclass
class Task:
    id: int = 0
    teamchat_session_id: int = 1
    agent: str = ""
    title: str = ""
    description: str = ""
    status: str = "pending"
    depends_on: list[int] = field(default_factory=list)
    github_issue: str = ""
    output_summary: str = ""
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.status == "pending" and len(self.depends_on) > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "teamchat_session_id": self.teamchat_session_id,
            "agent": self.agent,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "depends_on": self.depends_on,
            "github_issue": self.github_issue,
            "output_summary": self.output_summary,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class TaskTable:
    """SQLite-backed task table with dependency management."""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = config.teamchat_dir / "teamchat.db"
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle --

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("TaskTable not initialized")
        return self._conn

    def init(self):
        self.config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(task_table)")}
        if "teamchat_session_id" not in columns:
            self._conn.execute(
                "ALTER TABLE task_table ADD COLUMN teamchat_session_id INTEGER NOT NULL DEFAULT 1"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_session ON task_table(teamchat_session_id)"
            )
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- CRUD --

    def create(self, agent: str, title: str, description: str = "",
               depends_on: list[int] | None = None,
               teamchat_session_id: int = 1) -> Task:
        """Create a new task. Returns the created Task with ID."""
        now = datetime.now(timezone.utc).isoformat()
        deps = json.dumps(depends_on or [], ensure_ascii=False)
        self.conn.execute(
            """INSERT INTO task_table
               (teamchat_session_id, agent, title, description, status, depends_on, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (teamchat_session_id, agent, title, description, deps, now),
        )
        self.conn.commit()
        row_id = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return self.get(row_id)  # type: ignore

    def get(self, task_id: int) -> Task | None:
        row = self.conn.execute(
            "SELECT * FROM task_table WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def update(self, task_id: int, **kwargs):
        """Update task fields. e.g., update(14, status='done', output_summary='...')"""
        allowed = {"agent", "title", "description", "status",
                   "depends_on", "github_issue", "output_summary",
                   "started_at", "finished_at", "teamchat_session_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        if "depends_on" in updates and isinstance(updates["depends_on"], list):
            updates["depends_on"] = json.dumps(updates["depends_on"], ensure_ascii=False)

        # Auto-set timestamps
        now = datetime.now(timezone.utc).isoformat()
        if updates.get("status") == "running" and "started_at" not in updates:
            updates["started_at"] = now
        if updates.get("status") in ("done", "failed", "abandoned"):
            updates["finished_at"] = now

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        self.conn.execute(
            f"UPDATE task_table SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

    def list_tasks(self, status: str | None = None, agent: str | None = None,
                   teamchat_session_id: int | None = None) -> list[Task]:
        """List tasks, optionally filtered."""
        conditions = []
        params = []
        if teamchat_session_id is not None:
            conditions.append("teamchat_session_id = ?")
            params.append(teamchat_session_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if agent:
            conditions.append("agent = ?")
            params.append(agent)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = self.conn.execute(
            f"SELECT * FROM task_table{where} ORDER BY id ASC", params
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def delete(self, task_id: int):
        self.conn.execute("DELETE FROM task_table WHERE id = ?", (task_id,))
        self.conn.commit()

    # -- dependency logic --

    def ready_to_run(self, task_id: int) -> bool:
        """Check if all dependencies are done."""
        task = self.get(task_id)
        if not task:
            return False
        if task.status != "pending":
            return False
        for dep_id in task.depends_on:
            dep = self.get(dep_id)
            if not dep or dep.status != "done":
                return False
        return True

    def unblocked_tasks(self) -> list[Task]:
        """Find all pending tasks whose dependencies are satisfied."""
        pending = self.list_tasks(status="pending")
        return [t for t in pending if self.ready_to_run(t.id)]

    def blocked_tasks(self) -> list[Task]:
        """Find all pending tasks with unsatisfied dependencies."""
        pending = self.list_tasks(status="pending")
        return [t for t in pending if not self.ready_to_run(t.id)]

    def children_waiting_on(self, task_id: int) -> list[Task]:
        """Find tasks that depend on the given task."""
        all_tasks = self.list_tasks()
        return [t for t in all_tasks if task_id in t.depends_on]

    # -- stats --

    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM task_table GROUP BY status"
        ).fetchall()
        by_status = {r[0]: r[1] for r in rows}
        total = sum(by_status.values())
        done = by_status.get("done", 0)
        return {
            "total": total,
            "done": done,
            "pending": by_status.get("pending", 0),
            "running": by_status.get("running", 0),
            "failed": by_status.get("failed", 0),
            "completion_rate": done / total if total > 0 else 0.0,
            "by_agent": self._stats_by_agent(),
        }

    def _stats_by_agent(self) -> dict:
        rows = self.conn.execute(
            "SELECT agent, status, COUNT(*) FROM task_table GROUP BY agent, status"
        ).fetchall()
        result: dict = {}
        for agent, status, count in rows:
            if agent not in result:
                result[agent] = {"done": 0, "total": 0, "failed": 0}
            result[agent][status] = count
            result[agent]["total"] += count
        for agent in result:
            t = result[agent]["total"]
            d = result[agent]["done"]
            result[agent]["completion_rate"] = d / t if t > 0 else 0.0
        return result

    # -- helpers --

    def _row_to_task(self, row: tuple) -> Task:
        # Legacy rows: (id, agent, ...) without teamchat_session_id
        if len(row) >= 12:
            session_id = row[1]
            offset = 1
        else:
            session_id = 1
            offset = 0
        depends_raw = row[5 + offset] if len(row) > 5 + offset else "[]"
        try:
            depends = json.loads(depends_raw) if isinstance(depends_raw, str) else depends_raw
        except (json.JSONDecodeError, TypeError):
            depends = []
        return Task(
            id=row[0],
            teamchat_session_id=session_id,
            agent=row[1 + offset],
            title=row[2 + offset],
            description=row[3 + offset],
            status=row[4 + offset],
            depends_on=depends,
            github_issue=row[6 + offset] if len(row) > 6 + offset else "",
            output_summary=row[7 + offset] if len(row) > 7 + offset else "",
            created_at=row[8 + offset] if len(row) > 8 + offset else "",
            started_at=row[9 + offset] if len(row) > 9 + offset else "",
            finished_at=row[10 + offset] if len(row) > 10 + offset else "",
        )


def create_task_table(config: Config | None = None) -> TaskTable:
    if config is None:
        from engine.config import load_config
        config = load_config()
    tt = TaskTable(config)
    tt.init()
    return tt

"""
Session Store — SQLite-backed agent invocation history.

Stores every agent call: prompt, output, timing, token usage.
Provides fast query interfaces for the Dashboard (Phase 3) and debugging.
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.config import Config

# ---- Schema ----

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name  TEXT    NOT NULL,
    task_type   TEXT    NOT NULL DEFAULT 'general',
    prompt      TEXT    NOT NULL,
    output      TEXT    NOT NULL DEFAULT '',
    exit_code   INTEGER NOT NULL DEFAULT -1,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    token_usage TEXT    NOT NULL DEFAULT '{}',
    tag         TEXT    NOT NULL DEFAULT 'prod',
    started_at  TEXT    NOT NULL,
    finished_at TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_name);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_type ON sessions(task_type);
"""


@dataclass
class SessionRow:
    """One row from the sessions table."""
    id: int
    agent_name: str
    task_type: str
    prompt: str
    output: str
    exit_code: int
    duration_ms: int
    token_usage: dict
    tag: str
    started_at: str
    finished_at: str
    created_at: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def output_preview(self) -> str:
        return self.output[:200] + "..." if len(self.output) > 200 else self.output


class SessionStore:
    """SQLite-backed store for agent invocation history."""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = config.teamchat_dir / "sessions.db"
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    # ---- Lifecycle ----

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SessionStore not initialized. Call init() first.")
        return self._conn

    def init(self):
        """Create the database and tables. Idempotent."""
        self.config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads
        self._conn.executescript(SCHEMA)
        # Migrate older databases missing the tag column
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(sessions)")}
        if "tag" not in columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN tag TEXT NOT NULL DEFAULT 'prod'")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_tag ON sessions(tag)")
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- Write ----

    def log(self, agent_name: str, prompt: str, output: str,
            exit_code: int, duration_ms: int, token_usage: dict | None = None,
            task_type: str = "general", tag: str = "prod",
            started_at: str = "", finished_at: str = "") -> int:
        """Record one agent invocation. Returns the new row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                """INSERT INTO sessions
                   (agent_name, task_type, prompt, output, exit_code, duration_ms,
                    token_usage, tag, started_at, finished_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_name, task_type, prompt, output, exit_code,
                    duration_ms, json.dumps(token_usage or {}, ensure_ascii=False), tag,
                    started_at or now, finished_at or now, now,
                ),
            )
            self.conn.commit()
            return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ---- Read ----

    def get_recent(self, limit: int = 20, agent_name: str | None = None,
                   tag: str | None = None) -> list[SessionRow]:
        """Get recent sessions, optionally filtered by agent and/or tag."""
        query = "SELECT * FROM sessions"
        conditions: list[str] = []
        params: list = []
        if agent_name:
            conditions.append("agent_name = ?")
            params.append(agent_name)
        if tag:
            conditions.append("tag = ?")
            params.append(tag)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_by_id(self, session_id: int) -> SessionRow | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    # ---- Stats ----

    def stats(self, agent_name: str | None = None) -> dict:
        """Aggregated stats: total calls, success rate, avg duration."""
        where = "WHERE agent_name = ?" if agent_name else ""
        params = (agent_name,) if agent_name else ()

        total = self.conn.execute(
            f"SELECT COUNT(*) FROM sessions {where}", params
        ).fetchone()[0]

        success = self.conn.execute(
            f"SELECT COUNT(*) FROM sessions {where} AND exit_code = 0", params
        ).fetchone()[0] if total > 0 else 0

        avg_dur = self.conn.execute(
            f"SELECT AVG(duration_ms) FROM sessions {where}", params
        ).fetchone()[0] or 0

        token_rows = self.conn.execute(
            f"SELECT token_usage FROM sessions {where}", params
        ).fetchall()
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for (raw_usage,) in token_rows:
            try:
                usage = json.loads(raw_usage) if isinstance(raw_usage, str) else (raw_usage or {})
            except json.JSONDecodeError:
                usage = {}
            if not isinstance(usage, dict):
                continue
            input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or usage.get("tokens") or 0)
            token_usage["input_tokens"] += input_tokens
            token_usage["output_tokens"] += output_tokens
            token_usage["total_tokens"] += total_tokens or input_tokens + output_tokens

        return {
            "total_calls": total,
            "total_success": success,
            "success_rate": success / total if total > 0 else 0.0,
            "avg_duration_ms": round(avg_dur, 0),
            "token_usage": token_usage,
            "total_tokens": token_usage["total_tokens"],
        }

    def stats_by_agent(self) -> dict[str, dict]:
        """Per-agent stats."""
        agents = self.conn.execute(
            "SELECT DISTINCT agent_name FROM sessions"
        ).fetchall()
        return {a[0]: self.stats(agent_name=a[0]) for a in agents}

    # ---- Helpers ----

    def _row_to_session(self, row: tuple) -> SessionRow:
        return SessionRow(
            id=row[0],
            agent_name=row[1],
            task_type=row[2],
            prompt=row[3],
            output=row[4],
            exit_code=row[5],
            duration_ms=row[6],
            token_usage=json.loads(row[7]) if isinstance(row[7], str) else row[7],
            tag=row[8],
            started_at=row[9],
            finished_at=row[10],
            created_at=row[11],
        )


def create_store(config: Config | None = None) -> SessionStore:
    """Factory: create and initialize a SessionStore."""
    if config is None:
        from engine.config import load_config
        config = load_config()
    store = SessionStore(config)
    store.init()
    return store

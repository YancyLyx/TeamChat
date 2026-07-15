"""
TeamChat Session Store — persists named sessions with agent session IDs.
Each session = {name, directory, claude_id, codex_id, cursor_id, status}.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine.config import Config

DEFAULT_SESSION_NAME = "TeamChat 开发"

SCHEMA = """
CREATE TABLE IF NOT EXISTS teamchat_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    directory   TEXT    NOT NULL,
    claude_id   TEXT    DEFAULT '',
    codex_id    TEXT    DEFAULT '',
    cursor_id   TEXT    DEFAULT '',
    status      TEXT    DEFAULT 'active',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class TeamChatSession:
    id: int = 0
    name: str = ""
    directory: str = ""
    claude_id: str = ""
    codex_id: str = ""
    cursor_id: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "directory": self.directory,
            "claude_id": self.claude_id, "codex_id": self.codex_id,
            "cursor_id": self.cursor_id, "status": self.status,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


def _discover_agent_session_ids(project_root: Path) -> dict[str, str]:
    """Discover CLI session IDs from local agent storage (if present)."""
    from engine.runtime import find_claude_session, find_codex_session, find_cursor_session

    return {
        "claude_id": find_claude_session(project_root) or "",
        "codex_id": find_codex_session() or "",
        "cursor_id": find_cursor_session() or "",
    }


class SessionStore:
    """SQLite store for TeamChat sessions (project-level, not CLI sessions)."""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = config.teamchat_dir / "teamchat.db"
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle --

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SessionStore not initialized")
        return self._conn

    def init(self):
        self.config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        # Seed default session if database is empty
        if self.count() == 0:
            s = self.create(DEFAULT_SESSION_NAME, str(self.config.project_root))
            # Known session IDs for the TeamChat project directory
            self.update(s.id,
                claude_id="5fbaf844-4cbc-48b2-9242-7902d098bd81",
                codex_id="019f40ef-e8cf-76f0-8b49-6691cc7275f3",
                cursor_id="04e64d6d-de38-4861-a7ce-87c26d28d77f",
            )

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- CRUD --

    def create(self, name: str, directory: str) -> TeamChatSession:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO teamchat_sessions (name, directory, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, directory, now, now),
        )
        self.conn.commit()
        rid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return self.get(rid)  # type: ignore

    def get(self, session_id: int) -> TeamChatSession | None:
        row = self.conn.execute(
            "SELECT * FROM teamchat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_all(self) -> list[TeamChatSession]:
        rows = self.conn.execute(
            "SELECT * FROM teamchat_sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def update(self, session_id: int, **kwargs):
        allowed = {"name", "directory", "claude_id", "codex_id", "cursor_id", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        self.conn.execute(
            f"UPDATE teamchat_sessions SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

    def delete(self, session_id: int):
        self.conn.execute("DELETE FROM teamchat_sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM teamchat_sessions").fetchone()[0]

    def _row_to_session(self, row: tuple) -> TeamChatSession:
        return TeamChatSession(
            id=row[0], name=row[1], directory=row[2],
            claude_id=row[3] if len(row) > 3 else "",
            codex_id=row[4] if len(row) > 4 else "",
            cursor_id=row[5] if len(row) > 5 else "",
            status=row[6] if len(row) > 6 else "active",
            created_at=row[7] if len(row) > 7 else "",
            updated_at=row[8] if len(row) > 8 else "",
        )


def create_session_store(config: Config | None = None) -> SessionStore:
    if config is None:
        from engine.config import load_config
        config = load_config()
    ss = SessionStore(config)
    ss.init()
    return ss

"""
Agent Call Store — unified SQLite log of every Engine CLI invocation.

Stored in .teamchat/teamchat.db alongside task_table and teamchat_sessions.
FK-linked to teamchat_sessions.id for data isolation.
"""

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from engine.config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    teamchat_session_id INTEGER NOT NULL DEFAULT 1,
    agent_name  TEXT    NOT NULL,
    task_type   TEXT    NOT NULL DEFAULT 'general',
    prompt      TEXT    NOT NULL,
    output      TEXT    NOT NULL DEFAULT '',
    exit_code   INTEGER NOT NULL DEFAULT -1,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    token_usage TEXT    NOT NULL DEFAULT '{}',
    tool_calls  TEXT    NOT NULL DEFAULT '[]',
    tag         TEXT    NOT NULL DEFAULT 'prod',
    started_at  TEXT    NOT NULL,
    finished_at TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (teamchat_session_id) REFERENCES teamchat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_ac_session ON agent_calls(teamchat_session_id);
CREATE INDEX IF NOT EXISTS idx_ac_agent ON agent_calls(agent_name);
CREATE INDEX IF NOT EXISTS idx_ac_tag ON agent_calls(tag);
CREATE INDEX IF NOT EXISTS idx_ac_started ON agent_calls(started_at);
CREATE INDEX IF NOT EXISTS idx_ac_task_type ON agent_calls(task_type);
"""


@dataclass
class CallRow:
    id: int
    teamchat_session_id: int
    agent_name: str
    task_type: str
    prompt: str
    output: str
    exit_code: int
    duration_ms: int
    token_usage: dict
    tool_calls: list
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


class AgentCallStore:
    def __init__(self, config: Config):
        self.config = config
        self.db_path = config.teamchat_dir / "teamchat.db"
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("AgentCallStore not initialized")
        return self._conn

    def init(self):
        self.config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def log(self, agent_name: str, prompt: str, output: str,
            exit_code: int, duration_ms: int,
            token_usage: dict | None = None,
            tool_calls: list | None = None,
            task_type: str = "general", tag: str = "prod",
            teamchat_session_id: int = 1,
            started_at: str = "", finished_at: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                """INSERT INTO agent_calls
                   (teamchat_session_id, agent_name, task_type, prompt, output,
                    exit_code, duration_ms, token_usage, tool_calls, tag,
                    started_at, finished_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (teamchat_session_id, agent_name, task_type, prompt, output,
                 exit_code, duration_ms,
                 json.dumps(token_usage or {}, ensure_ascii=False),
                 json.dumps(tool_calls or [], ensure_ascii=False),
                 tag, started_at or now, finished_at or now, now),
            )
            self._conn.commit()
            return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_recent(self, limit: int = 20, agent_name: str | None = None,
                   tag: str = "prod", teamchat_session_id: int = 1) -> list[CallRow]:
        query = "SELECT * FROM agent_calls WHERE tag = ? AND teamchat_session_id = ?"
        params = [tag, teamchat_session_id]
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_call(r) for r in rows]

    def get_by_id(self, call_id: int) -> CallRow | None:
        row = self.conn.execute(
            "SELECT * FROM agent_calls WHERE id = ?", (call_id,)
        ).fetchone()
        return self._row_to_call(row) if row else None

    def stats(self, agent_name: str | None = None,
              tag: str = "prod", teamchat_session_id: int = 1) -> dict:
        base = "SELECT COUNT(*) FROM agent_calls WHERE tag = ? AND teamchat_session_id = ?"
        params = [tag, teamchat_session_id]
        if agent_name:
            base += " AND agent_name = ?"
            params.append(agent_name)
        total = self.conn.execute(base, params).fetchone()[0]
        success = self.conn.execute(
            base.replace("COUNT(*)", "COUNT(*)") + " AND exit_code = 0", params
        ).fetchone()[0] if total > 0 else 0
        avg_dur = self.conn.execute(
            base.replace("COUNT(*)", "AVG(duration_ms)"), params
        ).fetchone()[0] or 0

        token_rows = self.conn.execute(
            base.replace("COUNT(*)", "token_usage"), params
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

    def stats_by_agent(self, tag: str = "prod", teamchat_session_id: int = 1) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT DISTINCT agent_name FROM agent_calls WHERE tag = ? AND teamchat_session_id = ?",
            (tag, teamchat_session_id),
        ).fetchall()
        return {r[0]: self.stats(agent_name=r[0], tag=tag, teamchat_session_id=teamchat_session_id) for r in rows}

    def token_stats(self, agent_name: str | None = None,
                    tag: str = "prod", teamchat_session_id: int = 1) -> dict:
        """Aggregate token usage from JSON token_usage field."""
        query = "SELECT token_usage FROM agent_calls WHERE tag = ? AND teamchat_session_id = ?"
        params = [tag, teamchat_session_id]
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        rows = self.conn.execute(query, params).fetchall()

        input_t, output_t = 0, 0
        for (raw,) in rows:
            try:
                tu = json.loads(raw) if isinstance(raw, str) else (raw or {})
                input_t += tu.get("input_tokens", 0) or 0
                output_t += tu.get("output_tokens", 0) or 0
            except Exception:
                pass
        return {
            "input_tokens": input_t,
            "output_tokens": output_t,
            "total_tokens": input_t + output_t,
        }

    def tool_stats(self, agent_name: str | None = None,
                   tag: str = "prod", teamchat_session_id: int = 1) -> dict:
        """Aggregate tool call stats from JSON tool_calls field."""
        query = "SELECT tool_calls FROM agent_calls WHERE tag = ? AND teamchat_session_id = ?"
        params = [tag, teamchat_session_id]
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        rows = self.conn.execute(query, params).fetchall()

        total = 0
        by_name: dict[str, int] = {}
        for (raw,) in rows:
            try:
                tc = json.loads(raw) if isinstance(raw, str) else (raw or [])
                for t in tc:
                    total += 1
                    name = t.get("name", "unknown") if isinstance(t, dict) else str(t)
                    by_name[name] = by_name.get(name, 0) + 1
            except Exception:
                pass
        return {"total_tool_calls": total, "tools_by_name": by_name}

    def _row_to_call(self, row: tuple) -> CallRow:
        tu_raw = row[8] if len(row) > 8 else "{}"
        tc_raw = row[9] if len(row) > 9 else "[]"
        try:
            token_usage = json.loads(tu_raw) if isinstance(tu_raw, str) else tu_raw
        except Exception:
            token_usage = {}
        try:
            tool_calls = json.loads(tc_raw) if isinstance(tc_raw, str) else tc_raw
        except Exception:
            tool_calls = []
        return CallRow(
            id=row[0], teamchat_session_id=row[1], agent_name=row[2],
            task_type=row[3], prompt=row[4], output=row[5],
            exit_code=row[6], duration_ms=row[7],
            token_usage=token_usage, tool_calls=tool_calls,
            tag=row[10] if len(row) > 10 else "prod",
            started_at=row[11] if len(row) > 11 else "",
            finished_at=row[12] if len(row) > 12 else "",
            created_at=row[13] if len(row) > 13 else "",
        )


def create_store(config: Config | None = None) -> AgentCallStore:
    if config is None:
        from engine.config import load_config
        config = load_config()
    store = AgentCallStore(config)
    store.init()
    return store


# Backward-compatible alias used by older imports/tests
SessionStore = AgentCallStore

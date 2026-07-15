"""
Runtime Manager — CLI process lifecycle + stream-json event parsing.

Manages spawn/parse/communicate/resume for Claude, Codex, and Cursor CLIs.
Unifies their different JSON event formats into a common AgentEvent type.
"""

import asyncio
import json
import logging
import os
import glob
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from engine.config import AgentIdentity, Config, ALL_AGENTS

logger = logging.getLogger(__name__)

# ---- Unified Event Types ----


@dataclass
class AgentEvent:
    """Unified event from any agent CLI."""
    type: str  # "text" | "thinking" | "tool_use" | "result" | "error" | "session_init" | "done"
    agent_name: str
    content: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    session_id: str = ""
    duration_ms: int = 0
    usage: dict = field(default_factory=dict)
    is_error: bool = False
    raw: dict = field(default_factory=dict)


# ---- Session Discovery ----


def find_claude_session(project_root: Path) -> str | None:
    """Find the latest Claude session ID for this project."""
    project_slug = str(project_root.resolve()).replace("/", "-")
    sessions_dir = Path.home() / ".claude" / "projects" / project_slug
    if not sessions_dir.exists():
        return None
    jsonl_files = sorted(sessions_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    for f in jsonl_files:
        sid = f.stem  # e.g., "5fbaf844-4cbc-48b2-9242-7902d098bd81"
        if "-" in sid and len(sid) == 36:  # UUID format
            return sid
    return None


def find_codex_session() -> str | None:
    """Find the latest Codex session ID from session storage."""
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        return None
    # Scan year/month directories for session files
    latest = None
    latest_mtime = 0
    for f in sessions_root.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".jsonl"):
            mtime = os.path.getmtime(f)
            if mtime > latest_mtime:
                latest_mtime = mtime
                # Session ID is usually in the parent dir name or file name
                parent = f.parent.name
                if "-" in parent and len(parent) > 20:
                    latest = parent
                elif "-" in f.stem and len(f.stem) > 20:
                    latest = f.stem
    return latest


def find_cursor_session() -> str | None:
    """Find the latest Cursor session ID."""
    # Cursor stores sessions as: ~/.cursor/chats/<session_id>.jsonl
    chats_dir = Path.home() / ".cursor" / "chats"
    if not chats_dir.exists():
        return None
    latest = None
    latest_mtime = 0
    for f in chats_dir.rglob("*.jsonl"):
        mtime = os.path.getmtime(f)
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest = f.stem
    for f in chats_dir.rglob("*.json"):
        mtime = os.path.getmtime(f)
        if mtime > latest_mtime and "agent" in f.stem.lower():
            latest_mtime = mtime
            latest = f.stem
    return latest


# ---- CLI Command Builders ----


def build_claude_cmd(config: Config, agent: AgentIdentity, prompt: str,
                     session_id: str | None = None) -> list[str]:
    """Build Claude CLI command with stream-json flags."""
    cli_path = config.get_cli_path(agent)
    cmd = [
        cli_path, "--print", "--verbose",
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--permission-prompt-tool", "stdio",
    ]
    if session_id:
        cmd.extend(["--resume", session_id])
    # prompt will be sent via stdin
    return cmd


def build_codex_cmd(config: Config, agent: AgentIdentity, prompt: str,
                    session_id: str | None = None) -> list[str]:
    """Build Codex CLI command with --json flag."""
    cli_path = config.get_cli_path(agent)
    if session_id:
        cmd = [cli_path, "exec", "resume", session_id, "--json", prompt]
    else:
        cmd = [cli_path, "exec", "--json", prompt]
    return cmd


def build_cursor_cmd(config: Config, agent: AgentIdentity, prompt: str,
                     session_id: str | None = None) -> list[str]:
    """Build Cursor CLI command with stream-json flags."""
    cli_path = config.get_cli_path(agent)
    cmd = [
        cli_path, "--print",
        "--output-format", "stream-json",
    ]
    if session_id:
        cmd.append(f"--resume={session_id}")
    else:
        cmd.append("--continue")  # fallback: resume last session
    cmd.append(prompt)
    return cmd


# ---- Runtime Manager ----


class RuntimeManager:
    """Manages CLI process lifecycle for all agents."""

    def __init__(self, config: Config):
        self.config = config
        self.sessions: dict[str, str] = {}  # agent_name -> session_id

    def discover_sessions(self) -> dict[str, str]:
        """Scan CLI storage directories for existing sessions."""
        discovered = {}
        # Claude
        cid = find_claude_session(self.config.project_root)
        if cid:
            discovered["cici咪"] = cid
            logger.info(f"Found Claude session: {cid}")
        # Codex
        xid = find_codex_session()
        if xid:
            discovered["coco咪"] = xid
            logger.info(f"Found Codex session: {xid}")
        # Cursor
        sid = find_cursor_session()
        if sid:
            discovered["soso咪"] = sid
            logger.info(f"Found Cursor session: {sid}")
        self.sessions.update(discovered)
        return discovered

    def get_session_id(self, agent: AgentIdentity) -> str | None:
        return self.sessions.get(agent.name)

    def set_session_id(self, agent: AgentIdentity, session_id: str):
        self.sessions[agent.name] = session_id
        # Persist to .teamchat/
        sid_file = self.config.teamchat_dir / f"session_{agent.cli}.txt"
        sid_file.write_text(session_id)

    async def send(self, agent: AgentIdentity, prompt: str) -> list[AgentEvent]:
        """
        Send a message to an agent CLI and collect parsed events.

        1. Spawn CLI with --resume if session exists
        2. For Claude: write prompt to stdin (stream-json input format)
        3. For Codex/Cursor: prompt is in CLI args
        4. Parse stdout JSONL events into unified AgentEvent list
        5. Return all events
        """
        session_id = self.get_session_id(agent)

        if agent.cli == "claude":
            events = await self._run_claude(agent, prompt, session_id)
        elif agent.cli == "codex":
            events = await self._run_codex(agent, prompt, session_id)
        else:
            events = await self._run_cursor(agent, prompt, session_id)

        # Store session ID from init event
        for evt in events:
            if evt.type == "session_init" and evt.session_id:
                self.set_session_id(agent, evt.session_id)

        return events

    # ---- Claude (stdin/stdout stream-json) ----

    async def _run_claude(self, agent: AgentIdentity, prompt: str,
                          session_id: str | None) -> list[AgentEvent]:
        cmd = build_claude_cmd(self.config, agent, prompt, session_id)
        logger.info(f"Spawning Claude: {' '.join(cmd[:5])}... resume={session_id or 'none'}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.config.project_root),
        )

        # Send user message via stdin
        user_msg = json.dumps({
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        }, ensure_ascii=False) + "\n"
        process.stdin.write(user_msg.encode("utf-8"))
        await process.stdin.drain()

        events = []
        pending_reply = ""

        async for line in process.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                raw = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            etype = raw.get("type", "")

            if etype == "system":
                sid = raw.get("session_id", "")
                if sid and not session_id:
                    session_id = sid
                events.append(AgentEvent(
                    type="session_init", agent_name=agent.name, session_id=sid, raw=raw))

            elif etype == "assistant":
                for item in raw.get("message", {}).get("content", []):
                    if item.get("type") == "text":
                        t = item.get("text", "")
                        pending_reply = t
                        events.append(AgentEvent(
                            type="text", agent_name=agent.name, content=t, raw=raw))
                    elif item.get("type") == "thinking":
                        events.append(AgentEvent(
                            type="thinking", agent_name=agent.name,
                            content=item.get("thinking", ""), raw=raw))
                    elif item.get("type") == "tool_use":
                        events.append(AgentEvent(
                            type="tool_use", agent_name=agent.name,
                            tool_name=item.get("name", ""),
                            tool_input=item.get("input", {}), raw=raw))

            elif etype == "result":
                events.append(AgentEvent(
                    type="done", agent_name=agent.name,
                    content=raw.get("result", "") or pending_reply,
                    duration_ms=raw.get("duration_ms", 0),
                    usage=raw.get("usage", {}),
                    is_error=raw.get("subtype") == "error",
                    raw=raw))
                # Close stdin to finish
                if process.stdin and not process.stdin.is_closing():
                    process.stdin.write_eof()
                    await process.stdin.drain()

        await process.wait()
        return events

    # ---- Codex (prompt in args, stdout JSONL) ----

    async def _run_codex(self, agent: AgentIdentity, prompt: str,
                         session_id: str | None) -> list[AgentEvent]:
        cmd = build_codex_cmd(self.config, agent, prompt, session_id)
        logger.info(f"Spawning Codex: {' '.join(cmd[:4])}... resume={session_id or 'none'}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.config.project_root),
        )

        events = []
        async for line in process.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                raw = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            etype = raw.get("type", "")

            if etype == "thread.started":
                tid = raw.get("thread_id", "")
                if tid:
                    session_id = tid
                    self.set_session_id(agent, tid)
                events.append(AgentEvent(
                    type="session_init", agent_name=agent.name, session_id=tid, raw=raw))

            elif etype == "turn.started":
                pass  # marker, no content

            elif etype == "item.completed":
                item = raw.get("item", {})
                itype = item.get("type", "")
                if itype == "reasoning":
                    events.append(AgentEvent(
                        type="thinking", agent_name=agent.name,
                        content=item.get("text", ""), raw=raw))
                elif itype == "agent_message":
                    events.append(AgentEvent(
                        type="text", agent_name=agent.name,
                        content=item.get("text", ""), raw=raw))
                elif itype == "command_execution":
                    events.append(AgentEvent(
                        type="tool_use", agent_name=agent.name,
                        tool_name=item.get("command", "")[:80],
                        tool_input={"exit_code": item.get("exit_code")}, raw=raw))

            elif etype == "turn.completed":
                events.append(AgentEvent(
                    type="done", agent_name=agent.name,
                    usage=raw.get("usage", {}), raw=raw))

        await process.wait()
        return events

    # ---- Cursor (prompt in args, stdout stream-json) ----

    async def _run_cursor(self, agent: AgentIdentity, prompt: str,
                          session_id: str | None) -> list[AgentEvent]:
        cmd = build_cursor_cmd(self.config, agent, prompt, session_id)
        logger.info(f"Spawning Cursor: {' '.join(cmd[:4])}... resume={session_id or 'none'}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.config.project_root),
        )

        events = []
        async for line in process.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                raw = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            etype = raw.get("type", "")

            if etype == "system":
                events.append(AgentEvent(
                    type="session_init", agent_name=agent.name,
                    session_id=raw.get("session_id", ""), raw=raw))

            elif etype == "thinking":
                events.append(AgentEvent(
                    type="thinking", agent_name=agent.name,
                    content=raw.get("text", ""), raw=raw))

            elif etype == "assistant":
                for item in raw.get("message", {}).get("content", []):
                    if item.get("type") == "text":
                        events.append(AgentEvent(
                            type="text", agent_name=agent.name,
                            content=item.get("text", ""), raw=raw))

            elif etype == "tool_call":
                tc = raw.get("tool_call", {})
                events.append(AgentEvent(
                    type="tool_use", agent_name=agent.name,
                    tool_name=tc.get("name", ""),
                    tool_input=tc.get("arguments", {}), raw=raw))

            elif etype == "result":
                events.append(AgentEvent(
                    type="done", agent_name=agent.name,
                    content=raw.get("result", ""),
                    duration_ms=raw.get("duration_ms", 0),
                    usage=raw.get("usage", {}),
                    is_error=raw.get("is_error", False),
                    raw=raw))

        await process.wait()
        return events

    async def close(self):
        """No long-lived processes to close — each send() is a fresh spawn."""
        pass


def create_runtime(config: Config | None = None) -> RuntimeManager:
    if config is None:
        from engine.config import load_config
        config = load_config()
    return RuntimeManager(config)

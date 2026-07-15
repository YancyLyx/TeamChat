"""
Agent Runner — CLI driver layer.

Wraps asyncio.subprocess calls to Claude Code, Codex CLI, and Cursor.
Provides a unified interface: task in → structured result out.

Handles:
  - Timeouts (agent hung detection)
  - Process lifecycle (start, monitor, kill)
  - Output parsing (JSON where available, text fallback)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from engine.config import AgentIdentity, Config
from engine.codex_events import parse_codex_jsonl_output

logger = logging.getLogger(__name__)


def extract_cli_session_id(raw_output: str) -> str:
    """Parse the first CLI session/thread ID from JSONL stdout."""
    for line in raw_output.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            evt = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(evt, dict):
            continue
        sid = evt.get("session_id") or evt.get("thread_id")
        if isinstance(sid, str) and len(sid) > 8:
            return sid
        if evt.get("type") in ("system", "session_init", "thread.started"):
            tid = evt.get("thread_id") or evt.get("id")
            if isinstance(tid, str) and len(tid) > 8:
                return tid
    return ""


def parse_cursor_jsonl_output(raw_output: str) -> str:
    """Extract assistant-visible text from Cursor stream-json stdout."""
    text_parts: list[str] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        etype = raw.get("type", "")
        if etype == "assistant":
            message = raw.get("message") or {}
            for item in message.get("content") or []:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    if text:
                        text_parts.append(text)
        elif etype == "result":
            result = raw.get("result")
            if isinstance(result, str) and result:
                text_parts.append(result)
    cleaned = "\n".join(text_parts).strip()
    return cleaned

# ---- Data types ----


@dataclass
class AgentTask:
    """Input: a task to send to an agent."""
    prompt: str
    context: str = ""
    timeout_seconds: int = 300

    def full_prompt(self) -> str:
        if self.context:
            return f"{self.context}\n\n---\n\n{self.prompt}"
        return self.prompt


@dataclass
class AgentResult:
    """Output: result from an agent invocation."""
    agent_name: str
    task_prompt: str
    output: str
    exit_code: int
    duration_ms: int
    token_usage: dict = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    cli_session_id: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def summary(self) -> str:
        """First meaningful line of output, for display."""
        lines = [l for l in self.output.strip().split("\n") if l.strip()]
        return lines[0][:120] if lines else "(empty output)"


@dataclass
class RunnerStats:
    """Aggregated stats for one agent."""
    agent_name: str
    total_calls: int = 0
    total_success: int = 0
    total_duration_ms: int = 0

    @property
    def success_rate(self) -> float:
        return self.total_success / self.total_calls if self.total_calls > 0 else 0.0


# ---- Runner ----


class AgentRunner:
    """Manages CLI calls to AI agents via asyncio.subprocess."""

    def __init__(self, config: Config):
        self.config = config
        self.stats: dict[str, RunnerStats] = {}
        self._sessions: dict[str, bool] = {}  # agent_name -> has_active_session

    def _get_stats(self, name: str) -> RunnerStats:
        if name not in self.stats:
            self.stats[name] = RunnerStats(agent_name=name)
        return self.stats[name]

    def _has_session(self, agent: AgentIdentity) -> bool:
        return self._sessions.get(agent.name, False)

    async def run_with_context(self, agent: AgentIdentity, task: AgentTask,
                               working_dir: Path | None = None) -> AgentResult:
        """
        Run a task with session context. First call is normal, subsequent calls
        use --continue / --resume to maintain conversation history.
        """
        if self._has_session(agent):
            result = await self._run(agent, task, working_dir, use_continue=True)
        else:
            result = await self._run(agent, task, working_dir, use_continue=False)
        # Mark session as active — even if it failed, try --continue next time
        self._sessions[agent.name] = True
        return result

    async def run(self, agent: AgentIdentity, task: AgentTask,
                  working_dir: Path | None = None) -> AgentResult:
        """Execute a one-shot task (no session context)."""
        return await self._run(agent, task, working_dir, use_continue=False)

    async def reset_session(self, agent: AgentIdentity):
        """Forget session context for an agent (next call starts fresh)."""
        self._sessions.pop(agent.name, None)

    async def _run(self, agent: AgentIdentity, task: AgentTask,
                   working_dir: Path | None = None,
                   use_continue: bool = False,
                   session_id: str | None = None) -> AgentResult:
        """
        Execute a task on a specific agent CLI.

        Args:
            agent: Which agent to invoke
            task: The prompt + context + timeout
            working_dir: Working directory for the subprocess (default: project root)
            use_continue: If True, use --continue/resume template for session context
            session_id: Explicit CLI session ID to resume (TeamChat session binding)
        """
        cmd = self.config.get_cli_command(
            agent, task.full_prompt(),
            use_continue=use_continue,
            session_id=session_id,
        )
        cwd = working_dir or self.config.project_root

        logger.info(f"🚀 {agent.name} starting | timeout={task.timeout_seconds}s")
        logger.debug(f"   cmd: {' '.join(cmd[:3])}...")

        started_at = datetime.now(timezone.utc)
        started_ms = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=task.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(f"⏰ {agent.name} timed out after {task.timeout_seconds}s")
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            return AgentResult(
                agent_name=agent.name,
                task_prompt=task.full_prompt(),
                output=f"TIMEOUT: agent did not respond within {task.timeout_seconds}s",
                exit_code=-1,
                duration_ms=task.timeout_seconds * 1000,
                started_at=started_at.isoformat(),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        duration_ms = int((time.monotonic() - started_ms) * 1000)
        finished_at = datetime.now(timezone.utc)
        raw_output = (stdout.decode("utf-8", errors="replace") if stdout else "")
        error_output = (stderr.decode("utf-8", errors="replace") if stderr else "")
        cli_session_id = extract_cli_session_id(raw_output)
        if not cli_session_id and error_output:
            cli_session_id = extract_cli_session_id(error_output)
        output = raw_output

        if error_output:
            logger.warning(f"⚠️  {agent.name} stderr: {error_output[:200]}")

        # Attempt JSON parsing for structured CLI output.
        token_usage: dict = {}
        if agent.cli == "claude":
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    # Claude CLI --output-format json wraps text in "result" field
                    if "result" in parsed and isinstance(parsed["result"], str):
                        output = parsed["result"]
                    # Fallback: Claude API content blocks
                    elif "content" in parsed:
                        content_blocks = parsed.get("content", [])
                        text_parts = []
                        for block in content_blocks:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        if text_parts:
                            output = "\n".join(text_parts)
                    # Extract token usage
                    usage = parsed.get("usage", {})
                    if usage:
                        token_usage = {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                        }
            except (json.JSONDecodeError, TypeError):
                pass  # Not JSON, keep raw output
        elif agent.cli == "codex":
            clean_output, usage, saw_json_event = parse_codex_jsonl_output(output)
            if saw_json_event:
                output = clean_output
                token_usage = usage
        elif agent.cli == "cursor":
            cleaned = parse_cursor_jsonl_output(output)
            if cleaned:
                output = cleaned

        result = AgentResult(
            agent_name=agent.name,
            task_prompt=task.full_prompt(),
            output=output.strip() or error_output.strip(),
            exit_code=process.returncode or 0,
            duration_ms=duration_ms,
            token_usage=token_usage,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            cli_session_id=cli_session_id,
        )

        # Update stats
        stats = self._get_stats(agent.name)
        stats.total_calls += 1
        stats.total_duration_ms += duration_ms
        if result.success:
            stats.total_success += 1

        status = "✅" if result.success else "❌"
        logger.info(
            f"{status} {agent.name} | {duration_ms}ms | "
            f"exit={result.exit_code} | {len(result.output)} chars"
        )

        return result

    async def run_streaming(self, agent: AgentIdentity, task: AgentTask,
                            working_dir: Path | None = None) -> AsyncIterator[str]:
        """Execute a task, yielding output lines as they arrive."""
        cmd = self.config.get_cli_command(agent, task.full_prompt())
        cwd = working_dir or self.config.project_root

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        if process.stdout:
            async for line in process.stdout:
                yield line.decode("utf-8", errors="replace").rstrip()

        await process.wait()

    def get_stats(self) -> dict[str, RunnerStats]:
        """Return current stats for all agents."""
        return dict(self.stats)

    def report(self) -> str:
        """Human-readable stats report."""
        lines = ["Agent Runner Stats:", "-" * 40]
        for name, stats in self.stats.items():
            avg_ms = stats.total_duration_ms / stats.total_calls if stats.total_calls else 0
            lines.append(
                f"  {name}: {stats.total_calls} calls, "
                f"{stats.total_success} success ({stats.success_rate:.0%}), "
                f"avg {avg_ms:.0f}ms"
            )
        if not self.stats:
            lines.append("  (no calls yet)")
        return "\n".join(lines)


# ---- Convenience ----


def create_runner(config: Config | None = None) -> AgentRunner:
    """Factory: create an AgentRunner with default config."""
    if config is None:
        from engine.config import load_config
        config = load_config()
    return AgentRunner(config)

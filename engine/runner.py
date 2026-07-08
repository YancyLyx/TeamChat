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

logger = logging.getLogger(__name__)

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
        for agent in (AgentIdentity for _ in []):  # placeholder
            pass

    def _get_stats(self, name: str) -> RunnerStats:
        if name not in self.stats:
            self.stats[name] = RunnerStats(agent_name=name)
        return self.stats[name]

    async def run(self, agent: AgentIdentity, task: AgentTask,
                  working_dir: Path | None = None) -> AgentResult:
        """
        Execute a task on a specific agent CLI.

        Args:
            agent: Which agent to invoke (cici/coco/soso identity)
            task: The prompt + context + timeout
            working_dir: Working directory for the subprocess (default: project root)

        Returns:
            AgentResult with output, timing, and status
        """
        cmd = self.config.get_cli_command(agent, task.full_prompt())
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
        output = (stdout.decode("utf-8", errors="replace") if stdout else "")
        error_output = (stderr.decode("utf-8", errors="replace") if stderr else "")

        if error_output:
            logger.warning(f"⚠️  {agent.name} stderr: {error_output[:200]}")

        # Attempt JSON parsing for structured output (Claude --output-format json)
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

        result = AgentResult(
            agent_name=agent.name,
            task_prompt=task.full_prompt(),
            output=output.strip() or error_output.strip(),
            exit_code=process.returncode or 0,
            duration_ms=duration_ms,
            token_usage=token_usage,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
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

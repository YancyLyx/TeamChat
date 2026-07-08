"""
Persistent Agent Worker — long-running CLI subprocess with conversation history.

Each worker wraps one agent CLI and keeps it alive across multiple messages.
Uses asyncio.subprocess with stdin/stdout pipes for communication.

Protocol:
  - Send: write prompt + delimiter to stdin
  - Receive: read stdout until delimiter, parse structured sections
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine.config import AgentIdentity, Config

logger = logging.getLogger(__name__)

# Delimiter to mark end of agent response
END_MARKER = "\n---TEAMCHAT_END---\n"

# Regex patterns for structured output sections
THINKING_RE = re.compile(r"<THINKING>(.*?)</THINKING>", re.DOTALL)
TOOL_CALLS_RE = re.compile(r"<TOOL_CALLS>(.*?)</TOOL_CALLS>", re.DOTALL)
RESULT_RE = re.compile(r"<RESULT>(.*?)</RESULT>", re.DOTALL)


@dataclass
class ParsedOutput:
    """Structured output from an agent response."""

    raw: str
    thinking: list[str] = field(default_factory=list)   # folded by default
    tool_calls: list[str] = field(default_factory=list)  # folded by default
    result: str = ""  # the actual reply text

    @property
    def display_text(self) -> str:
        """Text to show in the chat bubble."""
        return self.result or self.raw[:500]

    @property
    def has_folded_content(self) -> bool:
        return bool(self.thinking) or bool(self.tool_calls)


def parse_output(raw: str) -> ParsedOutput:
    """Parse agent CLI output into structured sections."""
    thinking = [t.strip() for t in THINKING_RE.findall(raw)]
    tool_calls = [t.strip() for t in TOOL_CALLS_RE.findall(raw)]
    results = [r.strip() for r in RESULT_RE.findall(raw)]

    # Remove structured sections from raw to get clean output
    clean = raw
    clean = THINKING_RE.sub("", clean)
    clean = TOOL_CALLS_RE.sub("", clean)
    clean = RESULT_RE.sub("", clean)
    clean = clean.strip()

    result_text = results[0] if results else clean

    return ParsedOutput(
        raw=raw,
        thinking=thinking,
        tool_calls=tool_calls,
        result=result_text,
    )


class PersistentAgentWorker:
    """Long-running wrapper around one agent CLI process."""

    def __init__(self, agent: AgentIdentity, config: Config):
        self.agent = agent
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self.history: list[dict] = []  # conversation context
        self._started_at: str = ""
        self._message_count: int = 0
        self._alive: bool = False

    # ---- Lifecycle ----

    async def start(self) -> bool:
        """Launch the CLI process. Returns True if successful."""
        cmd = self.config.get_cli_command(self.agent, "")
        # For persistent mode, we don't pass prompt as arg.
        # Instead we start the CLI in stdin mode and pipe prompts.

        # Use the first parts of CLI template (binary + flags) without prompt
        template = self.config.get_cli_command(self.agent, "{prompt}")
        binary_and_flags = [p for p in template if p != "{prompt}"]

        logger.info(f"Starting {self.agent.name} worker: {' '.join(binary_and_flags[:3])}...")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *binary_and_flags,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.config.project_root),
            )
            self._alive = True
            self._started_at = datetime.now(timezone.utc).isoformat()

            # Send initial role-setting prompt
            init_prompt = self._build_init_prompt()
            await self._send_raw(init_prompt)
            # Read initial response (discard — just warm-up)
            await asyncio.sleep(1)

            logger.info(f"{self.agent.name} worker ready")
            return True
        except Exception as e:
            logger.error(f"Failed to start {self.agent.name}: {e}")
            self._alive = False
            return False

    async def shutdown(self, timeout: float = 5.0):
        """Gracefully stop the worker process."""
        if not self.process:
            return
        self._alive = False
        try:
            if self.process.stdin:
                self.process.stdin.write_eof()
                await self.process.stdin.drain()
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"{self.agent.name} worker didn't exit gracefully, killing")
            try:
                self.process.kill()
                await self.process.wait()
            except Exception:
                pass
        logger.info(f"{self.agent.name} worker shut down")

    # ---- Messaging ----

    async def send(self, message: str) -> ParsedOutput:
        """
        Send a message and wait for the structured response.

        Maintains conversation history so the agent has context.
        """
        if not self._alive or not self.process:
            raise RuntimeError(f"{self.agent.name} worker is not running")

        self._message_count += 1

        # Build prompt with history context
        prompt = self._build_prompt(message)

        # Send to process
        await self._send_raw(prompt)

        # Read response
        raw_output = await self._read_response()

        # Update history
        self.history.append({"role": "user", "content": message})

        # Parse structured output
        parsed = parse_output(raw_output)

        self.history.append({"role": "assistant", "content": parsed.result or parsed.raw[:500]})

        # Trim history if too long
        if len(self.history) > 20:
            self.history = self.history[-10:]

        return parsed

    # ---- Internal ----

    def _build_init_prompt(self) -> str:
        """Build the initial prompt that sets up the agent's role."""
        return (
            f"你是 {self.agent.name}，TeamChat 项目的 {self.agent.role}。\n"
            f"你的队友: cici咪(架构师), coco咪(开发), soso咪(QA)。\n"
            f"人类会通过聊天室向你发送消息。请用简洁的中文回复。\n"
            f"如果是打招呼，回复一句简短的自我介绍。\n"
            f"回复完毕后，在最后一行输出 ---TEAMCHAT_END---"
        )

    def _build_prompt(self, message: str) -> str:
        """Build a prompt with conversation history for context."""
        parts = []
        if self.history:
            parts.append("以下是之前的对话记录，用于上下文:\n")
            for h in self.history[-6:]:  # last 3 exchanges
                role = "人类" if h["role"] == "user" else self.agent.name
                parts.append(f"{role}: {h['content'][:200]}")
            parts.append("\n---\n")

        parts.append(f"人类的新消息: {message}\n")
        parts.append(
            "\n请回复。如果需要思考，用 <THINKING>...</THINKING> 包裹。"
            "如果使用了工具，用 <TOOL_CALLS>...</TOOL_CALLS> 包裹。"
            "你的最终回复用 <RESULT>...</RESULT> 包裹。"
            "回复完毕后输出 ---TEAMCHAT_END---"
        )
        return "\n".join(parts)

    async def _send_raw(self, text: str):
        """Write text to the process stdin."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Worker stdin not available")
        self.process.stdin.write((text + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def _read_response(self, timeout: float = 120.0) -> str:
        """Read from process stdout until END_MARKER or timeout."""
        if not self.process or not self.process.stdout:
            raise RuntimeError("Worker stdout not available")

        buffer = ""
        try:
            while True:
                line_bytes = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=timeout,
                )
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                buffer += line
                if END_MARKER.strip() in line:
                    break
        except asyncio.TimeoutError:
            logger.warning(f"{self.agent.name} response timeout after {timeout}s")

        # Try to parse JSON output from Claude
        clean = buffer.replace(END_MARKER.strip(), "").strip()
        if self.agent.cli == "claude":
            try:
                parsed = json.loads(clean)
                if isinstance(parsed, dict) and "result" in parsed:
                    return parsed["result"]
            except (json.JSONDecodeError, TypeError):
                pass

        return clean


class WorkerPool:
    """Manages all persistent agent workers."""

    def __init__(self, config: Config):
        self.config = config
        self.workers: dict[str, PersistentAgentWorker] = {}

    async def startup(self):
        """Launch workers for all agents."""
        from engine.config import ALL_AGENTS
        for agent in ALL_AGENTS:
            worker = PersistentAgentWorker(agent, self.config)
            success = await worker.start()
            if success:
                self.workers[agent.name] = worker
            else:
                logger.error(f"Failed to start {agent.name} worker")
        logger.info(f"WorkerPool: {len(self.workers)}/{len(ALL_AGENTS)} workers started")

    async def shutdown(self):
        """Shut down all workers."""
        for name, worker in self.workers.items():
            await worker.shutdown()
        self.workers.clear()
        logger.info("WorkerPool: all workers shut down")

    async def send(self, agent: AgentIdentity, message: str) -> ParsedOutput | None:
        """Send a message to a specific agent's worker."""
        worker = self.workers.get(agent.name)
        if worker is None:
            logger.error(f"No worker for {agent.name}")
            return None
        return await worker.send(message)

    async def broadcast(self, message: str, agents: list[AgentIdentity] | None = None
                        ) -> dict[str, ParsedOutput | None]:
        """Send the same message to multiple agents. Returns name -> result map."""
        targets = agents or list(self.workers.values())  # type: ignore
        results = {}
        for agent in (a if isinstance(a, AgentIdentity) else a.agent for a in targets):  # type: ignore
            results[agent.name] = await self.send(agent, message)
        return results

    def is_ready(self, agent: AgentIdentity) -> bool:
        """Check if a specific agent's worker is alive."""
        worker = self.workers.get(agent.name)
        return worker is not None and worker._alive

    def all_ready(self) -> bool:
        """Check if all workers are alive."""
        from engine.config import ALL_AGENTS
        return all(self.is_ready(a) for a in ALL_AGENTS)

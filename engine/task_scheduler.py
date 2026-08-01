"""
Task Scheduler — background loop that dispatches unblocked tasks to agents.

ADR-003 中枢模式: Engine 只派发不决策.
  - Polls task_table.unblocked_tasks() (pending tasks whose deps are done).
  - For each: mark running → spawn agent → log → push result to ResultRelay.
  - Does NOT mark done/failed — that is cici咪's job after reviewing (ADR-003 §1.1).
  - Does NOT write prompts — cici咪 writes them when creating tasks.

The scheduler runs as a FastAPI lifespan background task (api/main.py).
"""

import asyncio
import logging
from datetime import datetime, timezone

from engine.config import ALL_AGENTS, AgentIdentity
from engine.dispatch import spawn_with_session
from engine.router import Router
from engine.runner import AgentRunner, AgentResult, AgentTask
from engine.session_store import SessionStore
from engine.store import AgentCallStore
from engine.task_table import Task, TaskTable

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0  # seconds
DEFAULT_TIMEOUT = 300
MAX_RETRIES = 3  # transient failure retries (ADR-003 C6)
RETRY_DELAYS = (1, 2, 4)  # exponential backoff in seconds


class TaskScheduler:
    """Background poller that dispatches unblocked tasks to agents."""

    def __init__(
        self,
        runner: AgentRunner,
        router: Router,
        task_table: TaskTable,
        session_store: SessionStore,
        store: AgentCallStore,
        result_relay,
        ws_manager=None,
    ):
        self.runner = runner
        self.router = router
        self.task_table = task_table
        self.session_store = session_store
        self.store = store
        self.result_relay = result_relay
        self.ws_manager = ws_manager
        self._running = False

    def _find_agent(self, name: str) -> AgentIdentity | None:
        for a in ALL_AGENTS:
            if a.name == name:
                return a
        return None

    async def _broadcast(self, message: dict):
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(message)
            except Exception as exc:
                logger.warning(f"broadcast failed: {exc}")

    async def _spawn_with_retry(self, task: Task, agent: AgentIdentity,
                                agent_task: AgentTask) -> tuple[AgentResult, int]:
        """Spawn agent with transient-failure retries (ADR-003 C6).

        Deterministic retry: exit_code != 0 → retry up to MAX_RETRIES with backoff.
        The retry decision (retry/reassign/abandon) after exhaustion is cici咪's —
        the final failed result still goes through ResultRelay.
        """
        retries = 0
        while True:
            try:
                result = await spawn_with_session(
                    agent, agent_task, self.runner, self.session_store,
                    task.teamchat_session_id,
                )
            except Exception as exc:
                logger.error(f"❌ Task #{task.id} spawn error: {exc}")
                result = AgentResult(
                    agent_name=agent.name,
                    task_prompt=agent_task.full_prompt(),
                    output=f"DISPATCH ERROR: {exc}",
                    exit_code=1,
                    duration_ms=0,
                    started_at=datetime.now(timezone.utc).isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
            if result.success or retries >= MAX_RETRIES:
                return result, retries
            # Audit every retried attempt (soso咪 review 备注 on PR #95) —
            # final attempt is logged by _dispatch with task_type="scheduled_task".
            self.store.log(
                agent_name=agent.name, prompt=agent_task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                task_type="scheduled_task_retry",
                teamchat_session_id=task.teamchat_session_id,
                started_at=result.started_at, finished_at=result.finished_at,
            )
            retries += 1
            delay = RETRY_DELAYS[min(retries, len(RETRY_DELAYS)) - 1]
            logger.warning(
                f"⏳ Task #{task.id} failed ({retries}/{MAX_RETRIES}), "
                f"retry in {delay}s"
            )
            await asyncio.sleep(delay)

    async def _dispatch(self, task: Task):
        """Spawn the agent for one task, then hand the result to ResultRelay."""
        agent = self._find_agent(task.agent)
        if not agent:
            logger.error(f"⚠️ Task #{task.id}: unknown agent '{task.agent}'")
            self.task_table.update(
                task.id, status="failed",
                output_summary=f"Unknown agent: {task.agent}",
            )
            return

        now = datetime.now(timezone.utc).isoformat()
        self.task_table.update(task.id, status="running")
        self.router.mark_busy(agent)
        logger.info(f"🚀 Dispatching #{task.id} '{task.title}' → {agent.name}")
        await self._broadcast({
            "type": "task_started",
            "data": {"agent": agent.name, "prompt": task.title[:200],
                     "session_id": task.id, "timestamp": now},
        })
        # Track existing tasks so we can fix the session of any tasks cici咪
        # creates while executing this one (MCP defaults to session 1).
        tasks_before = {t.id for t in self.task_table.list_tasks()}

        result: AgentResult | None = None
        retries = 0
        try:
            agent_task = AgentTask(
                prompt=task.description or task.title,
                timeout_seconds=DEFAULT_TIMEOUT,
            )
            result, retries = await self._spawn_with_retry(task, agent, agent_task)
        finally:
            self.router.mark_free(agent)

        # Log the call (agent_calls) — records all activity (ADR-003 §10.4)
        self.store.log(
            agent_name=agent.name, prompt=task.description or task.title,
            output=result.output, exit_code=result.exit_code,
            duration_ms=result.duration_ms, token_usage=result.token_usage,
            task_type="scheduled_task",
            teamchat_session_id=task.teamchat_session_id,
            started_at=result.started_at, finished_at=result.finished_at,
        )

        finish_now = datetime.now(timezone.utc).isoformat()
        await self._broadcast({
            "type": "task_complete",
            "data": {"agent": agent.name, "session_id": task.id,
                     "success": result.success, "duration_ms": result.duration_ms,
                     "output_preview": result.output[:200], "timestamp": finish_now},
        })
        await self._broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": agent.name,
                     "content": result.output[:500], "timestamp": finish_now},
        })

        # cici咪 executing this task (e.g. a queued analysis) may have created
        # new tasks via MCP (session defaults to 1) — fix them to this session.
        if task.agent == "cici咪":
            from engine.task_planner import fix_new_task_sessions
            fixed = fix_new_task_sessions(
                self.task_table, tasks_before, task.teamchat_session_id,
            )
            if fixed:
                logger.info(f"🔧 Fixed {fixed} cici咪-created task(s) session")

        # Hand result to cici咪 for review — Engine does NOT mark done/failed.
        await self.result_relay.relay(task, result, retries=retries)

    async def run(self):
        """Main poll loop. Dispatch unblocked tasks whose agent is free."""
        self._running = True
        logger.info("🚀 Task Scheduler started")
        while self._running:
            try:
                unblocked = self.task_table.unblocked_tasks()
                for task in unblocked:
                    agent = self._find_agent(task.agent)
                    # Only dispatch if the target agent is free (one task per agent at a time)
                    if agent and not self.router.is_busy(agent):
                        await self._dispatch(task)
            except Exception as exc:
                logger.error(f"Scheduler loop error: {exc}")
            await asyncio.sleep(POLL_INTERVAL)

    def stop(self):
        self._running = False
        logger.info("🛑 Task Scheduler stopped")

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

from engine.config import AGENT_CICI, ALL_AGENTS, AgentIdentity
from engine.dispatch import spawn_with_session
from engine.router import Router
from engine.runner import AgentRunner, AgentResult, AgentTask
from engine.session_store import SessionStore
from engine.store import AgentCallStore
from engine.task_table import Task, TaskTable

logger = logging.getLogger(__name__)

POLL_INTERVAL = 0.5  # seconds（#97 实时性：watchdog 广播延迟 ≤0.5s）
DEFAULT_TIMEOUT = 300
MAX_RETRIES = 3  # transient failure retries (ADR-003 C6)
RETRY_DELAYS = (1, 2, 4)  # exponential backoff in seconds
MIN_PROMPT_LENGTH = 3  # 防测试污染：description ≤2 字符（如 "a"/"d"）不派发；中文短 prompt（"实现按钮"=4）不受影响


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
        # Diff-based WS watchdog: snapshot of task rows from the last poll,
        # used to broadcast task_table_updated for ANY change — including
        # cross-process writes (MCP server runs in a separate stdio process
        # sharing the SQLite DB and cannot broadcast itself).
        self._last_task_snapshot: dict[int, dict] | None = None

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
                # 记录最终失败原因（Phase 4.5 自愈：cici咪 决策需要知道为什么失败）
                if not result.success:
                    self.task_table.update(
                        task.id, retry_count=retries, last_error=result.output[:300],
                    )
                return result, retries
            # Audit every retried attempt (soso咪 review 备注 on PR #95) —
            # final attempt is logged by _dispatch with task_type="scheduled_task".
            self.store.log(
                agent_name=agent.name, prompt=agent_task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                tool_calls=result.tool_calls,
                task_type="scheduled_task_retry",
                teamchat_session_id=task.teamchat_session_id,
                started_at=result.started_at, finished_at=result.finished_at,
            )
            # 记录重试状态到任务（Phase 4.5）
            self.task_table.update(
                task.id, retry_count=retries + 1, last_error=result.output[:300],
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

        # 防异常任务：description ≤2 字符（如测试垃圾任务 "a"/"d"）不派发
        # （soso咪 测试污染 DB 事件后加的防护，避免 agent 收到无意义 prompt；
        #   中文短 prompt 如"实现按钮"=4 字符不受影响）
        prompt_text = (task.description or "").strip()
        if len(prompt_text) < MIN_PROMPT_LENGTH:
            logger.warning(
                f"⚠️ Task #{task.id} description 过短 ({len(prompt_text)} 字符)，"
                f"疑似测试污染，不派发 → abandoned"
            )
            self.task_table.update(
                task.id, status="abandoned",
                output_summary="Description too short — possible test pollution, not dispatched",
            )
            return

        now = datetime.now(timezone.utc).isoformat()
        self.task_table.update(task.id, status="running")
        # #97 实时性：状态变更立即广播（不等 watchdog 轮询对比）
        await self._broadcast({
            "type": "task_table_updated",
            "data": (self.task_table.get(task.id) or task).to_dict(),
        })
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
            tool_calls=result.tool_calls,
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
                     "content": result.output, "timestamp": finish_now},
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

        # #97: cici咪 任务不再自动收尾（exit_code 收尾无独立验证，假完成漏洞来源）。
        # 统一走 relay——cici咪 的结果也会排队进审核（自我编排模式，引导创建
        # soso咪 审查节点），由她基于审查证据验收（ADR-004 #97 v4）。

        # Hand result to cici咪 for review — Engine does NOT mark done/failed.
        # Refresh task first so retry_count/last_error written during retries
        # are visible in the review prompt (soso咪 review Bug 1 on Phase 4.5).
        fresh_task = self.task_table.get(task.id) or task
        await self.result_relay.relay(fresh_task, result, retries=retries)

    async def run(self):
        """Main poll loop. Dispatch unblocked tasks whose agent is free.

        每轮并发派发可派发的任务（ADR-006 #96）：不同 agent 的独立任务
        并行执行。同 agent 串行由 busy 标记保证（见 _collect_dispatchable）。
        """
        self._running = True
        logger.info("🚀 Task Scheduler started")
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error(f"Scheduler loop error: {exc}")
            await self._broadcast_task_changes()
            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_once(self):
        """One poll cycle: collect dispatchable tasks and dispatch them in parallel."""
        dispatchable = self._collect_dispatchable()
        if not dispatchable:
            return
        logger.info(f"🚀 Dispatching {len(dispatchable)} task(s) in parallel")
        results = await asyncio.gather(
            *(self._dispatch(t) for t in dispatchable),
            return_exceptions=True,
        )
        for task, res in zip(dispatchable, results):
            if isinstance(res, Exception):
                # 单个任务 spawn 失败不影响并行同伴和后续轮询（ADR-006 #96）
                logger.error(f"Task #{task.id} dispatch failed: {res}")

    def _collect_dispatchable(self) -> list:
        """Pick up to one unblocked task per free agent per poll.

        按 agent 去重（每轮每 agent 最多 1 个）——同 agent 的两个任务
        不会在同一轮被选中，第二个留到下一轮等 busy 释放，天然保持
        "同 agent 串行"，busy 标记管理零改动、无竞态（ADR-006 #96）。
        """
        unblocked = self.task_table.unblocked_tasks()
        picked: list = []
        picked_agents: set[str] = set()
        for task in unblocked:
            agent = self._find_agent(task.agent)
            # Only dispatch if the target agent is free (one task per agent at a time)
            if not agent or self.router.is_busy(agent):
                continue
            if agent.name in picked_agents:
                continue
            # 延迟派发: cici咪 busy（分析/审核中）期间创建的任务，
            # 等 cici咪 空闲后再派发 — 避免 task_started 先于
            # cici咪 的回复显示（用户报告的顺序问题）。
            if self._should_defer(task):
                continue
            picked.append(task)
            picked_agents.add(agent.name)
        return picked

    def _should_defer(self, task: Task) -> bool:
        """Defer dispatch if the task was created while cici咪 is busy
        (analyzing/reviewing) — its creation is part of cici咪's turn, so the
        dispatch should wait until cici咪 finishes and the user sees the reply."""
        if task.agent == "cici咪":
            return False  # cici咪 自己的任务，交给同一 busy 状态判断
        if not self.router.is_busy(AGENT_CICI):
            return False
        since = self.router.busy_since(AGENT_CICI)
        if not since or not task.created_at:
            return False
        # ISO timestamps compare lexicographically when same format
        return task.created_at > since

    async def _broadcast_task_changes(self):
        """Broadcast task_table_updated for any task row changed since the
        last poll. Covers in-process writes (dispatch running/retry) AND
        cross-process MCP create/update_task (separate stdio process) —
        the Tasks board stays live without touching MCP's process boundary."""
        tasks = self.task_table.list_tasks()
        snapshot = {t.id: t.to_dict() for t in tasks}
        if self._last_task_snapshot is None:
            self._last_task_snapshot = snapshot  # first pass: baseline only
            return
        for task_id, current in snapshot.items():
            previous = self._last_task_snapshot.get(task_id)
            if previous is None or previous != current:
                await self._broadcast({
                    "type": "task_table_updated",
                    "data": current,
                })
        self._last_task_snapshot = snapshot

    def stop(self):
        self._running = False
        logger.info("🛑 Task Scheduler stopped")

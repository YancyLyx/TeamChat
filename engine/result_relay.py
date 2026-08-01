"""
Result Relay — pushes agent results back to cici咪 for review.

ADR-003 中枢模式 (§1.1):
  agent 完成 → Engine 推结果给 cici咪 → cici咪 审核 → cici咪 update_task.
  Engine 不判断 done/fail, 不自动派发下一个.

排队 (ADR-003 §3.6): cici咪 busy 时, 结果暂存; cici咪 idle 时批量 spawn 审核.
这解决了人肉路由中的"等待"问题 — 不打断 cici咪 当前工作.

cici咪 审核 = spawn cici咪(--resume) + 结果拼进 prompt (非 stdin, runner 是一次性 spawn).
审核期间 cici咪 通过 MCP 工具 update_task / create_task (Engine 不碰这些).
"""

import logging
from datetime import datetime, timezone

from engine.config import AGENT_CICI
from engine.dispatch import spawn_with_session
from engine.runner import AgentResult, AgentTask
from engine.task_table import Task

logger = logging.getLogger(__name__)

REVIEW_TIMEOUT = 180
MAX_OUTPUT_IN_PROMPT = 2000


class ResultRelay:
    """Routes agent results to cici咪 for review, with queuing when cici咪 is busy."""

    def __init__(self, runner, router, session_store, task_table, ws_manager=None):
        self.runner = runner
        self.router = router
        self.session_store = session_store
        self.task_table = task_table
        self.ws_manager = ws_manager
        self._pending: list[tuple[Task, AgentResult]] = []
        self._reviewing = False

    async def relay(self, task: Task, result: AgentResult):
        """Push a task result to cici咪 for review (or queue if cici咪 is busy)."""
        # cici咪's own results are not reviewed by itself; but after cici咪 finishes,
        # there may be queued results to drain.
        if task.agent == "cici咪":
            await self._drain_if_idle()
            return

        self._pending.append((task, result))
        logger.info(
            f"📨 Result #{task.id} ({task.agent}) pending review, "
            f"queue={len(self._pending)}"
        )
        await self._drain_if_idle()

    async def _drain_if_idle(self):
        """Review all pending results in one batch, if cici咪 is free."""
        while True:
            if self._reviewing or not self._pending or self.router.is_busy(AGENT_CICI):
                if self._pending and self.router.is_busy(AGENT_CICI):
                    logger.info(f"⏳ cici咪 busy, {len(self._pending)} result(s) queued")
                return
            batch = self._pending[:]
            self._pending.clear()
            self._reviewing = True
            self.router.mark_busy(AGENT_CICI)
            try:
                await self._spawn_cici_review(batch)
            except Exception as exc:
                logger.error(f"❌ cici咪 review spawn failed: {exc}")
            finally:
                self.router.mark_free(AGENT_CICI)
                self._reviewing = False
            # loop: if more results arrived during review, drain again

    async def _spawn_cici_review(self, batch: list[tuple[Task, AgentResult]]):
        """Spawn cici咪(--resume) with all batched results to review."""
        prompt = self._build_review_prompt(batch)
        now = datetime.now(timezone.utc).isoformat()
        await self._broadcast({
            "type": "system_message",
            "data": {"content": f"cici咪 正在审核 {len(batch)} 个任务结果...",
                     "timestamp": now},
        })
        logger.info(f"🔍 Spawning cici咪 to review {len(batch)} result(s)")
        review_task = AgentTask(prompt=prompt, timeout_seconds=REVIEW_TIMEOUT)
        result = await spawn_with_session(
            AGENT_CICI, review_task, self.runner, self.session_store,
            batch[0][0].teamchat_session_id,
        )
        await self._broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": "cici咪",
                     "content": result.output[:500],
                     "timestamp": datetime.now(timezone.utc).isoformat()},
        })
        logger.info(f"✅ cici咪 review done ({len(result.output)} chars)")

    def _build_review_prompt(self, batch: list[tuple[Task, AgentResult]]) -> str:
        """Construct the review prompt for cici咪 (results + MCP tool instructions)."""
        parts = [
            "你是 cici咪，TeamChat 的架构师。以下 agent 完成了任务，请逐一审核并决定下一步。",
            "",
        ]
        for task, result in batch:
            status = "成功" if result.success else "失败"
            parts.append(f"## 任务 #{task.id}「{task.title}」(指派给 {task.agent})")
            parts.append(f"执行状态: {status} (exit_code={result.exit_code})")
            parts.append("执行输出:")
            parts.append(result.output[:MAX_OUTPUT_IN_PROMPT])
            parts.append("")
        parts.extend([
            "## 请对每个任务：",
            "1. 审核输出，判断是否真正完成",
            f"2. 调用 mcp__teamchat__update_task(task_id=<id>, status=\"done\" 或 \"failed\") 标记结果",
            "3. 如果需要后续步骤（如 review、测试、合并），调用 mcp__teamchat__create_task(agent=<coco咪/soso咪/cici咪>, title=<标题>, prompt=<详细指令>, depends_on=[<已完成任务id>])",
            "",
            "可用 MCP 工具: mcp__teamchat__update_task, mcp__teamchat__create_task, mcp__teamchat__list_tasks, mcp__teamchat__get_task",
            "注意：你只做审核和任务编排，不要自己执行开发任务。",
        ])
        return "\n".join(parts)

    async def _broadcast(self, message: dict):
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(message)
            except Exception as exc:
                logger.warning(f"broadcast failed: {exc}")

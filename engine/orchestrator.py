"""
Orchestrator — result queuing, dependency dispatch, failure handling (#19).

Coordinates the lifecycle of agent tasks:
  - Queues results when cici咪 is busy
  - Checks dependencies when tasks complete
  - Handles failures with retries + escalation
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

from engine.task_table import TaskTable, Task

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


@dataclass
class QueuedResult:
    task_id: int
    agent_name: str
    output: str
    success: bool
    timestamp: str = ""


class Orchestrator:
    """Coordinates task lifecycle with queuing, deps, and retries."""

    def __init__(self, task_table: TaskTable):
        self.tt = task_table
        self._queue: list[QueuedResult] = []      # results waiting for cici咪
        self._cici_busy: bool = False              # is cici咪 currently executing?
        self._retry_count: dict[int, int] = {}     # task_id -> retry count
        self._on_unblocked: Optional[Callable[[list[Task]], Awaitable[None]]] = None

    # -- result handling --

    async def on_task_done(self, task_id: int, agent_name: str,
                           output: str, success: bool):
        """Called when an agent finishes a task."""
        now = datetime.now(timezone.utc).isoformat()

        # Update task status
        new_status = "done" if success else "failed"
        self.tt.update(task_id, status=new_status, output_summary=output[:500])

        # Handle failure with retry
        if not success:
            retries = self._retry_count.get(task_id, 0) + 1
            self._retry_count[task_id] = retries
            if retries < MAX_RETRIES:
                logger.info(f"Task #{task_id} failed ({retries}/{MAX_RETRIES}) — retrying")
                self.tt.update(task_id, status="pending")
                return  # Will be picked up by dispatch loop
            else:
                logger.warning(f"Task #{task_id} failed {MAX_RETRIES} times — escalating")

        # Queue result if cici咪 is busy
        if self._cici_busy and agent_name != "cici咪":
            self._queue.append(QueuedResult(
                task_id=task_id, agent_name=agent_name,
                output=output, success=success, timestamp=now,
            ))
            logger.debug(f"Queued result from {agent_name} (cici咪 busy)")
            return

        # If cici咪 just finished, deliver all queued results
        if agent_name == "cici咪" and success:
            await self._deliver_queue()
            return

        # Check if any tasks are now unblocked
        await self._check_dependencies(task_id)

    async def _deliver_queue(self):
        """Deliver all queued results to cici咪's stdin."""
        if not self._queue:
            return
        logger.info(f"Delivering {len(self._queue)} queued results")
        # The actual delivery is done by the chat endpoint —
        # it reads self._queue after cici咪 completes
        pass  # Handled by chat endpoint

    def drain_queue(self) -> list[QueuedResult]:
        """Get and clear all queued results."""
        results = self._queue[:]
        self._queue.clear()
        return results

    def has_queued(self) -> bool:
        return len(self._queue) > 0

    # -- dependency checking --

    async def _check_dependencies(self, completed_task_id: int):
        """Check if any blocked tasks are now unblocked."""
        unblocked = self.tt.unblocked_tasks()
        if unblocked and self._on_unblocked:
            await self._on_unblocked(unblocked)

    # -- cici咪 busy tracking --

    def set_cici_busy(self, busy: bool):
        self._cici_busy = busy

    def is_cici_busy(self) -> bool:
        return self._cici_busy

    # -- failure escalation output --

    def build_escalation_message(self, task_id: int, error: str) -> str:
        """Build chat message for escalated failure."""
        retries = self._retry_count.get(task_id, MAX_RETRIES)
        task = self.tt.get(task_id)
        title = task.title if task else f"#{task_id}"
        return (
            f"⚠️ {task.agent if task else 'agent'} 执行 #{task_id} ({title}) 失败 {retries} 次。\n"
            f"最后错误: {error[:300]}\n"
            f"选项: [重试] [交给 cici咪 分析] [放弃]"
        )

    def handle_escalation(self, task_id: int, decision: str) -> str:
        """Handle human decision on escalated failure."""
        if decision == "retry":
            self._retry_count[task_id] = 0
            self.tt.update(task_id, status="pending")
            return f"🔄 #{task_id} 重试中..."
        elif decision == "cici":
            self.tt.update(task_id, status="pending", agent="cici咪")
            return f"📤 #{task_id} 已转交给 cici咪 分析"
        else:  # abandon
            self.tt.update(task_id, status="abandoned")
            return f"🗑 #{task_id} 已放弃"

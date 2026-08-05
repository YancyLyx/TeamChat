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


class ResultRelay:
    """Routes agent results to cici咪 for review, with queuing when cici咪 is busy."""

    def __init__(self, runner, router, session_store, task_table, ws_manager=None, store=None):
        self.runner = runner
        self.router = router
        self.session_store = session_store
        self.task_table = task_table
        self.ws_manager = ws_manager
        self.store = store  # AgentCallStore（审核输出落库，刷新不丢）
        self._pending: list[tuple[Task, AgentResult, int]] = []
        self._reviewing = False

    async def relay(self, task: Task, result: AgentResult, retries: int = 0):
        """Push a task result to cici咪 for review (or queue if cici咪 is busy).

        retries: how many automatic retries the scheduler performed before this
        result — surfaced to cici咪 in the review prompt.
        """
        # #97: cici咪 任务不再跳过——排队进审核（自我编排模式，她审自己的
        # 结果时被引导创建 soso咪 审查节点；不再"只 drain 不审核"）。
        self._pending.append((task, result, retries))
        logger.info(
            f"📨 Result #{task.id} ({task.agent}) pending review, "
            f"queue={len(self._pending)}"
        )
        await self.drain_if_idle()

    async def drain_if_idle(self):
        """Review all pending results in one batch, if cici咪 is free.

        Public — called by relay() and by chat.py after cici咪 finishes a turn,
        so queued results are reviewed promptly instead of waiting for the next relay.
        """
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
                # Re-queue the batch so results are not lost (soso咪 review 备注1),
                # then stop this pass — retry on the next drain trigger
                # (avoids a hot retry loop).
                self._pending = batch + self._pending
                return
            finally:
                self.router.mark_free(AGENT_CICI)
                self._reviewing = False
            # loop: if more results arrived during review, drain again

    async def _spawn_cici_review(self, batch: list[tuple[Task, AgentResult, int]]):
        """Spawn cici咪(--resume) with all batched results to review."""
        prompt = self._build_review_prompt(batch)
        target_session = batch[0][0].teamchat_session_id
        now = datetime.now(timezone.utc).isoformat()
        await self._broadcast({
            "type": "system_message",
            "data": {"content": f"cici咪 正在审核 {len(batch)} 个任务结果...",
                     "timestamp": now},
        })
        logger.info(f"🔍 Spawning cici咪 to review {len(batch)} result(s)")
        review_task = AgentTask(prompt=prompt, timeout_seconds=REVIEW_TIMEOUT)
        # Tasks created via MCP default to teamchat_session_id=1 (MCP is stateless);
        # track what exists so we can fix the session of review-created tasks below.
        tasks_before = {t.id for t in self.task_table.list_tasks()}
        result = await spawn_with_session(
            AGENT_CICI, review_task, self.runner, self.session_store,
            target_session,
        )
        # Fix teamchat_session_id on tasks cici咪 just created during review
        # (完善点③ — same problem chat.py already fixes for the /api/chat path).
        from engine.task_planner import fix_new_task_sessions, link_parallel_branches
        fixed = fix_new_task_sessions(self.task_table, tasks_before, target_session)
        if fixed:
            logger.info(f"🔧 Fixed {fixed} review-created task(s) session → {target_session}")
        # 审核回合创建的并行任务也归属同一需求树（L2 一张拓扑图，#97）
        linked = link_parallel_branches(self.task_table, tasks_before)
        if linked:
            logger.info(f"🌳 Linked {linked} review-created branch(es) to one feature tree")
        # 落库：cici咪 审核输出持久化（否则刷新后丢失——用户报告）
        if self.store:
            self.store.log(
                agent_name="cici咪", prompt=review_task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                task_type="chat_review", tag="prod",
                teamchat_session_id=target_session,
                started_at=result.started_at, finished_at=result.finished_at,
            )
        await self._broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": "cici咪",
                     "content": result.output,
                     "timestamp": datetime.now(timezone.utc).isoformat()},
        })
        logger.info(f"✅ cici咪 review done ({len(result.output)} chars)")

    def _build_review_prompt(self, batch: list[tuple[Task, AgentResult, int]]) -> str:
        """Construct the review prompt for cici咪 (results + MCP tool instructions)."""
        parts = [
            "你是 cici咪，TeamChat 的架构师。以下 agent 完成了任务，请逐一审核并决定下一步。",
            "",
        ]
        for task, result, retries in batch:
            status = "成功" if result.success else "失败"
            parts.append(f"## 任务 #{task.id}「{task.title}」(指派给 {task.agent}，类型={task.task_type})")
            parts.append(f"执行状态: {status} (exit_code={result.exit_code})")
            if retries:
                parts.append(f"（引擎已自动重试 {retries} 次后仍{'失败' if not result.success else '成功'}）")
            if not result.success and task.last_error:
                parts.append(f"最后错误: {task.last_error[:300]}")
            parts.append("执行输出（完整）:")
            parts.append(result.output)
            parts.append("")
        parts.extend([
            "## 节点类型与下一步（#97 审查闭环，务必按类型执行）:",
            "任务类型 = task_type 字段，取值 development（开发）/ review（审查）/ fix（修复）/ verify（复审）。",
            "- development（开发节点，含你自己的任务）: 审核产出 → update_task(status=done) 标记完成",
            "  → **必须** 创建 soso咪 的审查节点: mcp__teamchat__create_task(",
            "    agent='soso咪', task_type='review', title=<审查任务标题>, prompt=<基于刚看到的",
            "    真实产出写审查点: 代码改动/AC 对照/测试要求>, depends_on=[<本任务id>],",
            "    feature_id=<本任务id 的 feature_id，同一需求树>)",
            "  → task_type 和 feature_id 参数必须显式传入（不要省略）；不要直接收尾了事——",
            "    开发产出必须经 soso咪 独立审查（#97 强制流程）",
            "- review / verify（审查/复审节点，soso咪 的验证产出）: 审核 soso咪 的审查结论",
            "  → 通过: update_task(status=done)；发现问题: 创建修复任务",
            "  → 审查节点本身是验证环节，不再为它创建审查节点",
            "- fix（修复节点）: 审核修复产出 → update_task(status=done)",
            "  → **必须** 创建 soso咪 的复审节点: create_task(agent='soso咪', task_type='verify',",
            "    title=<复审标题>, prompt=<基于修复产出 + 原问题写复审点>, depends_on=[<本任务id>],",
            "    feature_id=<本任务 id 的 feature_id>)，task_type/feature_id 必须显式传",
            "",
            "## 每个任务段落的『本任务类型』决定必做动作（按 §节点类型 执行）:",
            "  - development → done 后必须建 soso咪 review 节点",
            "  - review/verify → 验收结论，不再建审查",
            "  - fix → done 后必须建 soso咪 verify 复审节点",
            "",
            "## 请对每个任务：",
            "1. 审核输出，判断是否真正完成",
            f"2. 调用 mcp__teamchat__update_task(task_id=<id>, status=\"done\" 或 \"failed\") 标记结果",
            "3. 如果需要后续步骤（如 review、测试、合并），调用 mcp__teamchat__create_task(agent=<coco咪/soso咪/cici咪>, title=<标题>, prompt=<详细指令>, depends_on=[<已完成任务id>])",
            "",
            "## 发现问题时（重要）:",
            "- 如果审核发现实现有 bug 或需要修改 → **追加修复任务**，不要回退：",
            "  创建新任务(agent=原实现者, title=修复XX, prompt=含具体问题描述)",
            "  ⚠️ depends_on 规则：修复任务**不要依赖失败/被废弃的任务**（会永久阻塞，",
            "  例如失败任务 → 修复任务依赖它 → 永远无法派发）。",
            "  应依赖已完成的上游任务，或留空 []。",
            "- 修复任务完成后，如需要，再创建复查任务（depends_on=[修复任务id]）",
            "- 保持 DAG 无环：禁止让任务依赖自己的后代",
            "",
            "## 失败任务的三选项（ADR-003 C6，自愈机制）:",
            "注意：失败任务当前 status=running（Engine 不自动标记失败，符合铁律），请用三选项之一更新：",
            "对标记为失败的任务，从三个选项中选择并执行（一个即可）：",
            "  1. 重试 → update_task(task_id=<id>, status=\"pending\")（问题可能是暂时的）",
            "  2. 转派 → update_task(task_id=<id>, agent=<另一位咪>, status=\"pending\")（换人重做）",
            "  3. 放弃 → update_task(task_id=<id>, status=\"abandoned\")（并考虑创建替代任务）",
            "注意：转派前评估失败原因，明显是环境/网络问题先重试，实现问题可转派。",
            "",
            "可用 MCP 工具: mcp__teamchat__update_task, mcp__teamchat__create_task, mcp__teamchat__list_tasks, mcp__teamchat__get_task, mcp__teamchat__dag_summary, mcp__teamchat__task_tree",
            "注意：你只做审核和任务编排，不要自己执行开发任务。",
            "禁止执行任何 git 命令（checkout/branch/reset/switch/commit/push 等）— 共享工作区，git 操作由人工统一管理。",
            "测试必须隔离数据库：跑测试用 tmp_path 独立目录，禁止写入真实 .teamchat/teamchat.db。",
        ])
        return "\n".join(parts)

    async def _broadcast(self, message: dict):
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(message)
            except Exception as exc:
                logger.warning(f"broadcast failed: {exc}")

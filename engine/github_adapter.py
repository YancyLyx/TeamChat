"""
GitHub Adapter — bridges GitHub events into the internal task system (ADR-005 Phase 4.1).

Minimal version: GitHub Issue events → task_table tasks ("拉模式" entry point).
  - issues.opened → create a pending task for cici咪 to analyze & break down.
  - Task → GitHub reply (comment/close) is the next iteration.

The webhook endpoint lives in api/routes/github.py; this module holds the logic.
"""

import logging
from datetime import datetime, timezone

from engine.config import AGENT_CICI
from engine.task_table import TaskTable

logger = logging.getLogger(__name__)


def handle_issue_event(payload: dict, task_table: TaskTable,
                       teamchat_session_id: int = 1) -> dict | None:
    """Handle a GitHub webhook payload (X-GitHub-Event: issues).

    Returns the created Task dict, or None if the event is not actionable
    (e.g. not an issue, or already closed).
    """
    action = payload.get("action")
    issue = payload.get("issue") or {}
    number = issue.get("number")
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    state = issue.get("state")

    if action != "opened":
        logger.info(f"[GitHub] Ignoring issue action: {action}")
        return None
    if not number or not title:
        logger.warning("[GitHub] Issue payload missing number/title")
        return None
    if state and state != "open":
        logger.info(f"[GitHub] Issue #{number} state={state}, not creating task")
        return None

    # 中枢模式: new Issue → cici咪 analyzes and breaks it down (DAG).
    # The task's description is the analysis prompt; cici咪 reviews and creates
    # follow-up tasks via MCP create_task.
    description = (
        f"人类在 GitHub 开了 Issue #{number}「{title}」。\n\n"
        f"Issue 内容:\n{body[:2000]}\n\n"
        f"请分析这个需求：判断能否直接派发，还是需要拆分为多个任务（DAG）。"
        f"如需拆分，用 mcp__teamchat__create_task 创建子任务并声明依赖。"
        f"如能直接执行，用 mcp__teamchat__create_task 创建任务给对应 agent。"
        f"对应 GitHub Issue: #{number}"
    )

    task = task_table.create(
        agent=AGENT_CICI.name,
        title=f"[GitHub #{number}] {title[:80]}",
        description=description,
        teamchat_session_id=teamchat_session_id,
    )
    # Record the GitHub issue reference for later Task→Issue sync
    task_table.update(task.id, github_issue=f"#{number}")

    logger.info(f"📥 GitHub Issue #{number} → task #{task.id} (cici咪 analysis)")
    return task.to_dict()


def build_issue_comment(task_id: int, output_preview: str) -> str:
    """Build the comment posted back to a GitHub Issue when a task completes."""
    return (
        f"✅ 任务 #{task_id} 已完成。\n\n"
        f"完成摘要:\n{output_preview[:500]}"
    )

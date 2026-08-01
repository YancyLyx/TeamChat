"""
Dispatch helpers — shared spawn logic for chat endpoint and Task Scheduler.

spawn_with_session: resume a stored CLI session ID if present, else cold-start
and capture the new ID. Used by both /api/chat (human-driven) and the
TaskScheduler (background auto-dispatch).
"""

from engine.config import AgentIdentity
from engine.runner import AgentRunner, AgentTask, AgentResult
from engine.session_store import SessionStore


async def spawn_with_session(
    agent: AgentIdentity,
    task: AgentTask,
    runner: AgentRunner,
    session_store: SessionStore,
    teamchat_session_id: int,
) -> AgentResult:
    """Spawn agent: resume stored CLI session ID, or cold-start and capture it."""
    sid = session_store.get_agent_session_id(teamchat_session_id, agent.cli)
    result = await runner._run(
        agent, task, use_continue=bool(sid), session_id=sid or None,
    )
    if result.cli_session_id and not sid:
        session_store.set_agent_session_id(
            teamchat_session_id, agent.cli, result.cli_session_id,
        )
    return result

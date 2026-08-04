"""
Dispatch helpers — shared spawn logic for chat endpoint and Task Scheduler.

spawn_with_session: resume a stored CLI session ID if present, else cold-start
and capture the new ID. Used by both /api/chat (human-driven) and the
TaskScheduler (background auto-dispatch).
"""

import logging

from engine.config import AgentIdentity
from engine.runner import AgentRunner, AgentTask, AgentResult
from engine.session_store import SessionStore

logger = logging.getLogger(__name__)

# codex threads accumulate the FULL history (incl. reasoning) on every resume.
# Evidence (#26): stored thread 019fbc3b grew to ~6M input tokens and codex
# sessions began exiting after a single plan-only message (~3.5M+ threshold).
# Rotate: after this many resumed uses, drop the stored id → cold-start fresh.
CODEX_SESSION_MAX_USES = 8

# (teamchat_session_id, agent_cli) -> resumed-use count for the stored thread.
_session_uses: dict[tuple[int, str], int] = {}


async def spawn_with_session(
    agent: AgentIdentity,
    task: AgentTask,
    runner: AgentRunner,
    session_store: SessionStore,
    teamchat_session_id: int,
    on_stream=None,
) -> AgentResult:
    """Spawn agent: resume stored CLI session ID, or cold-start and capture it.

    on_stream: optional async callback (text) forwarded to runner._run for
    chat-bubble streaming (段落级流式).
    """
    sid = session_store.get_agent_session_id(teamchat_session_id, agent.cli)
    result = await runner._run(
        agent, task, use_continue=bool(sid), session_id=sid or None,
        on_stream=on_stream,
    )
    if result.cli_session_id and not sid:
        # Cold start: capture the fresh thread and restart its use count.
        session_store.set_agent_session_id(
            teamchat_session_id, agent.cli, result.cli_session_id,
        )
        _session_uses[(teamchat_session_id, agent.cli)] = 0
    elif sid:
        # Resumed: bump the count; rotate codex before its thread bloats
        # (huge threads degrade to plan-only replies — see module docstring).
        uses = _session_uses.get((teamchat_session_id, agent.cli), 0) + 1
        _session_uses[(teamchat_session_id, agent.cli)] = uses
        if agent.cli == "codex" and uses >= CODEX_SESSION_MAX_USES:
            logger.info(
                f"🔄 codex session {sid} used {uses} times — rotating, "
                f"next task cold-starts a fresh thread"
            )
            session_store.reset_agent_session(teamchat_session_id, agent.cli)
    return result

"""
Agent status endpoints.

Provides current status, busy state, and historical stats for each team member.
"""

from fastapi import APIRouter, Request

from engine.config import ALL_AGENTS
from api.schemas import AgentInfo

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
async def list_agents(request: Request):
    """List all three agents with their current status and stats."""
    router_inst = request.app.state.router
    store = request.app.state.store

    agents = []
    for agent in ALL_AGENTS:
        stats = store.stats(agent_name=agent.name)
        agents.append(AgentInfo(
            name=agent.name,
            role=agent.role,
            cli=agent.cli,
            is_busy=router_inst.is_busy(agent),
            total_tasks=stats["total_calls"],
            success_rate=stats["success_rate"],
            avg_duration_ms=stats["avg_duration_ms"],
        ))
    return agents

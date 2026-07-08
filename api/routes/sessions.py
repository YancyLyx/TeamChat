"""
Session history endpoints.

Query past agent invocations filtered by agent and paginated.
"""

from fastapi import APIRouter, Query, Request

from api.schemas import SessionRow

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionRow])
async def list_sessions(
    request: Request,
    agent: str = Query("", description="Filter by agent name (cici咪, coco咪, soso咪)"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """Query recent session history, optionally filtered by agent."""
    store = request.app.state.store
    rows = store.get_recent(limit=limit, agent_name=agent or None)
    return [
        SessionRow(
            id=r.id,
            agent_name=r.agent_name,
            task_type=r.task_type,
            prompt=r.prompt,
            output=r.output,
            exit_code=r.exit_code,
            duration_ms=r.duration_ms,
            started_at=r.started_at,
            finished_at=r.finished_at,
            created_at=r.created_at,
        )
        for r in rows
    ]

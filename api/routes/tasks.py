"""
Task submission and query endpoints.

Submit tasks to agents via POST; retrieve completed results via GET.
Broadcasts task lifecycle events over WebSocket.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from engine.config import ALL_AGENTS
from engine.runner import AgentTask
from api.schemas import TaskRequest, TaskResult, SessionRow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    agent: str
    title: str
    description: str = ""
    depends_on: list[int] = []


# ---- TaskTable endpoints (static paths before /{task_id}) ----


@router.get("/table")
async def list_table_tasks(
    request: Request, status: str | None = None, agent: str | None = None
):
    """List tasks from the task table (ADR-003 C1)."""
    tt = request.app.state.task_table
    tasks = tt.list_tasks(status=status, agent=agent)
    return [t.to_dict() for t in tasks]


@router.get("/table/stats")
async def task_table_stats(request: Request):
    """Get task completion statistics."""
    return request.app.state.task_table.stats()


@router.get("/table/{table_task_id}")
async def get_table_task(request: Request, table_task_id: int):
    tt = request.app.state.task_table
    task = tt.get(table_task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{table_task_id} not found")
    return task.to_dict()


@router.post("/table", response_model=dict)
async def create_table_task(request: Request, req: TaskCreateRequest):
    tt = request.app.state.task_table
    task = tt.create(req.agent, req.title, req.description, req.depends_on)
    return task.to_dict()


@router.patch("/table/{table_task_id}")
async def update_table_task(request: Request, table_task_id: int, body: dict):
    tt = request.app.state.task_table
    task = tt.get(table_task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{table_task_id} not found")
    tt.update(table_task_id, **body)
    return tt.get(table_task_id).to_dict()


# ---- Legacy session-based task submission ----


@router.post("", response_model=dict)
async def submit_task(request: Request, task_req: TaskRequest):
    """Submit a new task to a specific agent. Runs immediately and returns the result."""
    agent = None
    for a in ALL_AGENTS:
        if a.name == task_req.agent:
            agent = a
            break
    if agent is None:
        valid_names = [a.name for a in ALL_AGENTS]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{task_req.agent}'. Valid: {valid_names}",
        )

    runner = request.app.state.runner
    router_inst = request.app.state.router
    ws_mgr = request.app.state.ws_manager

    router_inst.mark_busy(agent)

    await ws_mgr.broadcast({
        "type": "task_started",
        "data": {
            "agent": agent.name,
            "prompt": task_req.prompt[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    try:
        task = AgentTask(prompt=task_req.prompt, context=task_req.context)
        result = await runner.run(agent, task)

        store = request.app.state.store
        session_id = store.log(
            agent_name=agent.name,
            prompt=task.full_prompt(),
            output=result.output,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            token_usage=result.token_usage,
            task_type="api_task",
            tag="prod",
            started_at=result.started_at,
            finished_at=result.finished_at,
        )

        await ws_mgr.broadcast({
            "type": "task_complete",
            "data": {
                "agent": agent.name,
                "session_id": session_id,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "output_preview": result.output[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })

        return {
            "session_id": session_id,
            "result": TaskResult(
                agent_name=result.agent_name,
                task_prompt=result.task_prompt,
                output=result.output,
                exit_code=result.exit_code,
                duration_ms=result.duration_ms,
                token_usage=result.token_usage,
                started_at=result.started_at,
                finished_at=result.finished_at,
            ).model_dump(),
        }
    finally:
        router_inst.mark_free(agent)


@router.get("/{task_id}", response_model=SessionRow)
async def get_session_task(request: Request, task_id: int):
    """Query a completed task result by session ID."""
    store = request.app.state.store
    row = store.get_by_id(task_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task with session_id={task_id} not found",
        )
    return SessionRow(
        id=row.id,
        agent_name=row.agent_name,
        task_type=row.task_type,
        prompt=row.prompt,
        output=row.output,
        exit_code=row.exit_code,
        duration_ms=row.duration_ms,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
    )

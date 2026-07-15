"""TeamChat Session CRUD API — project-level sessions, not CLI sessions."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/session-manager", tags=["sessions"])


class SessionCreate(BaseModel):
    name: str
    directory: str


class SessionUpdate(BaseModel):
    name: str | None = None
    claude_id: str | None = None
    codex_id: str | None = None
    cursor_id: str | None = None
    status: str | None = None


@router.get("")
async def list_sessions(request: Request):
    store = request.app.state.session_store
    return [s.to_dict() for s in store.list_all()]


@router.post("")
async def create_session(request: Request, body: SessionCreate):
    from pathlib import Path
    if not Path(body.directory).exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {body.directory}")
    store = request.app.state.session_store
    s = store.create(body.name, body.directory)
    return s.to_dict()


@router.get("/{session_id}")
async def get_session(request: Request, session_id: int):
    store = request.app.state.session_store
    s = store.get(session_id)
    if not s:
        raise HTTPException(status_code=404)
    return s.to_dict()


@router.patch("/{session_id}")
async def update_session(request: Request, session_id: int, body: SessionUpdate):
    store = request.app.state.session_store
    s = store.get(session_id)
    if not s:
        raise HTTPException(status_code=404)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    store.update(session_id, **updates)
    return store.get(session_id).to_dict()


@router.delete("/{session_id}")
async def delete_session(request: Request, session_id: int):
    store = request.app.state.session_store
    s = store.get(session_id)
    if not s:
        raise HTTPException(status_code=404)
    store.delete(session_id)
    return {"ok": True}

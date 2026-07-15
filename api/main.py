"""
FastAPI application entry point for TeamChat.

Provides:
  - REST API endpoints (agents, sessions, tasks, stats)
  - WebSocket real-time push (/ws)
  - Health check endpoint

Usage:
    uvicorn api.main:app --reload
"""

import logging
import asyncio
from contextlib import asynccontextmanager
import os
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import File, UploadFile
from starlette.responses import Response
import json as _stdlib_json


class UnicodeJSONResponse(JSONResponse):
    """JSONResponse that doesn't escape non-ASCII characters (emojis, Chinese, etc)."""
    def render(self, content) -> bytes:
        return _stdlib_json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

from engine.config import load_config
from engine.runner import create_runner
from engine.router import Router
from engine.store import create_store
from engine.bus import MessageBus
from engine.task_table import create_task_table
from engine.runtime import create_runtime
from engine.orchestrator import Orchestrator
from engine.session_store import create_session_store

from api.routes import agents, sessions, tasks, chat, teamchat_sessions

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for real-time event push."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        stale = []
        text = _stdlib_json.dumps(message, ensure_ascii=False)
        for conn in self.active_connections:
            try:
                await conn.send_text(text)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.disconnect(conn)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine components on startup, clean up on shutdown."""
    config = load_config()
    session_store = create_session_store(config)
    store = create_store(config)
    runner = create_runner(config)
    router_inst = Router()
    bus = MessageBus(config)
    bus.init()
    task_table = create_task_table(config)
    runtime = create_runtime(config)

    # Discover existing sessions
    runtime.discover_sessions()

    app.state.config = config
    app.state.store = store
    app.state.runner = runner
    app.state.router = router_inst
    app.state.bus = bus
    app.state.task_table = task_table
    app.state.runtime = runtime
    app.state.orchestrator = Orchestrator(task_table)
    app.state.session_store = session_store
    app.state.ws_manager = manager
    app.state.loop = asyncio.get_running_loop()

    async def on_bus_message(msg):
        await manager.broadcast({
            "type": "message",
            "data": msg.to_dict(),
        })
    bus.subscribe("all", on_bus_message)

    logger.info("TeamChat API ready")
    yield

    await runtime.close()
    task_table.close()
    session_store.close()
    store.close()
    logger.info("TeamChat API shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TeamChat API",
        version="0.1.0",
        description="Multi-AI-Agent collaboration platform API",
        lifespan=lifespan,
        default_response_class=UnicodeJSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agents.router)
    app.include_router(sessions.router)
    app.include_router(tasks.router)
    app.include_router(chat.router)
    app.include_router(teamchat_sessions.router)

    return app


app = create_app()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time event feed for agent activities and message bus."""
    await manager.connect(websocket)
    try:
        await websocket.send_text(_stdlib_json.dumps({
            "type": "connected",
            "data": {"message": "Connected to TeamChat real-time feed"},
        }, ensure_ascii=False))
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(_stdlib_json.dumps({"type": "pong", "data": {}}, ensure_ascii=False))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
   return {"status": "ok", "version": "0.1.0"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save an uploaded file to /tmp/ and return the absolute path."""
    safe_name = file.filename or "attachment.bin"
    ext = os.path.splitext(safe_name)[1] or ".png"
    filename = f"teamchat-{uuid.uuid4().hex[:12]}{ext}"
    filepath = os.path.join("/tmp", filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    return {"path": filepath, "name": safe_name, "size": len(content)}


@app.get("/api/stats")
async def stats(request: Request):
    """Get aggregated statistics for all agents."""
    from engine.config import ALL_AGENTS

    store = request.app.state.store
    by_agent = store.stats_by_agent()
    agents = {}
    for agent in ALL_AGENTS:
        agents[agent.name] = by_agent.get(
            agent.name,
            {
                "total_calls": 0,
                "total_success": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0,
            },
        )
    return {"agents": agents}


@app.get("/api/engine")
async def engine_status(request: Request):
    """Engine runtime observability for the Live Panel (ADR-003 §9)."""
    router = request.app.state.router
    orchestrator = request.app.state.orchestrator
    from engine.config import ALL_AGENTS

    active_agents = [
        {"name": a.name, "is_busy": router.is_busy(a)}
        for a in ALL_AGENTS
    ]

    queue_length = 0
    if hasattr(orchestrator, "_queue"):
        queue_length = len(orchestrator._queue)

    # Default mode: parallel. Orchestrator can toggle when cici咪 is busy.
    mode = "serial" if orchestrator.is_cici_busy() else "parallel"

    return {
        "mode": mode,
        "active_agents": active_agents,
        "queue_length": queue_length,
    }


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)

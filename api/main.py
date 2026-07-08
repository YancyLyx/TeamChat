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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware

from engine.config import load_config
from engine.runner import create_runner
from engine.router import Router
from engine.store import create_store
from engine.bus import MessageBus

from api.routes import agents, sessions, tasks

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
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.disconnect(conn)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine components on startup, clean up on shutdown."""
    config = load_config()
    store = create_store(config)
    runner = create_runner(config)
    router_inst = Router()
    bus = MessageBus(config)
    bus.init()

    app.state.config = config
    app.state.store = store
    app.state.runner = runner
    app.state.router = router_inst
    app.state.bus = bus
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

    store.close()
    logger.info("TeamChat API shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TeamChat API",
        version="0.1.0",
        description="Multi-AI-Agent collaboration platform API",
        lifespan=lifespan,
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

    return app


app = create_app()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time event feed for agent activities and message bus."""
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "Connected to TeamChat real-time feed"},
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong", "data": {}})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/stats")
async def stats(request: Request):
    """Get aggregated statistics for all agents."""
    store = request.app.state.store
    return {"agents": store.stats_by_agent()}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)

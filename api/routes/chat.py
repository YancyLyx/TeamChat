"""
Chat endpoint for the Slack-style dashboard.
"""

import re
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engine.config import ALL_AGENTS
from engine.runner import AgentTask
from engine.bus import MessageBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

MENTION_PATTERN = re.compile(r"@(cici咪|coco咪|soso咪)")


class ChatRequest(BaseModel):
    """A human message sent from the chat input."""
    content: str = Field(..., min_length=1, description="Message content with optional @mentions")


class ChatResponse(BaseModel):
    """Response after processing a chat message."""
    session_id: int | None = None
    target_agent: str | None = None
    task_prompt: str = ""
    status: str = "ok"


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    """Process a human chat message.

    Parses @mentions to determine target agent. If found, routes the
    message content as a task to that agent via the AgentRunner.
    Results are broadcast through the existing WebSocket pipeline.
    """
    content = chat_req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    mentions = MENTION_PATTERN.findall(content)
    ws_mgr = request.app.state.ws_manager

    # Broadcast the human message to the chat
    await ws_mgr.broadcast({
        "type": "chat_message",
        "data": {
            "kind": "human",
            "agent": "human",
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    if not mentions:
        # No @mention — just echo to chat, no agent routing
        await ws_mgr.broadcast({
            "type": "chat_message",
            "data": {
                "kind": "system",
                "agent": "system",
                "content": "消息已收到。使用 @cici咪 @coco咪 @soso咪 指定目标 agent。",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })
        return ChatResponse(status="broadcast", task_prompt=content)

    # Find target agent from first mention
    target_agent_name = mentions[0]
    target_agent = None
    for a in ALL_AGENTS:
        if a.name == target_agent_name:
            target_agent = a
            break

    if target_agent is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {target_agent_name}")

    # Strip @mentions to get the clean prompt
    clean_prompt = MENTION_PATTERN.sub("", content).strip()
    if not clean_prompt:
        clean_prompt = content

    router_inst = request.app.state.router
    router_inst.mark_busy(target_agent)

    # Broadcast task_started
    await ws_mgr.broadcast({
        "type": "task_started",
        "data": {
            "agent": target_agent.name,
            "prompt": clean_prompt[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    try:
        runner = request.app.state.runner
        task = AgentTask(prompt=clean_prompt)
        result = await runner.run(target_agent, task)

        store = request.app.state.store
        session_id = store.log(
            agent_name=target_agent.name,
            prompt=task.full_prompt(),
            output=result.output,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            token_usage=result.token_usage,
            task_type="chat",
            started_at=result.started_at,
            finished_at=result.finished_at,
        )

        # Broadcast task_complete
        await ws_mgr.broadcast({
            "type": "task_complete",
            "data": {
                "agent": target_agent.name,
                "session_id": session_id,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "output_preview": result.output[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })

        # Broadcast agent's reply as chat message
        await ws_mgr.broadcast({
            "type": "chat_message",
            "data": {
                "kind": "agent_reply",
                "agent": target_agent.name,
                "content": result.output[:500],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
            },
        })

        return ChatResponse(
            session_id=session_id,
            target_agent=target_agent.name,
            task_prompt=clean_prompt,
            status="completed" if result.success else "failed",
        )
    finally:
        router_inst.mark_free(target_agent)

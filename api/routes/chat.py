"""
Chat endpoint for the Slack-style dashboard.

Uses engine.message_parser for @mention extraction (no duplicated regex).
Unaddressed messages go to cici咪 for analysis per spec.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engine.config import ALL_AGENTS, AGENT_CICI
from engine.message_parser import parse_message, build_cici_analysis_prompt
from engine.runner import AgentTask

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: int | None = None
    target_agent: str | None = None
    task_prompt: str = ""
    status: str = "ok"


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    content = chat_req.content.strip()
    if not content:
        raise HTTPStatusException(status_code=400, detail="Message cannot be empty")

    parsed = parse_message(content)
    ws_mgr = request.app.state.ws_manager
    now = datetime.now(timezone.utc).isoformat()

    # Broadcast human message to chat
    await ws_mgr.broadcast({
        "type": "chat_message",
        "data": {"kind": "human", "agent": "human", "content": content, "timestamp": now},
    })

    # ---- NO @mention: cici咪 analyzes ----
    if not parsed.mentions:
        await ws_mgr.broadcast({
            "type": "system_message",
            "data": {"content": f"cici咪 analyzing: {content[:80]}...", "timestamp": now},
        })

        runner = request.app.state.runner
        store = request.app.state.store

        analysis_prompt = build_cici_analysis_prompt(content)
        result = await runner.run(AGENT_CICI, AgentTask(prompt=analysis_prompt, timeout_seconds=60))
        analysis = result.output.strip()

        if analysis.startswith("ANSWER:"):
            answer = analysis.removeprefix("ANSWER:").strip()
            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {"kind": "agent_reply", "agent": "cici咪", "content": answer, "timestamp": now},
            })
            return ChatResponse(target_agent="cici咪", task_prompt=content, status="answered")

        elif analysis.startswith("TASK:"):
            rest = analysis.removeprefix("TASK:").strip()
            parts = rest.split(":", 1)
            task_type = parts[0].strip() if parts else "architecture"
            task_desc = parts[1].strip() if len(parts) > 1 else rest

            from engine.router import Router, TaskType
            try:
                dispatch = Router().dispatch(TaskType(task_type))
            except ValueError:
                dispatch = Router().dispatch(TaskType.ARCHITECTURE)
            target = dispatch.agent

            task = AgentTask(prompt=task_desc, context=f"cici咪 assigned: {task_desc}")
            result = await runner.run(target, task)

            session_id = store.log(
                agent_name=target.name, prompt=task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                task_type="chat_task", started_at=result.started_at, finished_at=result.finished_at,
            )

            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {"kind": "agent_reply", "agent": target.name, "content": result.output[:500],
                         "timestamp": now, "session_id": session_id},
            })
            return ChatResponse(session_id=session_id, target_agent=target.name,
                                task_prompt=task_desc, status="completed" if result.success else "failed")

        elif analysis.startswith("CLARIFY:"):
            question = analysis.removeprefix("CLARIFY:").strip()
            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {"kind": "agent_reply", "agent": "cici咪",
                         "content": f"Need clarification: {question}", "timestamp": now},
            })
            return ChatResponse(target_agent="cici咪", task_prompt=question, status="clarify")

        else:
            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {"kind": "agent_reply", "agent": "cici咪", "content": analysis[:500], "timestamp": now},
            })
            return ChatResponse(target_agent="cici咪", task_prompt=content, status="responded")

    # ---- MULTIPLE @mentions: broadcast ----
    if len(parsed.mentions) > 1:
        mentioned = [m.name for m in parsed.mentions]
        await ws_mgr.broadcast({
            "type": "system_message",
            "data": {"content": f"Human mentioned {', '.join(mentioned)}: {content}", "timestamp": now},
        })
        return ChatResponse(target_agent="multiple", task_prompt=parsed.cleaned_content, status="broadcast")

    # ---- SINGLE @mention: direct route ----
    target = parsed.direct_target
    if target is None:
        raise HTTPException(status_code=400, detail="Could not resolve target agent")

    clean = parsed.cleaned_content or content
    runner = request.app.state.runner
    store = request.app.state.store
    router_inst = request.app.state.router
    router_inst.mark_busy(target)

    await ws_mgr.broadcast({
        "type": "task_started",
        "data": {"agent": target.name, "prompt": clean[:200], "timestamp": now},
    })

    try:
        task = AgentTask(prompt=clean)
        result = await runner.run(target, task)

        session_id = store.log(
            agent_name=target.name, prompt=task.full_prompt(),
            output=result.output, exit_code=result.exit_code,
            duration_ms=result.duration_ms, token_usage=result.token_usage,
            task_type="chat", started_at=result.started_at, finished_at=result.finished_at,
        )

        await ws_mgr.broadcast({
            "type": "task_complete",
            "data": {"agent": target.name, "session_id": session_id,
                     "success": result.success, "duration_ms": result.duration_ms,
                     "output_preview": result.output[:200], "timestamp": now},
        })
        await ws_mgr.broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": target.name, "content": result.output[:500],
                     "timestamp": now, "session_id": session_id},
        })

        return ChatResponse(session_id=session_id, target_agent=target.name,
                            task_prompt=clean, status="completed" if result.success else "failed")
    finally:
        router_inst.mark_free(target)

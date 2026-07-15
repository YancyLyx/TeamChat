"""
Chat endpoint for the Slack-style dashboard.

Uses engine.message_parser for @mention extraction (no duplicated regex).
Unaddressed messages go to cici咪 for analysis per spec.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engine.config import ALL_AGENTS, AGENT_CICI, AGENT_COCO, AGENT_SOSO
from engine.message_parser import parse_message, build_cici_analysis_prompt
from engine.runner import AgentTask, AgentResult


async def _spawn_with_session(agent, task, runner, session_store,
                               teamchat_session_id) -> AgentResult:
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

GREETING_KEYWORDS = {"大家好", "hello", "hi", "在吗", "有人在吗", "你好", "你们好", "嗨"}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1)
    teamchat_session_id: int = 1  # which TeamChat session this message belongs to


class ChatResponse(BaseModel):
    session_id: int | None = None
    target_agent: str | None = None
    task_prompt: str = ""
    status: str = "ok"


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    content = chat_req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    parsed = parse_message(content)
    ws_mgr = request.app.state.ws_manager
    now = datetime.now(timezone.utc).isoformat()
    teamchat_session_id = chat_req.teamchat_session_id

    # Broadcast + persist human message
    await ws_mgr.broadcast({
        "type": "chat_message",
        "data": {"kind": "human", "agent": "human", "content": content, "timestamp": now},
    })
    # Log human message so chat history includes user content
    store = request.app.state.store
    store.log(
        agent_name="human", prompt=content, output=content,
        exit_code=0, duration_ms=0, task_type="chat_message", tag="prod",
        teamchat_session_id=teamchat_session_id,
        started_at=now, finished_at=now,
    )

    # ---- GREETING: broadcast to all three agents ----
    content_lower = content.lower().strip().rstrip("!！~～.。?？")
    is_greeting = content_lower in GREETING_KEYWORDS or (
        not parsed.mentions and len(content) <= 8 and
        any(kw in content_lower for kw in ["大家好", "hello", "hi", "在吗", "你好", "你们好"])
    )

    if is_greeting:
        runner = request.app.state.runner
        store = request.app.state.store
        router = request.app.state.router
        session_store = request.app.state.session_store
        greeting_msg = f"人类在聊天室发了 '{content}'。请简短回复一句问候/自我介绍（一句话即可），让人知道你在。"

        # Broadcast "analyzing" notification
        await ws_mgr.broadcast({
            "type": "system_message",
            "data": {"content": "三只猫收到了你的问候，正在回复...", "timestamp": now},
        })

        # Parallel: all three agents reply concurrently
        async def greet_one(agent):
            router.mark_busy(agent)
            task = AgentTask(prompt=greeting_msg, timeout_seconds=60)
            try:
                result = await _spawn_with_session(agent, task, runner,
                    session_store, teamchat_session_id)
            finally:
                router.mark_free(agent)
            # Log to store
            store.log(
                agent_name=agent.name, prompt=task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                task_type="chat_greeting", tag="prod",
                teamchat_session_id=teamchat_session_id,
                started_at=result.started_at, finished_at=result.finished_at,
            )
            # Broadcast as soon as this agent replies
            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {
                    "kind": "agent_reply",
                    "agent": agent.name,
                    "content": result.output[:500],
                    "timestamp": now,
                },
            })

        await asyncio.gather(
            greet_one(AGENT_CICI),
            greet_one(AGENT_COCO),
            greet_one(AGENT_SOSO),
        )

        return ChatResponse(target_agent="all", task_prompt=content, status="greeting_broadcast")

    # ---- NO @mention: cici咪 analyzes ----
    if not parsed.mentions:
        await ws_mgr.broadcast({
            "type": "system_message",
            "data": {"content": f"cici咪 analyzing: {content[:80]}...", "timestamp": now},
        })

        runner = request.app.state.runner
        store = request.app.state.store
        router = request.app.state.router
        session_store = request.app.state.session_store

        analysis_prompt = build_cici_analysis_prompt(content)
        router.mark_busy(AGENT_CICI)
        try:
            result = await _spawn_with_session(
                AGENT_CICI, AgentTask(prompt=analysis_prompt, timeout_seconds=60),
                runner, session_store, teamchat_session_id,
            )
        finally:
            router.mark_free(AGENT_CICI)
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
            router.mark_busy(target)
            try:
                result = await _spawn_with_session(
                    target, task, runner, session_store, teamchat_session_id,
                )
            finally:
                router.mark_free(target)

            call_id = store.log(
                agent_name=target.name, prompt=task.full_prompt(),
                output=result.output, exit_code=result.exit_code,
                duration_ms=result.duration_ms, token_usage=result.token_usage,
                task_type="chat_task", teamchat_session_id=teamchat_session_id,
                started_at=result.started_at, finished_at=result.finished_at,
            )

            await ws_mgr.broadcast({
                "type": "chat_message",
                "data": {"kind": "agent_reply", "agent": target.name, "content": result.output[:500],
                         "timestamp": now, "session_id": call_id},
            })
            return ChatResponse(session_id=call_id, target_agent=target.name,
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
    session_store = request.app.state.session_store
    router_inst.mark_busy(target)

    await ws_mgr.broadcast({
        "type": "task_started",
        "data": {"agent": target.name, "prompt": clean[:200], "timestamp": now},
    })

    try:
        task = AgentTask(prompt=clean)
        result = await _spawn_with_session(
            target, task, runner, session_store, teamchat_session_id,
        )

        call_id = store.log(
            agent_name=target.name, prompt=task.full_prompt(),
            output=result.output, exit_code=result.exit_code,
            duration_ms=result.duration_ms, token_usage=result.token_usage,
            task_type="chat", teamchat_session_id=teamchat_session_id,
            started_at=result.started_at, finished_at=result.finished_at,
        )

        await ws_mgr.broadcast({
            "type": "task_complete",
            "data": {"agent": target.name, "session_id": call_id,
                     "success": result.success, "duration_ms": result.duration_ms,
                     "output_preview": result.output[:200], "timestamp": now},
        })
        await ws_mgr.broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": target.name, "content": result.output[:500],
                     "timestamp": now, "session_id": call_id},
        })

        return ChatResponse(session_id=call_id, target_agent=target.name,
                            task_prompt=clean, status="completed" if result.success else "failed")
    finally:
        router_inst.mark_free(target)

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
from engine.dispatch import spawn_with_session
from engine.message_parser import parse_message, build_cici_analysis_prompt
from engine.runner import AgentTask, AgentResult

GREETING_KEYWORDS = {"大家好", "hello", "hi", "在吗", "有人在吗", "你好", "你们好", "嗨"}


async def _drain_relay(request) -> None:
    """After cici咪 frees up, immediately process queued review results.

    Without this, queued results wait for the next relay() call, adding latency
    (soso咪 review 备注2 on PR #94).
    """
    relay = getattr(request.app.state, "result_relay", None)
    if relay:
        try:
            await relay.drain_if_idle()
        except Exception as exc:
            logger.warning(f"drain relay failed: {exc}")


logger = logging.getLogger("teamchat.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Engine-level logging — visible in uvicorn terminal
engine_log = logging.getLogger("teamchat.engine")


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

    engine_log.info(f"💬 Human: '{content[:80]}' | session={teamchat_session_id} | mentions={[m.name for m in parsed.mentions]}")

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
        engine_log.info("👋 Greeting detected → broadcasting to all 3 agents")

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
            engine_log.info(f"🚀 Spawning {agent.name} ({agent.cli}) | session={teamchat_session_id}")
            router.mark_busy(agent)
            task = AgentTask(prompt=greeting_msg, timeout_seconds=60)
            try:
                result = await spawn_with_session(agent, task, runner,
                    session_store, teamchat_session_id)
            finally:
                router.mark_free(agent)
                if agent == AGENT_CICI:
                    await _drain_relay(request)
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
        task_table = request.app.state.task_table
        # Tasks created by cici咪 via MCP default to teamchat_session_id=1
        # (MCP server is stateless) — track what exists so we can fix sessions below.
        tasks_before = {t.id for t in task_table.list_tasks()}

        analysis_prompt = build_cici_analysis_prompt(content)
        engine_log.info(f"🤔 No @mention → spawning cici咪 for analysis")
        router.mark_busy(AGENT_CICI)
        try:
            result = await spawn_with_session(
                AGENT_CICI, AgentTask(prompt=analysis_prompt, timeout_seconds=120),
                runner, session_store, teamchat_session_id,
            )
        finally:
            router.mark_free(AGENT_CICI)
            # cici咪 空闲了 → 立即处理排队的审核结果（soso咪 review 备注2）
            await _drain_relay(request)
        analysis = result.output.strip()

        # Fix teamchat_session_id on tasks cici咪 just created via MCP —
        # they must belong to the session this message arrived in, otherwise
        # ResultRelay would resume the wrong cici咪 session for review.
        for t in task_table.list_tasks():
            if t.id not in tasks_before and t.teamchat_session_id != teamchat_session_id:
                task_table.update(t.id, teamchat_session_id=teamchat_session_id)
                engine_log.info(
                    f"🔧 Fixed task #{t.id} session {t.teamchat_session_id} → {teamchat_session_id}"
                )

        engine_log.info(f"📝 cici咪 analysis result ({len(analysis)} chars)")
        # Always show cici咪's output in chat bubble
        await ws_mgr.broadcast({
            "type": "chat_message",
            "data": {"kind": "agent_reply", "agent": "cici咪", "content": analysis[:500], "timestamp": now},
        })

        # cici咪 has created tasks via MCP tools during analysis.
        # The TaskScheduler (background loop) picks up unblocked tasks and dispatches them —
        # no synchronous dispatch here (ADR-003 中枢模式: Engine 派发, cici咪 决策).
        await ws_mgr.broadcast({
            "type": "system_message",
            "data": {"content": "cici咪 分析完成，任务已创建，调度器将自动派发", "timestamp": now},
        })
        return ChatResponse(target_agent="cici咪", task_prompt=content, status="analyzed")

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
        result = await spawn_with_session(
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
        if target == AGENT_CICI:
            await _drain_relay(request)

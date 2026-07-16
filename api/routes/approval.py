"""
Approval endpoint — human responds to Claude CLI tool permission requests.

When Claude needs tool approval, runner.py captures the control_request
and stores it in memory. This endpoint receives the human's decision
and writes the control_response back to the Claude process stdin.
"""

import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("teamchat.engine")

router = APIRouter(prefix="/api/approval", tags=["approval"])

# In-memory store: request_id -> (stdin_writer, asyncio.Event)
_pending_approvals: dict[str, tuple[asyncio.StreamWriter, asyncio.Event]] = {}


def register_approval(request_id: str, stdin_writer: asyncio.StreamWriter, event_data: dict | None = None):
    """Called by runner.py when Claude emits a control_request."""
    event = asyncio.Event()
    _pending_approvals[request_id] = (stdin_writer, event)
    logger.info(f"[Engine] 🔒 Approval requested: {request_id}")
    return event  # Return event so caller can await it


def clear_approval(request_id: str):
    _pending_approvals.pop(request_id, None)


class ApprovalRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    decision: Literal["allow", "deny"]


def build_control_response(request_id: str, decision: str) -> str:
    """Build Claude CLI control_response JSON (ADR-003 §3.5)."""
    response_msg = (
        {"behavior": "allow", "updatedInput": {}}
        if decision == "allow"
        else {"behavior": "deny", "message": "The user denied this tool use."}
    )
    return json.dumps({
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": request_id,
            "response": response_msg,
        },
    }, ensure_ascii=False) + "\n"


@router.post("")
async def handle_approval(body: ApprovalRequest):
    """Handle human decision on a Claude tool approval request."""
    entry = _pending_approvals.get(body.request_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Approval request not found or already handled")

    stdin_writer, event = entry
    control_response = build_control_response(body.request_id, body.decision)

    try:
        stdin_writer.write(control_response.encode("utf-8"))
        await stdin_writer.drain()
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        clear_approval(body.request_id)
        raise HTTPException(status_code=410, detail=f"Claude process no longer accepting input: {exc}") from exc

    event.set()  # Signal the runner to continue reading stdout
    clear_approval(body.request_id)
    logger.info(f"[Engine] ✅ Approval {body.request_id}: {body.decision}")

    return {"status": "ok", "request_id": body.request_id, "decision": body.decision}

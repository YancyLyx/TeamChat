"""
Approval endpoint — human responds to Claude CLI tool permission requests.

When Claude needs tool approval, runner.py captures the control_request
and stores it in memory. This endpoint receives the human's decision
and writes the control_response back to the Claude process stdin.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("teamchat.engine")

router = APIRouter(prefix="/api/approval", tags=["approval"])

# In-memory store: request_id -> (stdin_writer, event_data)
_pending_approvals: dict[str, asyncio.StreamWriter] = {}


def register_approval(request_id: str, stdin_writer: asyncio.StreamWriter, event_data: dict = None):
    """Called by runner.py when Claude emits a control_request."""
    _pending_approvals[request_id] = stdin_writer
    logger.info(f"[Engine] 🔒 Approval requested: {request_id}")


def clear_approval(request_id: str):
    _pending_approvals.pop(request_id, None)


class ApprovalRequest(BaseModel):
    request_id: str
    decision: str  # "allow" or "deny"


@router.post("")
async def handle_approval(request: Request, body: ApprovalRequest):
    """Handle human decision on a Claude tool approval request."""
    stdin_writer = _pending_approvals.get(body.request_id)
    if not stdin_writer:
        raise HTTPException(status_code=404, detail="Approval request not found or already handled")

    behavior = "allow" if body.decision == "allow" else "deny"
    response_msg = {
        "behavior": "allow",
        "updatedInput": {},
    } if behavior == "allow" else {
        "behavior": "deny",
        "message": "The user denied this tool use.",
    }

    control_response = json.dumps({
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": body.request_id,
            "response": response_msg,
        },
    }, ensure_ascii=False) + "\n"

    # Write to Claude's stdin — the runner is waiting for this
    stdin_writer.write(control_response.encode("utf-8"))
    await stdin_writer.drain()

    clear_approval(body.request_id)
    logger.info(f"[Engine] ✅ Approval {body.request_id}: {body.decision}")

    return {"status": "ok", "request_id": body.request_id, "decision": body.decision}

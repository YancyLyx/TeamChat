"""
GitHub Webhook endpoint — receives GitHub events, bridges them into tasks.

Security: X-Hub-Signature-256 verification is optional. Set
TEAMCHAT_GITHUB_WEBHOOK_SECRET to enable it (GitHub → repo → Settings →
Webhooks → Secret).
"""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from engine.github_adapter import handle_issue_event

logger = logging.getLogger("teamchat.engine")
router = APIRouter(prefix="/api/github", tags=["github"])


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify X-Hub-Signature-256 if a secret is configured."""
    secret = os.getenv("TEAMCHAT_GITHUB_WEBHOOK_SECRET")
    if not secret:
        return True  # no secret configured → no verification
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post("/webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events (issues.opened → create task)."""
    event_type = request.headers.get("X-GitHub-Event", "")
    raw_body = await request.body()

    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    if event_type != "issues":
        logger.info(f"[GitHub] Ignoring event type: {event_type}")
        return {"status": "ignored", "event": event_type}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    task_table = request.app.state.task_table
    created = handle_issue_event(payload, task_table)

    if created:
        return {"status": "task_created", "task": created}
    return {"status": "ignored", "event": event_type}

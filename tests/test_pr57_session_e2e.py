"""
E2E/API tests for PR #57 — session bugs (default IDs, human log, session_id).

Run:
  pytest tests/test_pr57_session_e2e.py -v
"""

from __future__ import annotations

import httpx
import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

from engine.session_store import DEFAULT_SESSION_NAME

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

KNOWN_IDS = {
    "claude_id": "5fbaf844-4cbc-48b2-9242-7902d098bd81",
    "codex_id": "019f40ef-e8cf-76f0-8b49-6691cc7275f3",
    "cursor_id": "04e64d6d-de38-4861-a7ce-87c26d28d77f",
}


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestDefaultSessionIds:
    """Default session should pre-fill agent CLI session IDs."""

    def test_default_session_has_agent_ids(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        sessions = httpx.get(f"{api_url}/api/session-manager", timeout=10.0).json()
        default = next((s for s in sessions if s["name"] == DEFAULT_SESSION_NAME), None)
        assert default is not None
        for key in ("claude_id", "codex_id", "cursor_id"):
            assert default.get(key), f"missing {key}"
        assert default["claude_id"] == KNOWN_IDS["claude_id"]
        assert default["cursor_id"] == KNOWN_IDS["cursor_id"]
        assert KNOWN_IDS["codex_id"] in default["codex_id"]


class TestHumanMessageLog:
    """Human chat messages should persist to agent_calls."""

    def test_chat_logs_human_message_with_session_id(self, e2e_servers, e2e_app):
        api_url = e2e_servers["api_url"]
        marker = "pr57-human-log-marker"
        resp = httpx.post(
            f"{api_url}/api/chat",
            json={"content": f"@coco咪 {marker}", "teamchat_session_id": 1},
            timeout=30.0,
        )
        resp.raise_for_status()

        rows = httpx.get(
            f"{api_url}/api/sessions?agent=human&limit=5&tag=prod&teamchat_session_id=1",
            timeout=10.0,
        ).json()
        assert any(r["prompt"] == f"@coco咪 {marker}" and r["task_type"] == "chat_message" for r in rows)

    def test_human_message_survives_page_reload(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        marker = "pr57-reload-human-msg"
        httpx.post(
            f"{api_url}/api/chat",
            json={"content": f"@coco咪 {marker}", "teamchat_session_id": 1},
            timeout=30.0,
        ).raise_for_status()

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        expect(page.get_by_text(f"@coco咪 {marker}")).to_be_visible(timeout=10_000)

        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_connected(page)
        expect(page.get_by_text(f"@coco咪 {marker}")).to_be_visible(timeout=10_000)


class TestSessionIdPassThrough:
    """ChatRequest teamchat_session_id should scope persisted rows."""

    def test_chat_scopes_to_non_default_session(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        scope_dir = "/tmp/pr57-scope"
        Path(scope_dir).mkdir(parents=True, exist_ok=True)
        created = httpx.post(
            f"{api_url}/api/session-manager",
            json={"name": "PR57 Scope Test", "directory": scope_dir},
            timeout=10.0,
        ).json()
        sid = created["id"]
        marker = f"pr57-scope-{sid}"

        httpx.post(
            f"{api_url}/api/chat",
            json={"content": f"@coco咪 {marker}", "teamchat_session_id": sid},
            timeout=30.0,
        ).raise_for_status()

        scoped = httpx.get(
            f"{api_url}/api/sessions?agent=human&limit=10&tag=prod&teamchat_session_id={sid}",
            timeout=10.0,
        ).json()
        assert any(r["prompt"] == f"@coco咪 {marker}" for r in scoped)

        default_rows = httpx.get(
            f"{api_url}/api/sessions?agent=human&limit=20&tag=prod&teamchat_session_id=1",
            timeout=10.0,
        ).json()
        assert not any(r["prompt"] == f"@coco咪 {marker}" for r in default_rows)

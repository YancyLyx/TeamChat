"""
E2E tests for Issue #47 — default session seed + agent session ID pre-fill.

Run:
  pytest tests/test_issue47_e2e.py -v
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from engine.session_store import DEFAULT_SESSION_NAME

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _open_session_manager(page: Page) -> None:
    page.get_by_role("button").filter(has_text="TeamChat").first.click()
    expect(page.get_by_role("heading", name="Session Manager")).to_be_visible()


class TestDefaultSessionSeed:
    def test_api_seeds_default_session_on_first_start(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/session-manager", timeout=10.0)
        resp.raise_for_status()
        sessions = resp.json()
        assert len(sessions) >= 1
        default = next((s for s in sessions if s["name"] == DEFAULT_SESSION_NAME), None)
        assert default is not None
        assert default["directory"]

    def test_ui_shows_default_session_with_ready_agents(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        sessions = httpx.get(f"{api_url}/api/session-manager", timeout=10.0).json()
        default = next(s for s in sessions if s["name"] == DEFAULT_SESSION_NAME)

        # Simulate discovered agent IDs (portable vs hardcoded machine UUIDs)
        httpx.patch(
            f"{api_url}/api/session-manager/{default['id']}",
            json={
                "claude_id": "test-claude-session",
                "codex_id": "test-codex-session",
                "cursor_id": "test-cursor-session",
            },
            timeout=10.0,
        ).raise_for_status()

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        card = page.locator("div.border.rounded-xl").filter(
            has=page.get_by_role("heading", name=DEFAULT_SESSION_NAME)
        ).first
        expect(card).to_be_visible(timeout=5_000)
        expect(card.locator(".session-dot.ready")).to_have_count(3)


class TestSessionCrud:
    def test_new_session_persists_after_reload(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        name = f"Issue47 {uuid.uuid4().hex[:6]}"
        directory = f"/tmp/teamchat-i47-{uuid.uuid4().hex[:8]}"
        Path(directory).mkdir(parents=True, exist_ok=True)

        page.get_by_placeholder("Session name").fill(name)
        page.get_by_placeholder("Absolute directory path").fill(directory)
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=5_000)

        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_connected(page)
        _open_session_manager(page)
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=10_000)

    def test_delete_session_via_ui(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        name = f"DeleteMe {uuid.uuid4().hex[:6]}"
        directory = f"/tmp/teamchat-del-{uuid.uuid4().hex[:8]}"
        Path(directory).mkdir(parents=True, exist_ok=True)

        page.get_by_placeholder("Session name").fill(name)
        page.get_by_placeholder("Absolute directory path").fill(directory)
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=5_000)

        card = page.locator("div.border.rounded-xl").filter(
            has=page.get_by_role("heading", name=name)
        ).first
        card.get_by_role("button", name="Session menu").click()
        card.get_by_role("button", name="Delete", exact=True).click()
        expect(page.get_by_role("heading", name=name)).to_have_count(0, timeout=5_000)

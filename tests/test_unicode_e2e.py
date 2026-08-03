"""E2E: dashboard renders emoji, not Python-style \\U0001f escape literals."""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import broadcast_ws, seed_task_table

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestUnicodeDisplay:
    def test_header_and_agent_cards_show_emoji_not_escapes(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        # Must not show raw JS-invalid Python-style escapes
        expect(page.locator("body")).not_to_contain_text(r"\U0001f")
        expect(page.locator("body")).not_to_contain_text(r"\U0001F")

        # Real emoji should appear
        expect(page.locator("header")).to_contain_text("🤖")
        expect(page.locator("aside").first).to_contain_text("🏗️")
        expect(page.locator("aside").first).to_contain_text("⚡")
        expect(page.locator("aside").first).to_contain_text("🔍")

    def test_task_panel_icons_are_emoji(self, page: Page, e2e_servers, e2e_app):
        seed_task_table(
            e2e_app, agent="coco咪", title=f"RUN_{uuid.uuid4().hex[:8]}", status="running"
        )
        seed_task_table(
            e2e_app, agent="soso咪", title=f"DONE_{uuid.uuid4().hex[:8]}", status="done"
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        task_panel = page.locator("aside").filter(has=page.get_by_text("Tasks", exact=True))
        expect(task_panel.get_by_text("Running")).to_be_visible()
        expect(task_panel.get_by_text("Done")).to_be_visible()
        expect(task_panel).to_contain_text("📋")
        expect(task_panel).to_contain_text("✅")
        expect(task_panel).not_to_contain_text(r"\U0001f4cb")

    def test_ws_chat_message_renders_emoji(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        marker = "🏗️ Unicode WS marker ✅"
        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": "unicode-ws-e2e",
                    "kind": "agent",
                    "agent": "cici咪",
                    "content": marker,
                    "timestamp": "2026-07-15T12:00:00Z",
                },
            },
        )
        expect(page.get_by_text(marker)).to_be_visible(timeout=10_000)

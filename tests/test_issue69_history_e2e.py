"""
E2E tests for Issue #69 — PR #68 retrospective: history order + human alignment.

Run:
  pytest tests/test_issue69_history_e2e.py -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import seed_session

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestHistoryOrder:
    def test_older_messages_appear_before_newer_after_reload(self, page: Page, e2e_servers, e2e_app):
        first = "issue69-history-first"
        second = "issue69-history-second"
        seed_session(
            e2e_app, agent_name="human", prompt=first, output=first,
            tag="prod",
        )
        seed_session(
            e2e_app, agent_name="human", prompt=second, output=second,
            tag="prod",
        )

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        main = page.locator("main")
        first_el = main.get_by_text(first).first
        second_el = main.get_by_text(second).first
        expect(first_el).to_be_visible(timeout=10_000)
        expect(second_el).to_be_visible(timeout=10_000)

        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_connected(page)

        first_box = main.get_by_text(first).first.bounding_box()
        second_box = main.get_by_text(second).first.bounding_box()
        assert first_box and second_box
        assert first_box["y"] < second_box["y"], "history should be oldest-first (top to bottom)"


class TestHumanAlignment:
    def test_human_messages_right_aligned_blue_bubble(self, page: Page, e2e_servers, e2e_app):
        marker = "issue69-human-align"
        seed_session(
            e2e_app, agent_name="human", prompt=marker, output=marker,
            tag="prod",
        )

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        bubble = page.locator("div.flex.justify-end.mb-3").filter(has_text=marker)
        expect(bubble).to_be_visible(timeout=10_000)
        expect(bubble.locator("div.bg-blue-500")).to_be_visible()

    def test_agent_prompts_not_shown_as_human_bubbles(self, page: Page, e2e_servers, e2e_app):
        agent_marker = "issue69-agent-prompt-only"
        seed_session(
            e2e_app, agent_name="coco咪", prompt=agent_marker, output="agent reply body",
            tag="prod",
        )

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        human_style = page.locator("div.flex.justify-end.mb-3").filter(has_text=agent_marker)
        expect(human_style).to_have_count(0, timeout=10_000)
        expect(page.locator("main").get_by_text(agent_marker).first).to_be_visible(timeout=10_000)

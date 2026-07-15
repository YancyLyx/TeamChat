"""
Playwright E2E tests for PR #41 — Engine observability Live panel.

Run:
  pytest tests/test_pr41_e2e.py -v
"""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestLivePanel:
    def test_live_tab_shows_engine_mode_and_agents(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Live", exact=True).click()

        expect(right_aside.get_by_text("🔴 Live")).to_be_visible(timeout=10_000)
        expect(right_aside.get_by_text("Engine Mode")).to_be_visible()
        expect(right_aside.get_by_text("Parallel")).to_be_visible()
        left_aside = page.locator("aside").first
        for agent in ("cici咪", "coco咪", "soso咪"):
            expect(left_aside.get_by_role("heading", name=agent)).to_be_visible()

    def test_engine_api_returns_observability_fields(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/engine", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        assert data["mode"] in ("parallel", "serial")
        assert len(data["active_agents"]) == 3
        assert "queue_length" in data

    def test_right_panel_has_stats_and_live_not_tasks(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        expect(right_aside.get_by_role("button", name="Stats", exact=True)).to_be_visible()
        expect(right_aside.get_by_role("button", name="Live", exact=True)).to_be_visible()
        expect(right_aside.get_by_role("button", name="Tasks", exact=True)).to_have_count(0)

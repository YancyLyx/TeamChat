"""
E2E tests for PR #72 — Agent Sidebar real-time status + Stats L1/L2/L3 (#71).

Run:
  pytest tests/test_pr72_e2e.py -v
"""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import seed_session

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestAgentSidebarStatus:
    def test_sidebar_shows_idle_not_task_stats(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="coco咪", prompt="sidebar seed", output="ok", tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        left_aside = page.locator("aside").first
        expect(left_aside.get_by_text("idle").first).to_be_visible(timeout=10_000)
        expect(left_aside.get_by_text("tasks ·", exact=False)).to_have_count(0)
        expect(left_aside.get_by_text("0%")).to_have_count(0)

    def test_sidebar_agents_not_in_live_tab(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Live", exact=True).click()
        expect(right_aside.get_by_text("Engine Mode")).to_be_visible(timeout=10_000)
        expect(right_aside.get_by_text("Active Agents")).to_have_count(0)
        expect(right_aside.get_by_text("Recent Events")).to_be_visible()


class TestStatsL1L2L3:
    def test_stats_subtabs_and_l1_tool_calls(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="coco咪", prompt="l1 stats", output="ok", tag="prod",
            token_usage={"input_tokens": 5, "output_tokens": 5},
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        stats_panel = page.locator("aside").last
        expect(stats_panel.get_by_role("button", name="L1 效能")).to_be_visible()
        expect(stats_panel.get_by_role("button", name="L2 效率")).to_be_visible()
        expect(stats_panel.get_by_role("button", name="L3 解放")).to_be_visible()
        expect(stats_panel.get_by_text("tool calls").first).to_be_visible(timeout=10_000)
        expect(stats_panel.get_by_text("Weekly Summary")).to_be_visible()

    def test_l2_shows_engine_and_task_stats(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        stats_panel = page.locator("aside").last
        stats_panel.get_by_role("button", name="L2 效率").click()
        expect(stats_panel.get_by_text("Engine Mode")).to_be_visible(timeout=10_000)
        expect(stats_panel.get_by_text("Parallel")).to_be_visible()
        expect(stats_panel.get_by_text("Task Stats")).to_be_visible()
        expect(stats_panel.get_by_text("completion:")).to_be_visible()

    def test_l3_shows_computed_liberation_metrics(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="human", prompt="human msg", output="human msg", tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        stats_panel = page.locator("aside").last
        stats_panel.get_by_role("button", name="L3 解放").click()
        expect(stats_panel.get_by_text("Human Liberation")).to_be_visible(timeout=10_000)
        expect(stats_panel.get_by_text("Automation Rate")).to_be_visible()
        expect(stats_panel.get_by_text("Manual Interventions")).to_be_visible()
        expect(stats_panel.get_by_text("Message to Completion")).to_be_visible()
        # Must not show PR placeholder hardcodes
        expect(stats_panel.get_by_text("87%")).to_have_count(0)
        expect(stats_panel.get_by_text("15 min", exact=True)).to_have_count(0)

    def test_task_table_stats_api_shape(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/tasks/table/stats", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        for key in ("total", "done", "pending", "running", "completion_rate"):
            assert key in data

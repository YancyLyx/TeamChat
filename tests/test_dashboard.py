"""
Playwright E2E tests for the TeamChat Dashboard shell and task sidebar.

Requires:
  - playwright + chromium: playwright install chromium
  - Running servers (started automatically via conftest.py fixtures)

Run:
  pytest tests/test_dashboard.py -v
"""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import seed_task_table

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

def _goto_dashboard(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)
    expect(page.locator("header")).to_contain_text("Connected", timeout=timeout)


class TestDashboardLoad:
    def test_dashboard_page_loads(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        expect(page.locator("h1")).to_contain_text("TeamChat")

    def test_three_agent_cards_visible(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        expect(page.get_by_text("cici咪", exact=True).first).to_be_visible()
        expect(page.get_by_text("coco咪", exact=True).first).to_be_visible()
        expect(page.get_by_text("soso咪", exact=True).first).to_be_visible()


class TestWebSocketConnection:
    def test_websocket_connection_indicator(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        expect(page.locator("header .bg-green-500").first).to_be_visible()


class TestTaskBoardFlow:
    def test_running_task_appears_in_running_group(self, page: Page, e2e_servers, e2e_app):
        marker = f"RUNNING_{uuid.uuid4().hex[:8]}"
        seed_task_table(e2e_app, agent="coco咪", title=marker, status="running")

        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        expect(tasks_panel.get_by_test_id("tasks-group-running").get_by_text(marker)).to_be_visible(timeout=10_000)

    def test_done_task_appears_in_done_group(self, page: Page, e2e_servers, e2e_app):
        marker = f"DONE_{uuid.uuid4().hex[:8]}"
        seed_task_table(e2e_app, agent="soso咪", title=marker, status="done")

        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        expect(tasks_panel.get_by_test_id("tasks-group-done").get_by_text(marker)).to_be_visible(timeout=15_000)


class TestWebSocketReconnect:
    def test_disconnect_reconnect(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        page.context.set_offline(True)
        expect(page.get_by_text("已断开")).to_be_visible(timeout=20_000)

        page.context.set_offline(False)
        _wait_connected(page, timeout=30_000)


class TestErrorState:
    def test_failed_task_shows_error_indicator(self, page: Page, e2e_servers, e2e_app):
        marker = f"FAIL_{uuid.uuid4().hex[:8]}"
        seed_task_table(e2e_app, agent="coco咪", title=marker, status="failed")

        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        failed_group = tasks_panel.get_by_test_id("tasks-group-failed")
        expect(failed_group.get_by_text(marker)).to_be_visible(timeout=15_000)
        expect(failed_group.get_by_text("执行失败")).to_be_visible()

"""
Playwright E2E tests for the TeamChat Dashboard.

Requires:
  - playwright + chromium: playwright install chromium
  - Running servers (started automatically via conftest_dashboard.py fixtures)

Run:
  pytest tests/test_dashboard.py -v
"""

from __future__ import annotations

import threading

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import inject_bus_message

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

HELLO_TASK = {
    "agent": "cici咪",
    "prompt": "Say hello in one short sentence. Output ONLY the greeting.",
}


def _goto_dashboard(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.locator("header")).to_contain_text("已连接", timeout=timeout)
    expect(page.locator("header .status-dot.connected")).to_be_visible(timeout=timeout)


def _submit_task(api_url: str, payload: dict) -> None:
    response = httpx.post(f"{api_url}/api/tasks", json=payload, timeout=60.0)
    response.raise_for_status()


def _column_locator(page: Page, label: str):
    return page.locator(f"h3:has-text('{label}')").locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]")


class TestDashboardLoad:
    def test_dashboard_page_loads(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        expect(page.locator("h1")).to_contain_text("TeamChat")

    def test_three_agent_cards_visible(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        expect(page.locator("h3", has_text="cici咪")).to_be_visible()
        expect(page.locator("h3", has_text="coco咪")).to_be_visible()
        expect(page.locator("h3", has_text="soso咪")).to_be_visible()


class TestWebSocketConnection:
    def test_websocket_connection_indicator(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        expect(page.locator("header .status-dot.connected")).to_be_visible()


class TestTaskBoardFlow:
    def test_submit_task_appears_on_taskboard(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        worker = threading.Thread(
            target=_submit_task,
            args=(api_url, HELLO_TASK),
            daemon=True,
        )
        worker.start()

        running_column = _column_locator(page, "进行中")
        expect(running_column.locator(".task-card")).to_have_count(1, timeout=10_000)
        worker.join(timeout=60)

    def test_task_moves_to_done_column(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        _submit_task(api_url, HELLO_TASK)

        done_column = _column_locator(page, "已完成")
        done_card = done_column.locator(".task-card", has_text="cici咪").first
        expect(done_card).to_be_visible(timeout=15_000)
        expect(done_card).to_contain_text("Say hello")


class TestMessageLog:
    def test_agent_message_appends_to_log(self, page: Page, e2e_servers, e2e_app):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        message_text = "E2E bus message from cici to coco"
        inject_bus_message(e2e_app, message_text)

        expect(page.locator("text=对话日志").locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]")).to_contain_text(
            message_text,
            timeout=10_000,
        )


class TestWebSocketReconnect:
    def test_disconnect_reconnect(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        page.context.set_offline(True)
        expect(page.locator("header")).to_contain_text("已断开", timeout=20_000)

        page.context.set_offline(False)
        _wait_connected(page, timeout=30_000)


class TestErrorState:
    def test_failed_task_shows_error_indicator(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        fail_prompt = "Please fail this task intentionally"
        _submit_task(
            api_url,
            {
                "agent": "coco咪",
                "prompt": fail_prompt,
            },
        )

        done_column = _column_locator(page, "已完成")
        failed_card = done_column.locator(".task-card", has_text=fail_prompt[:40])
        expect(failed_card).to_be_visible(timeout=15_000)
        expect(failed_card).to_contain_text("❌")

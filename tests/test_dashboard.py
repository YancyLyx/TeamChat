"""
Playwright E2E tests for the TeamChat Dashboard shell and task sidebar.

Requires:
  - playwright + chromium: playwright install chromium
  - Running servers (started automatically via conftest.py fixtures)

Run:
  pytest tests/test_dashboard.py -v
"""

from __future__ import annotations

import threading
import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

HELLO_TASK = {
    "agent": "cici咪",
    "prompt": "Say hello in one short sentence. Output ONLY the greeting.",
}


def _goto_dashboard(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)
    expect(page.locator("header")).to_contain_text("Connected", timeout=timeout)


def _submit_task(api_url: str, payload: dict) -> None:
    response = httpx.post(f"{api_url}/api/tasks", json=payload, timeout=60.0)
    response.raise_for_status()


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
    def test_submit_task_appears_in_progress(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        token = uuid.uuid4().hex[:8]
        payload = {**HELLO_TASK, "prompt": f"{HELLO_TASK['prompt']} {token}"}

        worker = threading.Thread(
            target=_submit_task,
            args=(api_url, payload),
            daemon=True,
        )
        worker.start()

        in_progress_section = page.locator("aside").filter(has=page.get_by_text("Running", exact=True))
        expect(in_progress_section.get_by_text(token)).to_be_visible(timeout=10_000)
        worker.join(timeout=60)

    def test_task_moves_to_done_column(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        token = uuid.uuid4().hex[:8]
        _submit_task(api_url, {**HELLO_TASK, "prompt": f"{HELLO_TASK['prompt']} {token}"})

        page.reload()
        _wait_connected(page)

        done_section = page.locator("aside").filter(has=page.get_by_text("Done", exact=True))
        expect(done_section.get_by_text(token)).to_be_visible(timeout=15_000)


class TestWebSocketReconnect:
    def test_disconnect_reconnect(self, page: Page, e2e_servers):
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        page.context.set_offline(True)
        expect(page.get_by_text("已断开")).to_be_visible(timeout=20_000)

        page.context.set_offline(False)
        _wait_connected(page, timeout=30_000)


class TestErrorState:
    def test_failed_task_shows_error_indicator(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto_dashboard(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        fail_prompt = f"Please fail intentionally {uuid.uuid4().hex[:8]}"
        _submit_task(
            api_url,
            {
                "agent": "coco咪",
                "prompt": fail_prompt,
            },
        )

        page.reload()
        _wait_connected(page)

        done_section = page.locator("aside").filter(has=page.get_by_text("Done", exact=True))
        expect(done_section.get_by_text("❌").first).to_be_visible(timeout=15_000)
        expect(done_section.get_by_text(fail_prompt[:40])).to_be_visible(timeout=15_000)

"""
E2E tests for Issue #88 — ChatRoom refresh button.

Run:
  pytest tests/test_issue88_refresh_e2e.py -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import seed_session

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

REFRESH_BTN = 'button[title="刷新消息"]'


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _wait_loaded(page: Page, timeout: float = 15_000) -> None:
    expect(page.locator(REFRESH_BTN)).to_be_enabled(timeout=timeout)


class TestRefreshButtonRender:
    def test_refresh_button_visible_with_emoji(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        btn = page.locator(REFRESH_BTN)
        expect(btn).to_be_visible()
        expect(btn).to_contain_text("🔄")

    def test_message_count_shown_when_history_exists(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="human", prompt="issue88-count-marker", output="issue88-count-marker",
            tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        expect(page.get_by_text("条消息", exact=False).first).to_be_visible(timeout=10_000)


class TestRefreshButtonFetch:
    def test_click_refresh_pulls_new_messages(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        marker = "issue88-refresh-new-msg"
        seed_session(
            e2e_app, agent_name="human", prompt=marker, output=marker,
            tag="prod",
        )

        expect(page.get_by_text(marker)).to_have_count(0)
        page.locator(REFRESH_BTN).click()
        _wait_loaded(page)
        expect(page.get_by_text(marker).first).to_be_visible(timeout=10_000)


class TestRefreshButtonLoading:
    def test_refresh_shows_spin_and_disables_button(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="human", prompt="issue88-loading-seed", output="issue88-loading-seed",
            tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        blocked: list = []

        def block_sessions(route) -> None:
            if route.request.method == "GET" and "/api/sessions" in route.request.url:
                blocked.append(route)
                return
            route.continue_()

        page.route("**/api/sessions*", block_sessions)
        btn = page.locator(REFRESH_BTN)
        btn.click()

        expect(btn).to_be_disabled(timeout=5_000)
        expect(btn.locator("span.animate-spin")).to_be_visible(timeout=5_000)

        for route in blocked:
            route.continue_()
        _wait_loaded(page)
        expect(btn).to_be_enabled()


class TestRefreshButtonMobile:
    def test_refresh_tappable_on_mobile_viewport(self, page: Page, e2e_servers, e2e_app):
        page.set_viewport_size({"width": 375, "height": 667})
        seed_session(
            e2e_app, agent_name="human", prompt="issue88-mobile-seed", output="issue88-mobile-seed",
            tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        # Collapse sidebars so the refresh control is not covered on narrow viewports.
        toggles = page.locator("header div.flex.items-center.gap-2 > button")
        toggles.nth(0).click()
        toggles.nth(1).click()

        btn = page.locator(REFRESH_BTN)
        expect(btn).to_be_visible()
        box = btn.bounding_box()
        assert box and box["width"] >= 32 and box["height"] >= 32

        marker = "issue88-mobile-refresh"
        seed_session(
            e2e_app, agent_name="human", prompt=marker, output=marker,
            tag="prod",
        )
        btn.click()
        _wait_loaded(page)
        expect(page.get_by_text(marker).first).to_be_visible(timeout=10_000)


class TestRefreshButtonNetworkError:
    def test_refresh_shows_error_on_network_failure(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app, agent_name="human", prompt="issue88-error-seed", output="issue88-error-seed",
            tag="prod",
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _wait_loaded(page)

        page.route("**/api/sessions*", lambda route: route.abort("failed"))
        page.locator(REFRESH_BTN).click()
        _wait_loaded(page)

        expect(page.get_by_text("加载历史失败", exact=False)).to_be_visible(timeout=10_000)
        expect(page.locator(REFRESH_BTN)).to_be_enabled()

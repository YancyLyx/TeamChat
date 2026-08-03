"""
Playwright E2E tests for PR #40 / #41 — session persistence, stats tokens, Live panel.

Run:
  pytest tests/test_pr40_41_e2e.py -v
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

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


def _open_session_manager(page: Page) -> None:
    page.get_by_role("button").filter(has_text="📁").first.click()
    expect(page.get_by_role("heading", name="Session Manager")).to_be_visible()


def _ensure_dir(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


class TestSessionPersistence:
    def test_created_session_survives_page_reload(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        name = f"Persist {uuid.uuid4().hex[:6]}"
        directory = _ensure_dir(f"/tmp/teamchat-persist-{uuid.uuid4().hex[:8]}")
        page.get_by_placeholder("Session name").fill(name)
        page.get_by_placeholder("Absolute directory path").fill(directory)
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=5_000)

        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_connected(page)
        _open_session_manager(page)
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=10_000)
        expect(page.get_by_text(directory)).to_be_visible()


class TestStatsConsistency:
    def test_stats_panel_shows_token_metrics(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app,
            agent_name="coco咪",
            prompt="token stats seed",
            output="done",
            tag="prod",
            token_usage={"input_tokens": 100, "output_tokens": 50},
        )
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/stats", timeout=10.0)
        resp.raise_for_status()
        expected_tokens = resp.json()["agents"]["coco咪"]["total_tokens"]
        assert expected_tokens >= 150

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        stats_panel = page.locator("aside").last
        expect(stats_panel.get_by_role("button", name="L1 效能")).to_be_visible(timeout=10_000)
        expect(stats_panel.get_by_text(f"{expected_tokens} tokens", exact=True)).to_be_visible()
        expect(stats_panel.get_by_text("Weekly Summary")).to_be_visible()
        expect(stats_panel.get_by_text("Tokens", exact=True).last).to_be_visible()

    def test_stats_api_includes_token_fields(self, e2e_servers, e2e_app):
        seed_session(
            e2e_app,
            agent_name="soso咪",
            prompt="api token seed",
            output="ok",
            tag="prod",
        )
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/stats", timeout=10.0)
        resp.raise_for_status()
        agents = resp.json()["agents"]
        for name in ("cici咪", "coco咪", "soso咪"):
            assert "total_tokens" in agents[name]
            assert "token_usage" in agents[name]


class TestLivePanel:
    def test_live_tab_shows_engine_mode_and_agents(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        expect(right_aside.get_by_role("button", name="Live", exact=True)).to_be_visible()
        right_aside.get_by_role("button", name="Live", exact=True).click()

        expect(right_aside.get_by_text("🔴 Live")).to_be_visible(timeout=10_000)
        expect(right_aside.get_by_text("Engine Mode")).to_be_visible()
        expect(right_aside.get_by_text("Parallel")).to_be_visible()
        expect(right_aside.get_by_text("Recent Events")).to_be_visible()
        left_aside = page.locator("aside").first
        for agent in ("cici咪", "coco咪", "soso咪"):
            expect(left_aside.get_by_role("heading", name=agent)).to_be_visible()
            expect(left_aside.get_by_text("idle").first).to_be_visible()

    def test_engine_api_returns_observability_fields(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/engine", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        assert data["mode"] in ("parallel", "serial")
        assert len(data["active_agents"]) == 3
        assert "queue_length" in data
        assert all("name" in a and "is_busy" in a for a in data["active_agents"])

    def test_live_panel_shows_recent_ws_events(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        textarea = page.get_by_placeholder("发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)")
        textarea.fill("大家好")
        page.get_by_role("button", name="Send").click()

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Live", exact=True).click()
        expect(right_aside.get_by_text("Recent Events")).to_be_visible(timeout=15_000)
        expect(right_aside.get_by_text("chat_message").or_(right_aside.get_by_text("system_message")).first).to_be_visible(timeout=30_000)


class TestRightPanelTabs:
    def test_tasks_stats_live_tabs(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        expect(right_aside.get_by_role("button", name="Tasks", exact=True)).to_be_visible()
        expect(right_aside.get_by_role("button", name="Stats", exact=True)).to_be_visible()
        expect(right_aside.get_by_role("button", name="Live", exact=True)).to_be_visible()
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        expect(right_aside.get_by_role("button", name="L1 效能")).to_be_visible()

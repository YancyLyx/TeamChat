"""
Playwright E2E tests for PR #28 — SessionManager, AgentCard, StatsPanel (Issue #29).

Run:
  pytest tests/test_pr28_e2e.py -v
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _open_session_manager(page: Page) -> None:
    page.get_by_role("button").filter(has_text="📁").first.click()
    expect(page.get_by_role("heading", name="Session Manager")).to_be_visible()


def _session_card(page: Page, name: str):
    return page.locator("div.border.rounded-xl").filter(has_text=name).first


class TestSessionManagerMenu:
    def test_rename_copy_path_delete(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        second_name = f"E2E Second {uuid.uuid4().hex[:6]}"
        second_path = "/tmp/teamchat-pr28-second"
        Path(second_path).mkdir(parents=True, exist_ok=True)
        page.get_by_placeholder("Session name").fill(second_name)
        page.get_by_placeholder("Absolute directory path").fill(second_path)
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_role("heading", name=second_name)).to_be_visible(timeout=5_000)

        card = _session_card(page, second_name)
        card.get_by_role("button", name="Session menu").click()
        card.get_by_role("button", name="Rename").click()

        renamed = f"Renamed {uuid.uuid4().hex[:6]}"
        edit_input = page.locator("div.border.rounded-xl.relative input").first
        expect(edit_input).to_be_visible(timeout=5_000)
        edit_input.fill(renamed)
        edit_input.press("Enter")
        expect(page.get_by_role("heading", name=renamed)).to_be_visible(timeout=5_000)

        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        card = _session_card(page, renamed)
        card.get_by_role("button", name="Session menu").click()
        page.get_by_role("button", name="Copy Path").click()
        copied = page.evaluate("async () => navigator.clipboard.readText()")
        assert copied == second_path

        card.get_by_role("button", name="Session menu").click()
        page.get_by_role("button", name="Delete").click()
        expect(page.get_by_role("heading", name=renamed)).to_have_count(0, timeout=5_000)

    def test_uninitialized_agents_show_dashes_not_yellow_dot(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)
        _open_session_manager(page)

        fresh_name = f"Fresh {uuid.uuid4().hex[:6]}"
        page.get_by_placeholder("Session name").fill(fresh_name)
        Path("/tmp/teamchat-fresh").mkdir(parents=True, exist_ok=True)
        page.get_by_placeholder("Absolute directory path").fill("/tmp/teamchat-fresh")
        page.get_by_role("button", name="Create").click()

        card = _session_card(page, fresh_name)
        expect(card.locator(".session-dot.pending")).to_have_count(0)
        expect(card.get_by_text("--")).to_have_count(3)

    def test_session_switch_updates_header_label(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        expect(page.get_by_role("button").filter(has_text="📁")).to_be_visible()
        _open_session_manager(page)

        alt_name = f"Alt Session {uuid.uuid4().hex[:6]}"
        page.get_by_placeholder("Session name").fill(alt_name)
        Path("/tmp/teamchat-alt").mkdir(parents=True, exist_ok=True)
        page.get_by_placeholder("Absolute directory path").fill("/tmp/teamchat-alt")
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_role("heading", name=alt_name)).to_be_visible(timeout=5_000)

        page.get_by_role("button", name="Close session manager").click()

        expect(page.get_by_role("button").filter(has_text=alt_name)).to_be_visible(timeout=5_000)


class TestAgentRoleCard:
    def test_expand_shows_cli_personality_specialty(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        cici_card = page.locator("aside").first.locator("h3").filter(has_text="cici咪").locator("..")
        cici_card.click()

        expect(page.get_by_text("claude --print")).to_be_visible(timeout=5_000)
        expect(page.get_by_text("角色卡:")).to_be_visible()
        expect(page.get_by_text("专长:")).to_be_visible()
        expect(page.get_by_text("系统架构 / ADR / 任务拆分")).to_be_visible()

        coco_card = page.locator("aside").first.locator("h3").filter(has_text="coco咪").locator("..")
        coco_card.click()
        expect(page.get_by_text("codex exec")).to_be_visible()
        expect(page.get_by_text("React / FastAPI / 前端工程")).to_be_visible()


class TestStatsPanel:
    def test_stats_tab_shows_three_agents(self, page: Page, e2e_servers, e2e_app):
        api_url = e2e_servers["api_url"]
        httpx.post(
            f"{api_url}/api/tasks",
            json={"agent": "cici咪", "prompt": f"stats seed {uuid.uuid4().hex[:8]}"},
            timeout=60.0,
        ).raise_for_status()

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        page.get_by_role("button", name="Stats", exact=True).click()
        expect(page.get_by_role("button", name="L1 效能")).to_be_visible(timeout=10_000)

        stats_panel = page.locator("aside").last
        for agent in ("cici咪", "coco咪", "soso咪"):
            expect(stats_panel.get_by_text(agent, exact=True)).to_be_visible()
        expect(stats_panel.get_by_text("1 tasks").first).to_be_visible()

        expect(stats_panel.get_by_text("Weekly Summary")).to_be_visible()
        expect(stats_panel.get_by_text("Tasks Done")).to_be_visible()

    def test_stats_api_returns_agent_metrics(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/stats", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        assert "agents" in data
        for name in ("cici咪", "coco咪", "soso咪"):
            assert name in data["agents"]
            agent = data["agents"][name]
            assert "total_tokens" in agent
            assert "tool_calls" in agent
            if agent.get("total_calls", 0) > 0:
                assert "success_rate" in agent

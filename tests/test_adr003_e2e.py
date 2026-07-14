"""
Playwright E2E tests for ADR-003 real CLI workflow UI (Issue #23).

Covers ChatMessage kinds, approval cards, @mention routing, session manager,
agent status bar, and task panel columns.

Run:
  pytest tests/test_adr003_e2e.py -v
"""

from __future__ import annotations

import threading
import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import (
    MOCK_AGENT_REPLY,
    broadcast_ws,
    seed_task_table,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

INPUT_PLACEHOLDER = "发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)"


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)
    expect(page.locator("header")).to_contain_text("Connected", timeout=timeout)


def _textarea(page: Page):
    return page.get_by_placeholder(INPUT_PLACEHOLDER)


def _send(page: Page, content: str, timeout: float = 15_000) -> None:
    ta = _textarea(page)
    expect(ta).to_be_enabled(timeout=10_000)
    ta.fill(content)
    send_btn = page.get_by_role("button", name="Send")
    expect(send_btn).to_be_enabled(timeout=5_000)
    send_btn.click()
    expect(page.get_by_text(content).last).to_be_visible(timeout=timeout)
    expect(page.get_by_text("Sending")).to_have_count(0, timeout=timeout)


def _agent_bubble(page: Page, agent: str):
    return page.locator(".justify-start").filter(has_text=agent)


def _submit_api_task(api_url: str, payload: dict) -> None:
    httpx.post(f"{api_url}/api/tasks", json=payload, timeout=60.0).raise_for_status()


class TestChatMessageKinds:
    """ChatMessage renders all five ADR-003 message kinds."""

    def test_human_agent_system_thinking_approval(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        expect(page.get_by_text("欢迎来到 TeamChat")).to_be_visible(timeout=10_000)

        token = uuid.uuid4().hex[:8]
        _send(page, f"@coco咪 E2E kinds {token}")
        expect(page.locator(".justify-end").filter(has_text="你").last).to_be_visible()
        expect(
            _agent_bubble(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY).last
        ).to_be_visible(timeout=20_000)

        think_id = f"think-{uuid.uuid4().hex[:8]}"
        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": think_id,
                    "kind": "thinking",
                    "agent": "cici咪",
                    "content": "E2E thinking trace content",
                    "timestamp": "2026-07-14T12:00:00Z",
                },
            },
        )
        thinking = page.locator("details").filter(has_text="THINKING").last
        expect(thinking).to_be_visible(timeout=10_000)

        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": f"apr-{uuid.uuid4().hex[:8]}",
                    "kind": "approval",
                    "agent": "cici咪",
                    "tool_name": "Bash",
                    "tool_input": {"command": "git push origin feature/test"},
                    "timestamp": "2026-07-14T12:00:01Z",
                },
            },
        )
        expect(page.get_by_text("Bash")).to_be_visible(timeout=10_000)
        expect(page.get_by_role("button", name="Allow")).to_be_visible()
        expect(page.get_by_role("button", name="Deny")).to_be_visible()


class TestApprovalCard:
    def test_allow_and_deny_remove_card(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": f"apr-{uuid.uuid4().hex[:8]}",
                    "kind": "approval",
                    "agent": "cici咪",
                    "tool_name": "Write",
                    "tool_input": {"path": "/tmp/e2e.txt"},
                    "timestamp": "2026-07-14T12:00:02Z",
                },
            },
        )
        allow_btn = page.get_by_role("button", name="Allow")
        expect(allow_btn).to_be_visible(timeout=10_000)
        allow_btn.click()
        expect(page.get_by_text("已允许工具执行")).to_be_visible(timeout=5_000)
        expect(page.get_by_role("button", name="Allow")).to_have_count(0)

        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": f"apr-{uuid.uuid4().hex[:8]}",
                    "kind": "approval",
                    "agent": "coco咪",
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf /"},
                    "timestamp": "2026-07-14T12:00:03Z",
                },
            },
        )
        deny_btn = page.get_by_role("button", name="Deny")
        expect(deny_btn).to_be_visible(timeout=10_000)
        deny_btn.click()
        expect(page.get_by_text("已拒绝工具执行")).to_be_visible(timeout=5_000)


class TestMentionRouting:
    def test_mention_routes_to_target_agent_only(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        token = uuid.uuid4().hex[:8]
        soso_before = _agent_bubble(page, "soso咪").filter(has_text=MOCK_AGENT_REPLY).count()
        coco_before = _agent_bubble(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY).count()
        _send(page, f"@soso咪 ADR003 mention route {token}")

        expect(
            _agent_bubble(page, "soso咪").filter(has_text=MOCK_AGENT_REPLY).last
        ).to_be_visible(timeout=30_000)
        expect(_agent_bubble(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY)).to_have_count(
            coco_before, timeout=10_000
        )


class TestSessionManager:
    def test_switch_and_create_session(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        page.get_by_role("button", name="TeamChat develop").click()
        expect(page.get_by_role("heading", name="Session Manager")).to_be_visible()

        page.locator("div").filter(has_text="New experiment").get_by_role("button", name="Switch").click()
        expect(page.get_by_text("New experiment")).to_be_visible()
        expect(page.get_by_role("button", name="✓ Current")).to_be_visible()

        session_name = f"E2E Session {uuid.uuid4().hex[:6]}"
        page.get_by_placeholder("Session name").fill(session_name)
        page.get_by_placeholder("Absolute directory path").fill("/tmp/teamchat-e2e")
        page.get_by_role("button", name="Create").click()
        expect(page.get_by_text(session_name)).to_be_visible(timeout=5_000)


class TestAgentStatusBar:
    def test_agent_busy_indicator_on_task_start(self, page: Page, e2e_servers):
        api_url = e2e_servers["api_url"]
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        token = uuid.uuid4().hex[:8]
        worker = threading.Thread(
            target=_submit_api_task,
            args=(api_url, {"agent": "cici咪", "prompt": f"status bar test {token}"}),
            daemon=True,
        )
        worker.start()

        left_aside = page.locator("aside").first
        cici_card = left_aside.locator("h3").filter(has_text="cici咪").locator("..")
        expect(cici_card.locator(".status-dot.busy")).to_be_visible(timeout=10_000)
        worker.join(timeout=60)


class TestTaskPanelColumns:
    def test_pending_running_done_columns(self, page: Page, e2e_servers, e2e_app):
        api_url = e2e_servers["api_url"]
        pending_marker = f"PENDING_{uuid.uuid4().hex[:8]}"
        done_marker = f"DONE_{uuid.uuid4().hex[:8]}"
        running_marker = f"RUN_{uuid.uuid4().hex[:8]}"

        seed_task_table(e2e_app, agent="coco咪", title=pending_marker, status="pending")
        seed_task_table(e2e_app, agent="soso咪", title=done_marker, status="done")

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        task_panel = page.locator("aside").filter(has=page.get_by_text("Tasks", exact=True))
        expect(task_panel.get_by_text(pending_marker)).to_be_visible(timeout=10_000)
        expect(task_panel.get_by_text(done_marker)).to_be_visible(timeout=10_000)

        worker = threading.Thread(
            target=_submit_api_task,
            args=(
                api_url,
                {"agent": "coco咪", "prompt": f"running column {running_marker}"},
            ),
            daemon=True,
        )
        worker.start()
        expect(task_panel.get_by_text(running_marker)).to_be_visible(timeout=15_000)
        worker.join(timeout=60)

        page.reload()
        _wait_connected(page)
        task_panel = page.locator("aside").filter(has=page.get_by_text("Tasks", exact=True))
        expect(task_panel.get_by_text(running_marker)).to_be_visible(timeout=15_000)


class TestTaskTableApi:
    def test_task_table_dependency_api(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        first = httpx.post(
            f"{api_url}/api/tasks/table",
            json={"agent": "coco咪", "title": "Step A", "depends_on": []},
            timeout=10.0,
        )
        first.raise_for_status()
        first_id = first.json()["id"]

        second = httpx.post(
            f"{api_url}/api/tasks/table",
            json={"agent": "soso咪", "title": "Step B", "depends_on": [first_id]},
            timeout=10.0,
        )
        second.raise_for_status()
        assert second.json()["depends_on"] == [first_id]

        listed = httpx.get(f"{api_url}/api/tasks/table", timeout=10.0)
        listed.raise_for_status()
        titles = [row["title"] for row in listed.json()]
        assert "Step A" in titles
        assert "Step B" in titles

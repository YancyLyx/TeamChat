"""
Playwright E2E tests for the TeamChat chat-room Dashboard (ADR-002).

Run:
  pytest tests/test_chat.py -v
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import MOCK_AGENT_REPLY, MOCK_GREETING_REPLY_SUFFIX, seed_session

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

AGENT_NAMES = ("cici咪", "coco咪", "soso咪")


def _goto_chat(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")


def _wait_chat_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _chat_textarea(page: Page):
    return page.get_by_placeholder("发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)")


def _send_chat_message(page: Page, content: str, timeout: float = 15_000) -> None:
    textarea = _chat_textarea(page)
    expect(textarea).to_be_enabled(timeout=10_000)
    textarea.fill(content)
    send_btn = page.get_by_role("button", name="Send")
    expect(send_btn).to_be_enabled(timeout=5_000)
    send_btn.click()
    expect(page.get_by_text(content).last).to_be_visible(timeout=timeout)
    expect(page.get_by_text("Sending")).to_have_count(0, timeout=timeout)


def _agent_reply(page: Page, agent_name: str):
    return page.locator(".justify-start").filter(has_text=agent_name)


class TestGreetingBroadcast:
    def test_greeting_triggers_three_agent_replies(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        _send_chat_message(page, "大家好")

        for agent in AGENT_NAMES:
            bubble = _agent_reply(page, agent).filter(has_text=MOCK_GREETING_REPLY_SUFFIX).last
            expect(bubble).to_be_visible(timeout=30_000)


class TestChatMentionFlow:
    def test_mention_message_sent_via_input(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        task_text = "say hello in one sentence"
        message = f"@coco咪 {task_text}"
        _send_chat_message(page, message)

        human_bubble = page.locator("div.flex.justify-end.mb-3").filter(has_text="你").last
        expect(human_bubble).to_be_visible(timeout=10_000)
        expect(human_bubble).to_contain_text("@coco咪")
        expect(human_bubble).to_contain_text(task_text)

    def test_mention_only_target_agent_replies(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        token = uuid.uuid4().hex[:8]
        coco_before = _agent_reply(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY).count()
        cici_before = _agent_reply(page, "cici咪").filter(has_text=MOCK_AGENT_REPLY).count()
        soso_before = _agent_reply(page, "soso咪").filter(has_text=MOCK_AGENT_REPLY).count()
        _send_chat_message(page, f"@coco咪 E2E target only {token}")

        expect(
            _agent_reply(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY).last
        ).to_be_visible(timeout=30_000)
        expect(_agent_reply(page, "cici咪").filter(has_text=MOCK_AGENT_REPLY)).to_have_count(
            cici_before, timeout=10_000
        )
        expect(_agent_reply(page, "soso咪").filter(has_text=MOCK_AGENT_REPLY)).to_have_count(
            soso_before, timeout=10_000
        )


class TestChatWithoutMention:
    def test_no_mention_routes_through_cici_analysis(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        unique = f"what is teamchat status {uuid.uuid4().hex[:8]}"
        _send_chat_message(page, unique)

        expect(page.get_by_text(unique).last).to_be_visible(timeout=10_000)
        expect(
            _agent_reply(page, "cici咪").filter(has_text="三只猫在线").last
        ).to_be_visible(timeout=20_000)

    def test_input_disabled_when_websocket_offline(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        page.context.set_offline(True)
        expect(page.get_by_text("已断开")).to_be_visible(timeout=20_000)
        expect(_chat_textarea(page)).to_be_disabled(timeout=10_000)


class TestSessionTagFiltering:
    def test_chat_history_excludes_test_tag_sessions(self, page: Page, e2e_servers, e2e_app):
        test_marker = f"E2E_TEST_TAG_{uuid.uuid4().hex[:8]}"
        prod_marker = f"E2E_PROD_TAG_{uuid.uuid4().hex[:8]}"

        seed_session(
            e2e_app,
            agent_name="coco咪",
            prompt=test_marker,
            output="test-only output",
            tag="test",
        )
        seed_session(
            e2e_app,
            agent_name="coco咪",
            prompt=prod_marker,
            output="prod output visible",
            tag="prod",
        )

        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        chat_main = page.locator("main")
        expect(chat_main.get_by_text(prod_marker)).to_be_visible(timeout=10_000)
        expect(chat_main.get_by_text(test_marker)).to_have_count(0)


class TestCollapsibleSections:
    def test_thinking_and_tool_calls_are_collapsible(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        _send_chat_message(page, "@coco咪 E2E_COLLAPSE show details")

        agent_bubble = _agent_reply(page, "coco咪").last
        expect(agent_bubble.locator("details").filter(has_text="THINKING")).to_be_visible(timeout=30_000)
        expect(agent_bubble.locator("details").filter(has_text="TOOL_CALLS")).to_be_visible()

        expect(agent_bubble).to_contain_text(MOCK_AGENT_REPLY)

        tool_calls = agent_bubble.locator("details").filter(has_text="TOOL_CALLS")
        tool_calls.locator("summary").click()
        expect(agent_bubble.get_by_text(MOCK_AGENT_REPLY)).to_be_visible()


class TestContinueContext:
    def test_second_mention_uses_continue_session(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        _send_chat_message(page, "@coco咪 first message")
        expect(
            _agent_reply(page, "coco咪").filter(has_text=MOCK_AGENT_REPLY).last
        ).to_be_visible(timeout=20_000)

        _send_chat_message(page, "@coco咪 second message")
        expect(
            _agent_reply(page, "coco咪").filter(has_text="[continue]").last
        ).to_be_visible(timeout=20_000)


class TestChatApiTagQuery:
    def test_sessions_api_filters_by_tag(self, e2e_servers, e2e_app):
        api_url = e2e_servers["api_url"]
        marker = f"API_TAG_{uuid.uuid4().hex[:8]}"
        seed_session(
            e2e_app,
            agent_name="soso咪",
            prompt=marker,
            output="tagged test row",
            tag="test",
        )

        prod_resp = httpx.get(f"{api_url}/api/sessions", params={"tag": "prod", "limit": 50})
        test_resp = httpx.get(f"{api_url}/api/sessions", params={"tag": "test", "limit": 50})
        prod_resp.raise_for_status()
        test_resp.raise_for_status()

        prod_prompts = [row["prompt"] for row in prod_resp.json()]
        test_prompts = [row["prompt"] for row in test_resp.json()]

        assert marker not in prod_prompts
        assert marker in test_prompts

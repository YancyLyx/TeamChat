"""
Playwright E2E tests for the TeamChat chat-room Dashboard.

Run:
  pytest tests/test_chat.py -v
"""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import MOCK_AGENT_REPLY

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

NO_MENTION_HINT = "消息已收到。使用 @cici咪 @coco咪 @soso咪 指定目标 agent。"


def _goto_chat(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")


def _wait_chat_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _chat_textarea(page: Page):
    return page.get_by_placeholder("发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)")


def _send_chat_message(page: Page, content: str) -> None:
    textarea = _chat_textarea(page)
    expect(textarea).to_be_enabled(timeout=10_000)
    textarea.fill(content)
    page.get_by_role("button", name="发送").click()


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

    def test_agent_reply_appears_in_chat_area(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        token = uuid.uuid4().hex[:8]
        _send_chat_message(page, f"@soso咪 E2E reply test {token}")

        agent_bubble = page.locator(".justify-start").filter(has_text="soso咪").filter(
            has_text=MOCK_AGENT_REPLY
        ).last
        expect(agent_bubble).to_be_visible(timeout=20_000)
        expect(agent_bubble).to_contain_text(MOCK_AGENT_REPLY)


class TestChatWithoutMention:
    def test_no_mention_shows_routing_hint(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        unique = f"plain message {uuid.uuid4().hex[:8]}"
        _send_chat_message(page, unique)

        expect(page.get_by_text(unique).last).to_be_visible(timeout=10_000)
        expect(page.get_by_text(NO_MENTION_HINT)).to_be_visible(timeout=10_000)

    def test_input_disabled_when_websocket_offline(self, page: Page, e2e_servers):
        _goto_chat(page, e2e_servers["dashboard_url"])
        _wait_chat_connected(page)

        page.context.set_offline(True)
        expect(page.get_by_text("已断开")).to_be_visible(timeout=20_000)
        expect(_chat_textarea(page)).to_be_disabled(timeout=10_000)

"""Tests for PR #90 — Markdown rendering + XSS hardening."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import broadcast_ws

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[1]


class TestMarkdownUnit:
    def test_node_markdown_security_checks(self):
        script = ROOT / "dashboard" / "scripts" / "verify-markdown.mjs"
        proc = subprocess.run(
            ["node", str(script)],
            cwd=ROOT / "dashboard",
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestMarkdownRenderE2E:
    def test_agent_bubble_renders_markdown_bold(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        marker = f"md-bold-{uuid.uuid4().hex[:8]}"
        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": f"md-{marker}",
                    "kind": "agent",
                    "agent": "coco咪",
                    "content": f"**{marker}**",
                    "timestamp": "2026-07-18T12:00:00Z",
                },
            },
        )
        bubble = page.locator(".justify-start").filter(has_text="coco咪").last
        expect(bubble.locator("strong").filter(has_text=marker)).to_be_visible(timeout=10_000)

    def test_xss_payload_does_not_execute(self, page: Page, e2e_servers, e2e_app):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        payload = '<img src=x onerror="window.__teamchat_xss=1">'
        broadcast_ws(
            e2e_app,
            {
                "type": "chat_message",
                "data": {
                    "id": f"xss-{uuid.uuid4().hex[:8]}",
                    "kind": "agent",
                    "agent": "cici咪",
                    "content": payload,
                    "timestamp": "2026-07-18T12:00:01Z",
                },
            },
        )
        expect(page.locator(".justify-start").filter(has_text="cici咪").last).to_be_visible(timeout=10_000)
        page.wait_for_timeout(500)
        assert page.evaluate("window.__teamchat_xss") is None

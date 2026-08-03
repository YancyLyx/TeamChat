"""
E2E/API tests for PR #54 (stats tokens), #55 (WS dedup), #56 (paste upload).

Run:
  pytest tests/test_pr54_56_e2e.py -v
"""

from __future__ import annotations

import io

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


class TestStatsTokenApi:
    """PR #54 — enriched /api/stats with token + tool_calls."""

    def test_stats_api_returns_token_and_tool_fields(self, e2e_servers, e2e_app):
        seed_session(
            e2e_app,
            agent_name="coco咪",
            prompt="stats token e2e",
            output="done",
            tag="prod",
            token_usage={"input_tokens": 40, "output_tokens": 20},
        )

        def _patch_tools() -> None:
            row = e2e_app.state.store.get_recent(limit=1)[0]
            e2e_app.state.store.conn.execute(
                "UPDATE agent_calls SET tool_calls = ? WHERE id = ?",
                ('[{"name": "read_file", "status": "ok"}]', row.id),
            )
            e2e_app.state.store.conn.commit()

        e2e_app.state.loop.call_soon_threadsafe(_patch_tools)
        import time
        time.sleep(0.15)

        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/stats", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        assert "token_grand_total" in data
        assert data["token_grand_total"] >= 60
        coco = data["agents"]["coco咪"]
        assert coco["input_tokens"] >= 40
        assert coco["output_tokens"] >= 20
        assert coco["total_tokens"] >= 60
        assert coco["tool_calls"] >= 1
        assert "read_file" in coco.get("tools_by_name", {})

    def test_stats_panel_shows_token_metrics(self, page: Page, e2e_servers, e2e_app):
        seed_session(
            e2e_app,
            agent_name="coco咪",
            prompt="panel token seed",
            output="ok",
            tag="prod",
            token_usage={"input_tokens": 10, "output_tokens": 5},
        )
        api_url = e2e_servers["api_url"]
        resp = httpx.get(f"{api_url}/api/stats", timeout=10.0)
        resp.raise_for_status()
        expected_tokens = resp.json()["agents"]["coco咪"]["total_tokens"]
        assert expected_tokens >= 15

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        right_aside = page.locator("aside").last
        right_aside.get_by_role("button", name="Stats", exact=True).click()
        stats_panel = page.locator("aside").last
        expect(stats_panel.get_by_role("button", name="L1 效能")).to_be_visible(timeout=10_000)
        stats_panel.get_by_role("button", name="L1 效能").click()
        expect(stats_panel.get_by_text(f"{expected_tokens} tokens", exact=True)).to_be_visible(timeout=10_000)


class TestWsDedup:
    """PR #55 — duplicate connected/system events should not flood chat."""

    def test_single_connected_banner_in_chat(self, page: Page, e2e_servers):
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=10_000)
        assert page.get_by_text("已连接 TeamChat 实时通道").count() <= 1


class TestUploadApi:
    """PR #56 — POST /api/upload for clipboard paste."""

    def test_upload_png_returns_path(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        resp = httpx.post(
            f"{api_url}/api/upload",
            files={"file": ("paste-screenshot.png", io.BytesIO(png_bytes), "image/png")},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        assert data["path"].startswith("/tmp/teamchat-")
        assert data["name"] == "paste-screenshot.png"
        assert data["size"] == len(png_bytes)

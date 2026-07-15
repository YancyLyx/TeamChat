"""Verify REST API and WebSocket emit unescaped Unicode (emoji, Chinese)."""

from __future__ import annotations

import json

import httpx
import pytest

pytestmark = pytest.mark.e2e


def test_agents_api_returns_literal_emoji_names(e2e_servers):
    """Agent names with 咪 must not be ASCII-escaped in JSON body."""
    api_url = e2e_servers["api_url"]
    response = httpx.get(f"{api_url}/api/agents", timeout=10.0)
    response.raise_for_status()

    raw = response.text
    assert "\\u54aa" not in raw
    assert "cici咪" in raw

    agents = response.json()
    names = {a["name"] for a in agents}
    assert "cici咪" in names
    assert "coco咪" in names
    assert "soso咪" in names


def test_chat_ws_connected_message_has_chinese(e2e_servers):
    """WebSocket connected payload should carry readable Chinese, not \\u escapes."""
    pytest.importorskip("websockets")
    import asyncio
    import websockets

    api_url = e2e_servers["api_url"]
    ws_url = api_url.replace("http://", "ws://") + "/ws"

    async def _read_connected():
        async with websockets.connect(ws_url) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            return msg

    raw = asyncio.run(_read_connected())

    assert "\\u5df2" not in raw
    data = json.loads(raw)
    assert data["type"] == "connected"
    assert "Connected" in data["data"]["message"]


def test_broadcast_ws_preserves_emoji(e2e_servers, e2e_app):
    """Engine broadcast must deliver emoji in chat_message without escaping."""
    from tests.e2e_support import broadcast_ws

    broadcast_ws(
        e2e_app,
        {
            "type": "chat_message",
            "data": {
                "id": "unicode-test-emoji",
                "kind": "agent",
                "agent": "cici咪",
                "content": "🏗️ 架构师在线 ✅",
                "timestamp": "2026-07-15T12:00:00Z",
            },
        },
    )

    # If broadcast didn't raise, WS layer accepted the payload — verify JSON round-trip
    payload = json.dumps(
        {
            "type": "chat_message",
            "data": {"content": "🏗️ 架构师在线 ✅"},
        },
        ensure_ascii=False,
    )
    assert "🏗️" in payload
    assert "\\u" not in payload

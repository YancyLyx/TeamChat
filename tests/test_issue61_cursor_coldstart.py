"""
Tests for Issue #61 — Cursor cold-start session ID capture.

Run:
  pytest tests/test_issue61_cursor_coldstart.py -v
"""

from __future__ import annotations

import httpx
import pytest
import uuid
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestCursorColdStartBinding:
    def test_greeting_captures_cursor_id_on_blank_session(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        scope_dir = f"/tmp/issue61-cursor-{uuid.uuid4().hex[:8]}"
        Path(scope_dir).mkdir(parents=True, exist_ok=True)

        created = httpx.post(
            f"{api_url}/api/session-manager",
            json={"name": "Issue61 Cursor", "directory": scope_dir},
            timeout=10.0,
        ).json()
        sid = created["id"]

        httpx.patch(
            f"{api_url}/api/session-manager/{sid}",
            json={"claude_id": "", "codex_id": "", "cursor_id": ""},
            timeout=10.0,
        ).raise_for_status()

        httpx.post(
            f"{api_url}/api/chat",
            json={"content": "大家好", "teamchat_session_id": sid},
            timeout=60.0,
        ).raise_for_status()

        row = httpx.get(f"{api_url}/api/session-manager/{sid}", timeout=10.0).json()
        assert row["cursor_id"] == "e2e-cursor-coldstart", (
            f"cursor_id not captured: {row['cursor_id']!r}"
        )

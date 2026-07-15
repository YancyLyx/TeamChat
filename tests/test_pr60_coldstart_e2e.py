"""
E2E/API tests for PR #60 — cold-start CLI session ID binding (#59).

Run:
  pytest tests/test_pr60_coldstart_e2e.py -v
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestColdStartSessionBinding:
    def test_greeting_captures_cli_ids_for_blank_session(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        scope_dir = f"/tmp/pr60-coldstart-{uuid.uuid4().hex[:8]}"
        Path(scope_dir).mkdir(parents=True, exist_ok=True)

        created = httpx.post(
            f"{api_url}/api/session-manager",
            json={"name": "PR60 Cold Start", "directory": scope_dir},
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
        assert row["claude_id"] == "e2e-claude-coldstart"
        assert row["codex_id"] == "e2e-codex-coldstart"
        assert row["cursor_id"] == "e2e-cursor-coldstart"

    def test_resume_uses_stored_session_id(self, tmp_path):
        from engine.config import Config, AGENT_COCO
        from engine.session_store import SessionStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = SessionStore(config)
        ss.init()
        created = ss.create("Resume Test", str(tmp_path))
        stored = "019f40ef-e8cf-76f0-8b49-6691cc7275f3"
        ss.set_agent_session_id(created.id, "codex", stored)

        cmd = config.get_cli_command(
            AGENT_COCO, "hello", session_id=ss.get_agent_session_id(created.id, "codex"),
        )
        assert stored in cmd
        assert "resume" in cmd
        ss.close()

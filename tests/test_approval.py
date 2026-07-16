"""Tests for POST /api/approval (ADR-003 §3.5, PR #80)."""

from __future__ import annotations

import json

import httpx
import pytest

from api.routes import approval as approval_mod
from engine.config import AGENT_CICI, Config


class MockStdinWriter:
    """Minimal asyncio.StreamWriter stand-in for approval tests."""

    def __init__(self):
        self.chunks: list[bytes] = []
        self._closed = False

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self._closed


@pytest.fixture(autouse=True)
def clear_pending_approvals():
    approval_mod._pending_approvals.clear()
    yield
    approval_mod._pending_approvals.clear()


class TestBuildControlResponse:
    def test_allow_shape_matches_adr(self):
        raw = approval_mod.build_control_response("req-1", "allow")
        payload = json.loads(raw)
        assert payload["type"] == "control_response"
        assert payload["response"]["request_id"] == "req-1"
        assert payload["response"]["response"]["behavior"] == "allow"

    def test_deny_includes_message(self):
        raw = approval_mod.build_control_response("req-2", "deny")
        payload = json.loads(raw)
        assert payload["response"]["response"]["behavior"] == "deny"
        assert "denied" in payload["response"]["response"]["message"].lower()


class TestApprovalEndpoint:
    def test_unknown_request_returns_404(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "missing-id", "decision": "allow"},
            timeout=10.0,
        )
        assert resp.status_code == 404

    def test_invalid_decision_returns_422(self, e2e_servers):
        api_url = e2e_servers["api_url"]
        resp = httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "req-x", "decision": "maybe"},
            timeout=10.0,
        )
        assert resp.status_code == 422

    def test_allow_writes_control_response_to_stdin(self, e2e_servers):
        writer = MockStdinWriter()
        approval_mod.register_approval("req-allow", writer)

        api_url = e2e_servers["api_url"]
        resp = httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "req-allow", "decision": "allow"},
            timeout=10.0,
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "allow"
        assert len(writer.chunks) == 1
        payload = json.loads(writer.chunks[0].decode())
        assert payload["response"]["response"]["behavior"] == "allow"
        assert "req-allow" not in approval_mod._pending_approvals

    def test_deny_writes_deny_response(self, e2e_servers):
        writer = MockStdinWriter()
        approval_mod.register_approval("req-deny", writer)

        api_url = e2e_servers["api_url"]
        resp = httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "req-deny", "decision": "deny"},
            timeout=10.0,
        )
        assert resp.status_code == 200
        payload = json.loads(writer.chunks[0].decode())
        assert payload["response"]["response"]["behavior"] == "deny"

    def test_second_submit_returns_404(self, e2e_servers):
        writer = MockStdinWriter()
        approval_mod.register_approval("req-once", writer)
        api_url = e2e_servers["api_url"]
        httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "req-once", "decision": "allow"},
            timeout=10.0,
        ).raise_for_status()
        resp = httpx.post(
            f"{api_url}/api/approval",
            json={"request_id": "req-once", "decision": "allow"},
            timeout=10.0,
        )
        assert resp.status_code == 404


class TestClaudeAcceptEditsConfig:
    def test_claude_templates_include_accept_edits(self):
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
        )
        cmd = config.get_cli_command(AGENT_CICI, "hello")
        assert "--permission-mode" in cmd
        assert "acceptEdits" in cmd

        resume = config.get_cli_command(AGENT_CICI, "hello", session_id="sess-123")
        assert "acceptEdits" in resume

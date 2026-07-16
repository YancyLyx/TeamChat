"""Tests for Claude line-by-line stdout + approval event wiring (PR #86)."""

from __future__ import annotations

import asyncio
import json

import pytest

from api.routes import approval as approval_mod
from engine.config import AGENT_CICI, Config
from engine.runner import AgentRunner
from tests.test_approval import MockStdinWriter


@pytest.fixture(autouse=True)
def clear_pending_approvals():
    approval_mod._pending_approvals.clear()
    yield
    approval_mod._pending_approvals.clear()


class TestRegisterApprovalEvent:
    def test_register_returns_same_event_as_pending_store(self):
        writer = MockStdinWriter()
        event = approval_mod.register_approval("req-sync", writer, {"type": "control_request"})
        assert event is approval_mod._pending_approvals["req-sync"][1]

    @pytest.mark.asyncio
    async def test_api_approval_unblocks_registered_event(self, e2e_servers):
        writer = MockStdinWriter()
        event = approval_mod.register_approval("req-wait", writer)

        async def resolve_via_api() -> None:
            await asyncio.sleep(0.05)
            import httpx
            api_url = e2e_servers["api_url"]
            httpx.post(
                f"{api_url}/api/approval",
                json={"request_id": "req-wait", "decision": "allow"},
                timeout=10.0,
            ).raise_for_status()

        waiter = asyncio.create_task(asyncio.wait_for(event.wait(), timeout=2))
        resolver = asyncio.create_task(resolve_via_api())
        await asyncio.gather(waiter, resolver)
        assert len(writer.chunks) == 1


class TestReadClaudeStream:
    @pytest.mark.asyncio
    async def test_waits_on_register_event_not_local_copy(self):
        lines = [
            '{"type":"control_request","request_id":"req-stream","request":{"tool_name":"Bash","input":{"command":"ls"}}}\n',
            '{"type":"result","result":"ok"}\n',
        ]

        class MockReader:
            def __init__(self, payload: list[str]):
                self._payload = [p.encode("utf-8") for p in payload]
                self._idx = 0

            async def readline(self) -> bytes:
                if self._idx >= len(self._payload):
                    return b""
                data = self._payload[self._idx]
                self._idx += 1
                return data

        class MockProcess:
            def __init__(self):
                self.stdout = MockReader(lines)
                self.stderr = MockReader([])
                self.stdin = MockStdinWriter()
                self._returncode = 0

            async def wait(self) -> int:
                return self._returncode

        async def approve_mid_stream(agent, request_id, evt) -> None:
            await asyncio.sleep(0.02)
            entry = approval_mod._pending_approvals.get(request_id)
            assert entry is not None
            _, event = entry
            payload = approval_mod.build_control_response(request_id, "allow")
            entry[0].write(payload.encode("utf-8"))
            await entry[0].drain()
            event.set()
            approval_mod.clear_approval(request_id)

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
        )
        runner = AgentRunner(config)
        runner.approval_notifier = approve_mid_stream

        stdout, _stderr = await runner._read_claude_stream(MockProcess(), timeout=5, agent=AGENT_CICI)
        text = stdout.decode("utf-8")
        assert "control_request" in text
        assert "result" in text
        assert "req-stream" not in approval_mod._pending_approvals

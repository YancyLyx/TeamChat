"""
Integration tests for the TeamChat AgentRunner CLI driver layer.

Run all tests:  python -m pytest tests/ -v
Run fast only: python -m pytest tests/ -v -m "not slow"
"""

import asyncio
import json
import os
import shutil
import subprocess

import pytest

from engine.config import (
    AGENT_CICI,
    AGENT_COCO,
    AGENT_SOSO,
    ALL_AGENTS,
)
from engine.runner import AgentRunner, AgentTask, create_runner
from tests.conftest import (
    CLI_BINARY_NAMES,
    HELLO_PROMPT,
    IntegrationTestConfig,
    run_cli_version_check,
    skip_if_cli_missing,
    skip_if_not_ready_for_real_call,
)


class TestCliDetection:
    """Verify agent CLIs are discoverable on PATH."""

    def test_claude_cli_responds(self):
        skip_if_cli_missing(AGENT_CICI)
        result = run_cli_version_check("claude", "--version")
        if result.returncode != 0:
            result = run_cli_version_check("claude", "--help")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() or result.stderr.strip()

    def test_codex_cli_responds(self):
        skip_if_cli_missing(AGENT_COCO)
        result = run_cli_version_check("codex", "--version")
        if result.returncode != 0:
            result = run_cli_version_check("codex", "--help")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() or result.stderr.strip()

    def test_cursor_agent_exists_and_executable(self):
        skip_if_cli_missing(AGENT_SOSO)
        path = shutil.which("cursor-agent")
        assert path is not None
        assert os.access(path, os.X_OK)

    @pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.cli)
    def test_config_cli_templates_match_known_binaries(self, agent):
        skip_if_cli_missing(agent)
        binary = CLI_BINARY_NAMES[agent.cli]
        assert shutil.which(binary) is not None


class TestRealCliInvocation:
    """End-to-end CLI calls through AgentRunner."""

    @pytest.mark.slow
    @pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.cli)
    async def test_agent_hello_prompt(self, runner, agent):
        skip_if_not_ready_for_real_call(agent)
        task = AgentTask(prompt=HELLO_PROMPT, timeout_seconds=120)
        result = await runner.run(agent, task)

        assert result.exit_code == 0, result.output
        assert result.output.strip(), "stdout should not be empty"
        assert result.duration_ms >= 0
        assert result.started_at
        assert result.finished_at

    @pytest.mark.slow
    async def test_timeout_with_generous_limit(self, runner):
        """Simple prompt completes within a 10s timeout."""
        skip_if_not_ready_for_real_call(AGENT_CICI)
        task = AgentTask(prompt=HELLO_PROMPT, timeout_seconds=10)
        result = await runner.run(AGENT_CICI, task)

        assert "TIMEOUT" not in result.output
        assert result.exit_code == 0 or result.duration_ms <= 10_000


class TestErrorHandling:
    """Runner behavior for invalid inputs and failure modes."""

    async def test_missing_cli_path_raises(self):
        test_config = IntegrationTestConfig(
            command_builder=lambda agent, prompt: [
                "/nonexistent/teamchat/cli/binary",
                prompt,
            ],
        )
        runner = AgentRunner(test_config)

        with pytest.raises(FileNotFoundError):
            await runner.run(AGENT_CICI, AgentTask(prompt=HELLO_PROMPT))

    async def test_short_timeout_triggers_timeout(self):
        test_config = IntegrationTestConfig(
            command_builder=lambda agent, prompt: ["sleep", "30"],
        )
        runner = AgentRunner(test_config)

        result = await runner.run(
            AGENT_CICI,
            AgentTask(prompt=HELLO_PROMPT, timeout_seconds=1),
        )

        assert result.exit_code == -1
        assert "TIMEOUT" in result.output
        assert result.duration_ms == 1000

    @pytest.mark.slow
    @pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.cli)
    async def test_empty_prompt_handled(self, runner, agent):
        skip_if_not_ready_for_real_call(agent)
        result = await runner.run(agent, AgentTask(prompt="", timeout_seconds=30))
        assert isinstance(result.output, str)
        assert result.exit_code is not None


class TestOutputParsing:
    """Claude JSON output parsing and token usage extraction."""

    @staticmethod
    def _make_fake_process(stdout_data: bytes = b""):
        """claude 分支走 _read_claude_stream（逐行读 stdout）— FakeProcess 需模拟 stdout 流。"""

        class FakeStream:
            def __init__(self, data: bytes):
                self._lines = data.splitlines(keepends=True) if data else []
                self._closed = False

            async def readline(self):
                return self._lines.pop(0) if self._lines else b""

            def close(self):
                self._closed = True

        class FakeProcess:
            returncode = 0
            stdin = None

            def __init__(self, stdout_data=b""):
                self.stdout = FakeStream(stdout_data)
                self.stderr = FakeStream(b"")

            async def communicate(self):
                return b"", b""

            async def kill(self):
                pass

            async def wait(self):
                pass

        return FakeProcess(stdout_data)

    async def test_claude_json_output_parsed(self, monkeypatch):
        runner = AgentRunner(IntegrationTestConfig())
        # stream-json 事件格式（runner 现在按事件解析）：assistant 提取 text，result 提取 usage
        payload = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello from Claude!"}]}},
            {"type": "result", "usage": {"input_tokens": 12, "output_tokens": 7}},
        ]
        raw = "\n".join(json.dumps(p) for p in payload)

        async def fake_exec(*args, **kwargs):
            return self._make_fake_process(raw.encode("utf-8"))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        result = await runner.run(AGENT_CICI, AgentTask(prompt=HELLO_PROMPT))

        assert result.output == "Hello from Claude!"
        assert result.token_usage == {
            "input_tokens": 12,
            "output_tokens": 7,
        }
        assert result.success is True

    async def test_non_json_output_kept_as_text(self, monkeypatch):
        runner = AgentRunner(IntegrationTestConfig())

        async def fake_exec(*args, **kwargs):
            return self._make_fake_process(b"plain text response\n")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        result = await runner.run(AGENT_CICI, AgentTask(prompt=HELLO_PROMPT))

        assert result.output == "plain text response"
        assert result.token_usage == {}

    @staticmethod
    def _fake_process_for_cli(cli: str) -> bytes:
        """Build a JSONL stream that exercises the per-CLI text extraction."""
        if cli == "claude":
            events = [
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "第一段"},
                ]}},
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "第二段"},
                    {"type": "tool_use", "name": "Bash", "input": {}},
                ]}},
            ]
        elif cli == "codex":
            events = [
                {"type": "item.completed", "item": {"type": "agent_message", "text": "codex第一段"}},
                {"type": "item.completed", "item": {"type": "reasoning", "text": "内部思考不流式"}},
                {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
            ]
        else:  # cursor
            events = [
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "cursor第一段"}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "cursor第二段"}]}},
            ]
        return "\n".join(json.dumps(e) for e in events).encode("utf-8")

    @pytest.mark.parametrize(
        "agent, expected_chunks",
        [
            (AGENT_CICI, ["第一段", "第二段"]),
            (AGENT_COCO, ["codex第一段"]),
            (AGENT_SOSO, ["cursor第一段", "cursor第二段"]),
        ],
        ids=["claude", "codex", "cursor"],
    )
    async def test_on_stream_receives_text_chunks(self, monkeypatch, agent, expected_chunks):
        """on_stream 回调逐段收到 agent 文本（段落级流式的基础）。"""
        runner = AgentRunner(IntegrationTestConfig())
        chunks: list[str] = []

        async def fake_exec(*args, **kwargs):
            return self._make_fake_process(self._fake_process_for_cli(agent.cli))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        result = await runner.run(
            agent, AgentTask(prompt=HELLO_PROMPT), on_stream=chunks.append,
        )

        assert chunks == expected_chunks, f"{agent.name} 流式段落不匹配"
        # 完整结果仍然解析出来（流式不影响最终输出）
        assert result.output.strip()

    @pytest.mark.slow
    async def test_claude_live_json_token_usage(self, runner):
        skip_if_not_ready_for_real_call(AGENT_CICI)
        result = await runner.run(
            AGENT_CICI,
            AgentTask(prompt=HELLO_PROMPT, timeout_seconds=120),
        )

        assert result.success
        assert result.output.strip()
        if result.token_usage:
            assert "input_tokens" in result.token_usage
            assert "output_tokens" in result.token_usage
            assert result.token_usage["input_tokens"] >= 0
            assert result.token_usage["output_tokens"] >= 0


class TestRunnerFactory:
    """Smoke check for runner factory wiring."""

    def test_create_runner_uses_default_config(self):
        runner = create_runner()
        assert runner.config.repo_name == "TeamChat"
        assert isinstance(runner, AgentRunner)

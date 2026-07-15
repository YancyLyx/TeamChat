"""
Smoke tests for the TeamChat Engine.
Run: python -m pytest tests/ -v
"""

import json

import pytest

from engine.config import (
    Config, AgentIdentity, load_config,
    AGENT_CICI, AGENT_COCO, AGENT_SOSO, ALL_AGENTS,
)
from engine.runner import AgentRunner, AgentTask, AgentResult, RunnerStats
from engine.router import Router, TaskType, DispatchResult, DEFAULT_ROUTES
from engine.bus import MessageBus, BusMessage, MessageType


class TestConfig:
    """Configuration is correct and complete."""

    def test_agent_identities(self):
        assert AGENT_CICI.name == "cici咪"
        assert AGENT_COCO.name == "coco咪"
        assert AGENT_SOSO.name == "soso咪"
        assert len(ALL_AGENTS) == 3

    def test_agent_tokens_have_env_names(self):
        assert AGENT_CICI.token_env == "TEAMCHAT_CICI_TOKEN"
        assert AGENT_COCO.token_env == "TEAMCHAT_COCO_TOKEN"
        assert AGENT_SOSO.token_env == "TEAMCHAT_SOSO_TOKEN"

    def test_cli_templates_have_all_agents(self):
        from engine.config import CLI_TEMPLATES
        assert "claude" in CLI_TEMPLATES
        assert "codex" in CLI_TEMPLATES
        assert "cursor" in CLI_TEMPLATES

    def test_codex_templates_use_json_output(self):
        from engine.config import CLI_CONTINUE_TEMPLATES, CLI_TEMPLATES
        assert "--json" in CLI_TEMPLATES["codex"]
        assert "--json" in CLI_CONTINUE_TEMPLATES["codex"]

    def test_load_config(self):
        config = load_config()
        assert config.repo_owner == "YancyLyx"
        assert config.repo_name == "TeamChat"
        assert "github.com" in config.repo_url


class TestRouter:
    """Task routing logic."""

    def test_architecture_routes_to_cici(self):
        router = Router()
        result = router.dispatch(TaskType.ARCHITECTURE)
        assert result.agent.name == "cici咪"

    def test_frontend_routes_to_coco(self):
        router = Router()
        result = router.dispatch(TaskType.FRONTEND)
        assert result.agent.name == "coco咪"

    def test_testing_routes_to_soso(self):
        router = Router()
        result = router.dispatch(TaskType.TESTING)
        assert result.agent.name == "soso咪"

    def test_direct_assignment_overrides_routing(self):
        router = Router()
        result = router.dispatch(TaskType.FRONTEND, preferred_agent=AGENT_CICI)
        assert result.agent.name == "cici咪"
        assert "Direct human assignment" in result.reason

    def test_all_task_types_have_routes(self):
        router = Router()
        for tt in TaskType:
            result = router.dispatch(tt)
            assert result.agent is not None

    def test_batch_dispatch(self):
        router = Router()
        tasks = [(TaskType.FRONTEND, None), (TaskType.TESTING, None)]
        results = router.dispatch_batch(tasks)
        assert len(results) == 2

    def test_busy_management(self):
        router = Router()
        router.mark_busy(AGENT_CICI)
        assert router.is_busy(AGENT_CICI)
        assert not router.is_busy(AGENT_COCO)
        router.mark_free(AGENT_CICI)
        assert not router.is_busy(AGENT_CICI)


class TestMessageBus:
    """Agent-to-agent messaging."""

    def test_send_and_receive(self, tmp_path):
        from engine.config import Config
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        config.messages_dir.mkdir(parents=True, exist_ok=True)

        bus = MessageBus(config)
        bus.init()

        msg = bus.send(
            from_agent=AGENT_CICI,
            to_agent=AGENT_COCO,
            msg_type=MessageType.TASK_ASSIGNMENT,
            content="请实现 WebSocket 重连 (#42)",
            github_ref="#42",
        )
        assert msg.id.startswith("msg-")
        assert msg.from_agent == "cici咪"
        assert msg.to_agent == "coco咪"

        inbox = bus.inbox(AGENT_COCO)
        assert len(inbox) >= 1
        assert inbox[0].content == "请实现 WebSocket 重连 (#42)"

    def test_broadcast(self, tmp_path):
        from engine.config import Config
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        config.teamchat_dir.mkdir(parents=True, exist_ok=True)
        config.messages_dir.mkdir(parents=True, exist_ok=True)

        bus = MessageBus(config)
        bus.init()

        bus.broadcast(AGENT_CICI, "Phase 2 开始！")
        assert len(bus.inbox(AGENT_COCO)) >= 1
        assert len(bus.inbox(AGENT_SOSO)) >= 1


class TestRunnerDataTypes:
    """AgentRunner data types are correct."""

    def test_agent_task_full_prompt(self):
        task = AgentTask(prompt="写一个 API", context="这是一个 Python 项目")
        full = task.full_prompt()
        assert "写一个 API" in full
        assert "Python 项目" in full

    def test_agent_result_success(self):
        result = AgentResult(
            agent_name="cici咪",
            task_prompt="test",
            output="done",
            exit_code=0,
            duration_ms=100,
        )
        assert result.success is True

    def test_agent_result_failure(self):
        result = AgentResult(
            agent_name="cici咪",
            task_prompt="test",
            output="error",
            exit_code=1,
            duration_ms=100,
        )
        assert result.success is False


class TestCodexEventParsing:
    """Codex JSONL output is cleaned before reaching chat bubbles."""

    def test_parse_codex_jsonl_output_uses_agent_message_only(self):
        from engine.codex_events import parse_codex_jsonl_output

        output = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "abc"}, ensure_ascii=False),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "reasoning", "text": "internal thinking"},
            }, ensure_ascii=False),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "git status", "exit_code": 0},
            }, ensure_ascii=False),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "干净回复"},
            }, ensure_ascii=False),
            json.dumps({
                "type": "turn.completed",
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }, ensure_ascii=False),
        ])

        clean_output, usage, saw_json_event = parse_codex_jsonl_output(output)

        assert saw_json_event is True
        assert clean_output == "干净回复"
        assert "internal thinking" not in clean_output
        assert "git status" not in clean_output
        assert usage == {"input_tokens": 3, "output_tokens": 2}

    def test_parse_codex_jsonl_output_supports_message_content_blocks(self):
        from engine.codex_events import parse_codex_jsonl_output

        output = json.dumps({
            "type": "item.completed",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "content block reply"}],
            },
        })

        clean_output, _, saw_json_event = parse_codex_jsonl_output(output)

        assert saw_json_event is True
        assert clean_output == "content block reply"


class TestSessionStore:
    """SQLite-backed session logging."""

    def test_init_and_log(self, tmp_path):
        from engine.config import Config
        from engine.store import SessionStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        store = SessionStore(config)
        store.init()

        row_id = store.log(
            agent_name="cici咪",
            prompt="test prompt",
            output="test output",
            exit_code=0,
            duration_ms=150,
            task_type="architecture",
        )
        assert row_id == 1

        row = store.get_by_id(1)
        assert row is not None
        assert row.agent_name == "cici咪"
        assert row.exit_code == 0
        assert row.success is True

        stats = store.stats(agent_name="cici咪")
        assert stats["total_calls"] == 1
        assert stats["total_success"] == 1

        store.close()

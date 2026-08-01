"""
Smoke tests for the TeamChat Engine.
Run: python -m pytest tests/ -v
"""

import json
import sqlite3

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
    """SQLite-backed agent call logging (unified teamchat.db)."""

    def test_init_and_log(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()

        row_id = store.log(
            agent_name="cici咪",
            prompt="test prompt",
            output="test output",
            exit_code=0,
            duration_ms=150,
            task_type="architecture",
            teamchat_session_id=1,
        )
        assert row_id == 1

        row = store.get_by_id(1)
        assert row is not None
        assert row.agent_name == "cici咪"
        assert row.teamchat_session_id == 1
        assert row.tool_calls == []
        assert row.exit_code == 0
        assert row.success is True

        stats = store.stats(agent_name="cici咪")
        assert stats["total_calls"] == 1
        assert stats["total_success"] == 1

        store.close()
        ss.close()


class TestUnifiedDbSchema:
    """ADR-003 §10 — unified teamchat.db tables, FK, indexes."""

    def test_schema_has_fk_indexes_and_tool_calls(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore
        from engine.task_table import TaskTable

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()
        tt = TaskTable(config)
        tt.init()

        indexes = {
            row[0] for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL"
            ).fetchall()
        }
        for idx in (
            "idx_ac_session", "idx_ac_agent", "idx_ac_tag",
            "idx_task_session", "idx_task_status", "idx_task_agent",
        ):
            assert idx in indexes

        with pytest.raises(sqlite3.IntegrityError):
            store.log(
                agent_name="cici咪", prompt="p", output="o",
                exit_code=0, duration_ms=1, teamchat_session_id=9999,
            )

        call_id = store.log(
            agent_name="coco咪", prompt="p", output="o", exit_code=0, duration_ms=1,
            tool_calls=[{"name": "read_file", "status": "ok", "duration_ms": 12}],
        )
        row = store.get_by_id(call_id)
        assert row.tool_calls[0]["name"] == "read_file"

        task = tt.create("soso咪", "schema task", teamchat_session_id=1)
        assert task.teamchat_session_id == 1

        store.close()
        tt.close()
        ss.close()


class TestTeamChatSessionStore:
    """Project-level session persistence (PR #40) + default seed (#47)."""

    def test_default_session_seed(self, tmp_path):
        from engine.config import Config
        from engine.session_store import DEFAULT_SESSION_NAME, SessionStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        store = SessionStore(config)
        store.init()

        assert store.count() == 1
        default = store.get(1)
        assert default is not None
        assert default.name == DEFAULT_SESSION_NAME
        assert default.directory == str(tmp_path)
        assert default.claude_id == "5fbaf844-4cbc-48b2-9242-7902d098bd81"
        assert default.cursor_id == "04e64d6d-de38-4861-a7ce-87c26d28d77f"
        assert default.codex_id
        assert "019f40ef-e8cf-76f0-8b49-6691cc7275f3" in default.codex_id
        store.close()

    def test_agent_session_id_get_set(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        store = SessionStore(config)
        store.init()
        created = store.create("Cold Start", str(tmp_path / "cold"))

        assert store.get_agent_session_id(created.id, "claude") == ""
        store.set_agent_session_id(created.id, "claude", "uuid-claude-test")
        assert store.get_agent_session_id(created.id, "claude") == "uuid-claude-test"
        store.set_agent_session_id(created.id, "codex", "uuid-codex-test")
        assert store.get_agent_session_id(created.id, "codex") == "uuid-codex-test"
        store.close()

    def test_create_list_delete(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        store = SessionStore(config)
        store.init()

        created = store.create("Dev Session", str(tmp_path))
        assert created.id == 2
        assert created.name == "Dev Session"

        listed = store.list_all()
        assert len(listed) == 2

        store.update(2, name="Renamed")
        assert store.get(2).name == "Renamed"

        store.delete(2)
        assert store.count() == 1
        store.close()


class TestCliSessionExtract:
    def test_extract_session_id_from_jsonl(self):
        from engine.runner import extract_cli_session_id

        raw = (
            '{"type":"thread.started","thread_id":"019f40ef-e8cf-76f0-8b49-6691cc7275f3"}\n'
            '{"type":"message","content":"hi"}\n'
        )
        assert extract_cli_session_id(raw) == "019f40ef-e8cf-76f0-8b49-6691cc7275f3"

    def test_extract_session_id_from_session_init(self):
        from engine.runner import extract_cli_session_id

        raw = '{"session_id":"5fbaf844-4cbc-48b2-9242-7902d098bd81","type":"system"}\n'
        assert extract_cli_session_id(raw) == "5fbaf844-4cbc-48b2-9242-7902d098bd81"

    def test_extract_cursor_system_session_id(self):
        from engine.runner import extract_cli_session_id

        raw = (
            '{"type":"system","session_id":"04e64d6d-de38-4861-a7ce-87c26d28d77f"}\n'
            '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}\n'
        )
        assert extract_cli_session_id(raw) == "04e64d6d-de38-4861-a7ce-87c26d28d77f"

    def test_parse_cursor_jsonl_output(self):
        from engine.runner import parse_cursor_jsonl_output

        raw = (
            '{"type":"system","session_id":"04e64d6d-de38-4861-a7ce-87c26d28d77f"}\n'
            '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello from soso咪"}]}}\n'
        )
        assert parse_cursor_jsonl_output(raw) == "Hello from soso咪"

    def test_cursor_cli_uses_stream_json(self):
        from engine.config import Config, AGENT_SOSO

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
        )
        cmd = config.get_cli_command(AGENT_SOSO, "hello")
        assert "--print" in cmd
        assert "stream-json" in cmd

        resume = config.get_cli_command(
            AGENT_SOSO, "hello", session_id="04e64d6d-de38-4861-a7ce-87c26d28d77f",
        )
        assert "--resume=04e64d6d-de38-4861-a7ce-87c26d28d77f" in resume
        assert "stream-json" in resume


class TestTokenAndToolStats:
    """PR #54 — token_stats / tool_stats helpers."""

    def test_token_and_tool_stats_respect_tag(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()

        store.log(
            agent_name="coco咪", prompt="prod", output="ok", exit_code=0, duration_ms=10,
            tag="prod", token_usage={"input_tokens": 10, "output_tokens": 5},
            tool_calls=[{"name": "grep", "status": "ok"}],
        )
        store.log(
            agent_name="coco咪", prompt="test", output="ok", exit_code=0, duration_ms=10,
            tag="test", token_usage={"input_tokens": 100, "output_tokens": 100},
            tool_calls=[{"name": "ignored", "status": "ok"}],
        )

        tokens = store.token_stats(agent_name="coco咪", tag="prod")
        tools = store.tool_stats(agent_name="coco咪", tag="prod")
        assert tokens["total_tokens"] == 15
        assert tools["total_tool_calls"] == 1
        assert tools["tools_by_name"]["grep"] == 1

        store.close()
        ss.close()


class TestStoreTokenStats:
    """Token aggregation in SessionStore.stats (PR #40)."""

    def test_stats_aggregates_token_usage(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()

        store.log(
            agent_name="coco咪", prompt="p1", output="o1", exit_code=0, duration_ms=100,
            token_usage={"input_tokens": 10, "output_tokens": 5},
        )
        store.log(
            agent_name="coco咪", prompt="p2", output="o2", exit_code=0, duration_ms=100,
            token_usage={"input_tokens": 20, "output_tokens": 10},
        )

        stats = store.stats(agent_name="coco咪")
        assert stats["total_tokens"] == 45
        assert stats["token_usage"]["input_tokens"] == 30
        assert stats["token_usage"]["output_tokens"] == 15
        store.close()
        ss.close()


class TestRunnerAgentEnv:
    """Agent subprocess env injects per-agent git identity + PAT (ADR-003 §5)."""

    def _make_runner(self, tmp_path):
        from engine.config import Config
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        return AgentRunner(config)

    def test_git_identity_injected(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env = runner._build_agent_env(AGENT_CICI)
        assert env["GIT_AUTHOR_NAME"] == AGENT_CICI.git_name
        assert env["GIT_AUTHOR_EMAIL"] == AGENT_CICI.git_email
        assert env["GIT_COMMITTER_NAME"] == AGENT_CICI.git_name
        assert env["GIT_COMMITTER_EMAIL"] == AGENT_CICI.git_email

    def test_token_injected_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEAMCHAT_CICI_TOKEN", "pat_test_123")
        runner = self._make_runner(tmp_path)
        env = runner._build_agent_env(AGENT_CICI)
        assert env["GH_TOKEN"] == "pat_test_123"
        assert env["GITHUB_TOKEN"] == "pat_test_123"

    def test_no_token_still_sets_git_identity(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TEAMCHAT_CICI_TOKEN", raising=False)
        runner = self._make_runner(tmp_path)
        env = runner._build_agent_env(AGENT_CICI)
        # Git identity is set regardless of whether a PAT exists
        assert env["GIT_AUTHOR_NAME"] == AGENT_CICI.git_name
        assert env["GIT_COMMITTER_EMAIL"] == AGENT_CICI.git_email

    def test_parent_env_inherited(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env = runner._build_agent_env(AGENT_CICI)
        assert "PATH" in env  # inherits parent process env

    def test_each_agent_gets_own_identity(self, tmp_path):
        runner = self._make_runner(tmp_path)
        for agent in (AGENT_CICI, AGENT_COCO, AGENT_SOSO):
            env = runner._build_agent_env(agent)
            assert env["GIT_AUTHOR_NAME"] == agent.git_name
            assert env["GIT_AUTHOR_EMAIL"] == agent.git_email

    def test_strips_sibling_agent_tokens(self, tmp_path, monkeypatch):
        """An agent's subprocess must not see sibling agents' PATs (soso咪 备注2)."""
        monkeypatch.setenv("TEAMCHAT_CICI_TOKEN", "pat_cici")
        monkeypatch.setenv("TEAMCHAT_COCO_TOKEN", "pat_coco")
        monkeypatch.setenv("TEAMCHAT_SOSO_TOKEN", "pat_soso")
        runner = self._make_runner(tmp_path)

        # coco咪's env keeps its own token, strips cici咪 and soso咪
        env = runner._build_agent_env(AGENT_COCO)
        assert env.get("TEAMCHAT_COCO_TOKEN") == "pat_coco"
        assert "TEAMCHAT_CICI_TOKEN" not in env
        assert "TEAMCHAT_SOSO_TOKEN" not in env

        # cici咪's env strips the other two
        env = runner._build_agent_env(AGENT_CICI)
        assert env.get("TEAMCHAT_CICI_TOKEN") == "pat_cici"
        assert "TEAMCHAT_COCO_TOKEN" not in env
        assert "TEAMCHAT_SOSO_TOKEN" not in env

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

    def test_codex_sandbox_flag_position(self):
        """codex resume 子命令不接受 --sandbox（exec 级选项）→ 必须用 -c 覆盖 sandbox_mode。"""
        from engine.config import (
            AGENT_COCO, CLI_CONTINUE_TEMPLATES, CLI_TEMPLATES, Config,
        )

        # 冷启动：--sandbox 是 exec 级选项，位于 exec 之后、prompt 之前
        cold = CLI_TEMPLATES["codex"]
        assert cold[1] == "exec"
        assert cold[2] == "--sandbox"
        assert cold[3] == "workspace-write"

        # continue(--last)：resume 子命令之后不得出现 --sandbox
        cont = CLI_CONTINUE_TEMPLATES["codex"]
        assert "--sandbox" not in cont
        assert "resume" in cont and "--last" in cont
        assert "-c" in cont and 'sandbox_mode="workspace-write"' in cont

        # resume 指定 session：同样不得出现 --sandbox
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
        )
        cmd = config.get_cli_command(AGENT_COCO, "hello", session_id="session-123")
        assert cmd[:3] == ["codex", "exec", "resume"]
        assert "--sandbox" not in cmd
        assert "-c" in cmd and 'sandbox_mode="workspace-write"' in cmd
        assert cmd[-1] == "hello"

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


class TestToolCallsCollection:
    """#28 — runner collects tool_use events into agent_calls.tool_calls."""

    def test_codex_collector_extracts_tool_calls(self):
        from engine.codex_events import collect_codex_tool_calls
        sample = '\n'.join([
            '{"type":"item.completed","item":{"id":"i1","type":"mcp_tool_call","name":"mcp__teamchat__create_task","input":{"agent":"soso咪"}}}',
            '{"type":"item.completed","item":{"id":"i2","type":"command_execution","command":"/bin/zsh -lc \\"ls -la\\"","exit_code":0}}',
            '{"type":"item.completed","item":{"id":"i3","type":"agent_message","text":"done"}}',
        ])
        calls = collect_codex_tool_calls(sample)
        assert len(calls) == 2
        assert calls[0]["name"] == "mcp__teamchat__create_task"
        assert calls[0]["input"] == {"agent": "soso咪"}
        assert "ls -la" in calls[1]["name"]

    def test_cursor_collector_extracts_tool_use(self):
        from engine.runner import collect_cursor_tool_calls
        sample = '\n'.join([
            '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"},{"type":"tool_use","name":"Read","input":{"file_path":"a.py"}}]}}',
            '{"type":"result","result":"hi"}',
        ])
        calls = collect_cursor_tool_calls(sample)
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"
        assert calls[0]["input"] == {"file_path": "a.py"}

    def test_summarize_tool_input_truncates(self):
        from engine.runner import _summarize_tool_input
        big = {"data": "x" * 1000}
        out = _summarize_tool_input(big)
        assert "preview" in out and len(out["preview"]) <= 300
        assert _summarize_tool_input({"a": 1}) == {"a": 1}


class TestCodexSessionRotation:
    """#26 — codex threads bloat on every resume (observed ~6M input tokens →
    plan-only replies). spawn_with_session must rotate the stored thread."""

    async def test_rotation_resets_stored_id_and_cold_starts(self, tmp_path):
        from unittest.mock import AsyncMock

        from engine.config import AGENT_COCO, Config
        from engine.dispatch import (
            CODEX_SESSION_MAX_USES, _session_uses, spawn_with_session,
        )
        from engine.runner import AgentResult, AgentTask
        from engine.session_store import SessionStore

        config = Config(
            repo_owner="t", repo_name="t", repo_url="https://t/t",
            project_root=tmp_path,
        )
        ss = SessionStore(config)
        ss.init()
        # init() seeds hardcoded IDs for the default session — clear so the
        # first spawn is a genuine cold start.
        ss.reset_agent_session(1, "codex")

        def make_result(sid: str) -> AgentResult:
            r = AgentResult(
                agent_name="coco咪", task_prompt="p", output="done",
                exit_code=0, duration_ms=1, started_at="s", finished_at="f",
            )
            r.cli_session_id = sid
            return r

        runner = AsyncMock()
        # 第 1 次冷启动捕获 thread-A；resume 至第 9 次（第 8 次 resume 触发轮换）；
        # 第 10 次调用冷启动捕获 thread-B。
        runner._run = AsyncMock(side_effect=[make_result("thread-A")] * 9 + [make_result("thread-B")])

        _session_uses.clear()
        task = AgentTask(prompt="t")
        for _ in range(CODEX_SESSION_MAX_USES + 2):
            await spawn_with_session(AGENT_COCO, task, runner, ss, 1)

        # 前 9 次：第 1 次冷启动（无 session_id），其后 resume thread-A
        for i, call in enumerate(runner._run.await_args_list[1:9], start=2):
            assert call.kwargs["session_id"] == "thread-A", f"call {i} should resume thread-A"
        # 轮换后：第 10 次调用冷启动（无 session_id）
        assert runner._run.await_args_list[9].kwargs["session_id"] is None
        # 存储最终指向新线程
        assert ss.get_agent_session_id(1, "codex") == "thread-B"

    async def test_claude_not_rotated(self, tmp_path):
        from unittest.mock import AsyncMock

        from engine.config import AGENT_CICI, Config
        from engine.dispatch import _session_uses, spawn_with_session
        from engine.runner import AgentResult, AgentTask
        from engine.session_store import SessionStore

        config = Config(
            repo_owner="t", repo_name="t", repo_url="https://t/t",
            project_root=tmp_path,
        )
        ss = SessionStore(config)
        ss.init()
        ss.reset_agent_session(1, "claude")

        def make_result(sid: str) -> AgentResult:
            r = AgentResult(
                agent_name="cici咪", task_prompt="p", output="done",
                exit_code=0, duration_ms=1, started_at="s", finished_at="f",
            )
            r.cli_session_id = sid
            return r

        runner = AsyncMock()
        runner._run = AsyncMock(side_effect=[make_result("claude-A")] * 5)
        _session_uses.clear()
        task = AgentTask(prompt="t")
        for _ in range(5):
            await spawn_with_session(AGENT_CICI, task, runner, ss, 1)
        # 仅 codex 轮换：claude 即使多次 resume 也保留存储
        assert ss.get_agent_session_id(1, "claude") == "claude-A"


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


class TestCodexTokenIncrement:
    """#27 — codex token_usage is thread-cumulative; stats must use increments."""

    def _store(self, tmp_path):
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
        return store, ss

    def _log(self, store, agent, in_t, out_t, seq):
        store.log(
            agent_name=agent, prompt="p", output="ok", exit_code=0, duration_ms=1,
            tag="prod", teamchat_session_id=1,
            token_usage={"input_tokens": in_t, "output_tokens": out_t},
            started_at=f"2026-08-03T0{seq}:00:00+00:00",
        )

    def test_codex_usage_uses_increments(self, tmp_path):
        """coco咪 (codex): cumulative 100→300→600 ⇒ increments 100+200+300."""
        store, ss = self._store(tmp_path)
        self._log(store, "coco咪", 100, 50, 1)
        self._log(store, "coco咪", 300, 80, 2)
        self._log(store, "coco咪", 600, 120, 3)

        tokens = store.token_stats(agent_name="coco咪", tag="prod")
        assert tokens["input_tokens"] == 600
        assert tokens["output_tokens"] == 120
        assert tokens["total_tokens"] == 720

        stats = store.stats(agent_name="coco咪", tag="prod")
        assert stats["token_usage"]["input_tokens"] == 600
        assert stats["total_tokens"] == 720
        store.close()
        ss.close()

    def test_codex_thread_rotation_negative_delta_falls_back(self, tmp_path):
        """New thread starts small (600 → 50): negative delta falls back to
        the current value, then continues incrementally."""
        store, ss = self._store(tmp_path)
        self._log(store, "coco咪", 600, 100, 1)
        self._log(store, "coco咪", 50, 10, 2)   # 线程轮换 → 负增量 → 兜底本次值
        self._log(store, "coco咪", 80, 20, 3)   # 50→80 增量 30/10

        tokens = store.token_stats(agent_name="coco咪", tag="prod")
        assert tokens["input_tokens"] == 600 + 50 + 30
        assert tokens["output_tokens"] == 100 + 10 + 10
        store.close()
        ss.close()

    def test_claude_usage_direct_sum_unchanged(self, tmp_path):
        """cici咪 (claude): usage is already incremental — direct sum."""
        store, ss = self._store(tmp_path)
        self._log(store, "cici咪", 100, 5, 1)
        self._log(store, "cici咪", 200, 10, 2)

        tokens = store.token_stats(agent_name="cici咪", tag="prod")
        assert tokens["input_tokens"] == 300
        assert tokens["output_tokens"] == 15
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

        # coco咪 = codex：token_usage 是线程累计值 → 增量语义
        # input: 10 + (20-10) = 20；output: 5 + (10-5) = 10；total = 30
        stats = store.stats(agent_name="coco咪")
        assert stats["total_tokens"] == 30
        assert stats["token_usage"]["input_tokens"] == 20
        assert stats["token_usage"]["output_tokens"] == 10
        store.close()
        ss.close()



class TestL3Stats:
    """#29 — L3 解放指标：自动化率 / 人工介入 / 消息→完成 / 审批。"""

    def _build(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore
        from engine.task_table import create_task_table

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()
        tt = create_task_table(config)
        return store, tt, ss

    def _human_msg(self, store, ts):
        store.log(
            agent_name="human", prompt="做个功能", output="做个功能",
            exit_code=0, duration_ms=0, task_type="chat_message", tag="prod",
            teamchat_session_id=1, started_at=ts, finished_at=ts,
        )

    def test_automation_rate_and_interventions(self, tmp_path):
        store, tt, ss = self._build(tmp_path)
        for _ in range(3):
            t = tt.create(agent="coco咪", title="x", description="d")
            tt.update(t.id, status="done")
            tt.update(t.id, finished_at="2026-07-31T10:00:00+00:00")
        t = tt.create(agent="coco咪", title="y", description="d")
        tt.update(t.id, status="abandoned")
        tt.update(t.id, finished_at="2026-07-31T11:00:00+00:00")

        l3 = store.l3_stats(tt, teamchat_session_id=1)
        assert l3["automation_rate"] == 0.75
        assert l3["human_interventions"] == 1
        assert l3["approvals"] == 0

    def test_message_to_completion_uses_max_finish(self, tmp_path):
        store, tt, ss = self._build(tmp_path)
        # 消息时间取过去（任务 created_at 是真实 now，须晚于消息才归组）
        self._human_msg(store, "2026-07-31T09:00:00+00:00")
        t1 = tt.create(agent="coco咪", title="a", description="d")
        tt.update(t1.id, status="done")
        tt.update(t1.id, finished_at="2026-07-31T09:10:00+00:00")
        t2 = tt.create(agent="soso咪", title="b", description="d")
        tt.update(t2.id, status="done")
        tt.update(t2.id, finished_at="2026-07-31T09:15:00+00:00")

        l3 = store.l3_stats(tt, teamchat_session_id=1)
        assert l3["message_to_completion_ms"] == 15 * 60 * 1000

    def test_incomplete_group_excluded(self, tmp_path):
        store, tt, ss = self._build(tmp_path)
        self._human_msg(store, "2026-07-31T09:00:00+00:00")
        tt.create(agent="coco咪", title="c", description="d")  # 仍 pending

        l3 = store.l3_stats(tt, teamchat_session_id=1)
        assert l3["message_to_completion_ms"] is None

    def test_no_human_messages(self, tmp_path):
        store, tt, ss = self._build(tmp_path)
        t = tt.create(agent="coco咪", title="x", description="d")
        tt.update(t.id, status="done")

        l3 = store.l3_stats(tt, teamchat_session_id=1)
        assert l3["message_to_completion_ms"] is None
        assert l3["automation_rate"] == 1.0


class TestL3ApprovalCount:
    """#29 — approvals count from persisted approval rows + endpoint wiring."""

    def test_approvals_counted_from_agent_calls(self, tmp_path):
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore
        from engine.task_table import create_task_table

        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()
        tt = create_task_table(config)
        tt.init()

        now = "2026-08-03T01:00:00+00:00"
        for _ in range(2):
            store.log(
                agent_name="human", prompt="approval:req", output="allow",
                exit_code=0, duration_ms=0, task_type="approval", tag="prod",
                teamchat_session_id=1, started_at=now, finished_at=now,
            )
        l3 = store.l3_stats(tt, teamchat_session_id=1)
        assert l3["approvals"] == 2

    def test_handle_approval_persists_row(self, tmp_path):
        """Sync TestClient avoids asyncio loop clash with Playwright e2e in same session."""
        import json

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routes import approval as approval_mod
        from engine.config import Config
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore
        from tests.test_approval import MockStdinWriter

        approval_mod._pending_approvals.clear()
        config = Config(
            repo_owner="test", repo_name="test", repo_url="https://github.com/test/test",
            project_root=tmp_path,
        )
        ss = TeamChatSessionStore(config)
        ss.init()
        store = AgentCallStore(config)
        store.init()

        app = FastAPI()
        app.include_router(approval_mod.router)
        app.state.store = store
        client = TestClient(app)

        writer = MockStdinWriter()
        approval_mod.register_approval("req-log", writer)
        resp = client.post(
            "/api/approval",
            json={"request_id": "req-log", "decision": "allow"},
        )
        assert resp.status_code == 200
        rows = store.conn.execute(
            "SELECT COUNT(*) FROM agent_calls WHERE agent_name='human' AND task_type='approval'"
        ).fetchone()
        assert rows[0] == 1
        assert writer.chunks and json.loads(writer.chunks[0].decode())["type"] == "control_response"
        approval_mod._pending_approvals.clear()
        store.close()
        ss.close()


class TestToolCallCollection:
    """#28 - runner collects tool_use events into AgentResult.tool_calls."""
    def test_collect_codex_tool_calls(self):
        from engine.codex_events import collect_codex_tool_calls
        sample = chr(10).join([
            '{"type":"thread.started","thread_id":"t1"}',
            '{"type":"item.completed","item":{"id":"i1","type":"command_execution","command":["grep","-r","x"],"exit_code":0}}',
            '{"type":"item.completed","item":{"id":"i2","type":"mcp_tool_call","name":"create_task","input":{"agent":"coco咪"}}}',
            '{"type":"item.completed","item":{"id":"i3","type":"agent_message","text":"done"}}',
            '{"type":"item.completed","item":{"id":"i4","type":"reasoning","text":"think"}}',
        ])
        calls = collect_codex_tool_calls(sample)
        assert len(calls) == 2
        assert calls[0]["name"] == "grep -r x"
        assert calls[1]["name"] == "create_task"
    def test_collect_cursor_tool_calls(self):
        from engine.runner import collect_cursor_tool_calls
        sample = chr(10).join([
            '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"},{"type":"tool_use","name":"Read","input":{"file":"a.py"}}]}}',
            '{"type":"result","result":"done"}',
        ])
        calls = collect_cursor_tool_calls(sample)
        assert len(calls) == 1 and calls[0]["name"] == "Read"
    def test_summarize_input_caps_long_json(self):
        from engine.runner import _summarize_tool_input
        big = {"data": "x" * 1000}
        s = _summarize_tool_input(big)
        assert "preview" in s and len(s["preview"]) == 300
        assert _summarize_tool_input({"a": 1}) == {"a": 1}

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

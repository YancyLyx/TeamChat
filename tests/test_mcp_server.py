"""Unit + subprocess tests for engine/mcp_server.py (ADR-003 §7, PR #78)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine.config import Config, load_config
from engine.session_store import SessionStore as TeamChatSessionStore
from engine.task_table import TaskTable
import engine.mcp_server as mcp


@pytest.fixture
def task_table(tmp_path):
    base = load_config()
    config = Config(
        repo_owner=base.repo_owner,
        repo_name=base.repo_name,
        repo_url=base.repo_url,
        project_root=tmp_path,
    )
    ss = TeamChatSessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()
    mcp._task_table_override = tt
    yield tt
    mcp._task_table_override = None
    tt.close()
    ss.close()


class TestMcpProcessRequest:
    def test_initialize_returns_server_info(self):
        resp = mcp.process_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp is not None
        assert resp["result"]["serverInfo"]["name"] == "teamchat"

    def test_tools_list_returns_all_tools(self):
        resp = mcp.process_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {t["name"] for t in resp["result"]["tools"]}
        assert names == {"create_task", "update_task", "list_tasks", "get_task", "dag_summary", "task_tree"}

    def test_unknown_method_returns_error(self):
        resp = mcp.process_request({"jsonrpc": "2.0", "id": 9, "method": "nope", "params": {}})
        assert resp["error"]["code"] == -32601

    def test_notifications_initialized_returns_none(self):
        assert mcp.process_request({
            "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
        }) is None


class TestMcpToolHandlers:
    def test_create_and_get_task(self, task_table: TaskTable):
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {
                    "agent": "coco咪",
                    "title": "MCP unit test",
                    "prompt": "run tests",
                    "depends_on": [],
                },
            },
        })
        assert "error" not in resp
        assert resp["result"].get("isError") is not True
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["task_id"] > 0
        assert payload["agent"] == "coco咪"

        got = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_task", "arguments": {"task_id": payload["task_id"]}},
        })
        task = json.loads(got["result"]["content"][0]["text"])["task"]
        assert task["title"] == "MCP unit test"
        assert task["description"] == "run tests"

    def test_create_task_validation_error_is_marked(self, task_table: TaskTable):
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "create_task", "arguments": {"title": "no agent"}},
        })
        assert resp["result"]["isError"] is True
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert "error" in payload

    def test_update_task_changes_status(self, task_table: TaskTable):
        task = task_table.create("soso咪", "Review PR")
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "update_task",
                "arguments": {"task_id": task.id, "status": "done"},
            },
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["status"] == "done"
        assert task_table.get(task.id).status == "done"

    def test_update_task_can_fix_depends_on(self, task_table: TaskTable):
        """soso咪 Bug 2: cici咪 must be able to break a cycle via update_task."""
        a = task_table.create("coco咪", "A")
        b = task_table.create("soso咪", "B", depends_on=[a.id])
        task_table.update(a.id, depends_on=[b.id])  # A↔B cycle

        # cici咪 fixes it: A no longer depends on B
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "update_task",
                "arguments": {"task_id": a.id, "status": "pending", "depends_on": []},
            },
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["depends_on"] == []
        assert task_table.get(a.id).depends_on == []
        # Cycle resolved
        from engine.task_planner import detect_cycles
        assert detect_cycles(task_table) == []

    def test_create_task_warns_on_cycle(self, task_table: TaskTable):
        """soso咪 缺口: create_task 触发循环时返回 warning."""
        a = task_table.create("coco咪", "A")
        b = task_table.create("soso咪", "B", depends_on=[a.id])
        task_table.update(a.id, depends_on=[b.id])  # already cyclic

        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {"agent": "coco咪", "title": "C", "prompt": "x",
                              "depends_on": [b.id]},
            },
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["warning"] and "循环" in payload["warning"]

    def test_create_task_warns_on_orphan_dep(self, task_table: TaskTable):
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {"agent": "coco咪", "title": "C", "prompt": "x",
                              "depends_on": [999]},
            },
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["warning"] and "不存在" in payload["warning"]

    def test_task_tree_tool(self, task_table: TaskTable):
        """soso咪 Bug 3: task_tree 已暴露为 MCP 工具."""
        a = task_table.create("coco咪", "A")
        b = task_table.create("soso咪", "B", depends_on=[a.id])
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "task_tree", "arguments": {"task_id": a.id}},
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        root = payload["root"]
        assert root["id"] == a.id
        assert root["children"][0]["id"] == b.id

    def test_update_pending_resets_retry_records(self, task_table: TaskTable):
        """soso咪 备注1: 手动重试（pending）时清零 retry_count/last_error。"""
        task = task_table.create("coco咪", "A")
        task_table.update(task.id, retry_count=3, last_error="boom")
        mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "update_task",
                "arguments": {"task_id": task.id, "status": "pending"},
            },
        })
        updated = task_table.get(task.id)
        assert updated.retry_count == 0
        assert updated.last_error == ""

    def test_update_task_can_reassign_agent(self, task_table: TaskTable):
        """Phase 4.5: update_task 支持 agent 转派（自愈三选项之一）。"""
        task = task_table.create("coco咪", "A")
        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "update_task",
                "arguments": {"task_id": task.id, "status": "pending", "agent": "soso咪"},
            },
        })
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert task_table.get(task.id).agent == "soso咪"  # 转派成功

    def test_list_tasks_filter(self, task_table: TaskTable):
        task_table.create("cici咪", "A")
        done = task_table.create("coco咪", "B")
        task_table.update(done.id, status="done")

        resp = mcp.process_request({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "list_tasks", "arguments": {"status": "done"}},
        })
        tasks = json.loads(resp["result"]["content"][0]["text"])["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["status"] == "done"


class TestMcpStdioSubprocess:
    def test_stdio_tools_list(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "engine.mcp_server"],
            input='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n',
            capture_output=True,
            text=True,
            cwd=root,
            timeout=10,
        )
        assert proc.returncode == 0
        line = proc.stdout.strip().splitlines()[-1]
        data = json.loads(line)
        assert data["id"] == 1
        assert len(data["result"]["tools"]) == 6
        assert proc.stderr  # MCP logs go to stderr

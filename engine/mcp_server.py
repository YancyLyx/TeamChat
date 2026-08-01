"""
TeamChat MCP Server — stdio-based JSON-RPC server for Claude CLI.

Provides tools for cici咪 to manage the task table.
Claude CLI spawns this process via --mcp-config.

Logs to stderr so stdout stays clean for JSON-RPC.
"""

import json
import logging
import sys
from typing import Any

from engine.task_planner import dag_summary, detect_cycles, task_tree

# Log to stderr (stdout is for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MCP] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("teamchat.mcp")

# ---- Tool implementations ----


# Lazy override for tests (monkeypatch this to inject a TaskTable).
_task_table_override = None


def _get_task_table():
    """Lazy init TaskTable connected to the current project."""
    if _task_table_override is not None:
        return _task_table_override
    from engine.task_table import create_task_table
    from engine.config import load_config
    config = load_config()
    tt = create_task_table(config)
    return tt


def handle_create_task(args: dict) -> dict:
    agent = args.get("agent", "")
    title = args.get("title", "")
    prompt = args.get("prompt", "")
    depends_on = args.get("depends_on", [])

    if not agent or not title:
        return {"error": "agent and title are required"}

    tt = _get_task_table()
    task = tt.create(agent=agent, title=title, description=prompt, depends_on=depends_on)
    logger.info(f"📝 create_task: #{task.id} '{title}' → {agent} (deps={depends_on})")

    # Phase 4.2: DAG 校验 — 循环 + 孤儿依赖（不阻塞创建，cici咪 修正）
    warnings = []
    cycles = detect_cycles(tt)
    if cycles:
        warnings.append(f"⚠️ 依赖存在循环: {cycles}，可用 update_task 修正 depends_on")
        logger.warning(f"create_task #{task.id} 导致循环: {cycles}")
    missing = [d for d in (depends_on or []) if not tt.get(d)]
    if missing:
        warnings.append(f"⚠️ 依赖的任务不存在: {missing}")

    return {"task_id": task.id, "agent": agent, "title": title,
            "status": "pending", "warning": "; ".join(warnings) or None}


def handle_dag_summary(args: dict) -> dict:
    """DAG 概况：任务数、按状态分布、循环/孤儿/失败阻塞检测。"""
    tt = _get_task_table()
    return dag_summary(tt, teamchat_session_id=args.get("teamchat_session_id"))


def handle_task_tree(args: dict) -> dict:
    """以某任务为根的 DAG 子树（soso咪 review Bug 3: 兑现 prompt 的'任务树'）。"""
    task_id = args.get("task_id", 0)
    tt = _get_task_table()
    return {"root": task_tree(tt, task_id)}


def handle_update_task(args: dict) -> dict:
    task_id = args.get("task_id", 0)
    status = args.get("status", "")

    if not task_id or not status:
        return {"error": "task_id and status are required"}

    tt = _get_task_table()
    task = tt.get(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found"}

    # soso咪 review Bug 2: 支持 depends_on 修正（cici咪 修复循环依赖的途径）
    kwargs = {"status": status}
    if "depends_on" in args:
        kwargs["depends_on"] = args["depends_on"]
    tt.update(task_id, **kwargs)
    # soso咪 审查建议: update 后复检循环（create 有 warning，update 也要有）
    warning = None
    cycles = detect_cycles(tt)
    if cycles:
        warning = f"⚠️ 更新后依赖存在循环: {cycles}"
        logger.warning(f"update_task #{task_id} 后存在循环: {cycles}")
    logger.info(f"🔄 update_task: #{task_id} → {status}")
    return {"task_id": task_id, "status": status,
            "depends_on": args.get("depends_on", task.depends_on),
            "warning": warning}


def handle_list_tasks(args: dict) -> dict:
    status_filter = args.get("status") or args.get("status_filter")
    tt = _get_task_table()
    tasks = tt.list_tasks(status=status_filter or None)
    logger.info(f"📋 list_tasks: {len(tasks)} results (filter={status_filter or 'all'})")
    return {"tasks": [t.to_dict() for t in tasks]}


def handle_get_task(args: dict) -> dict:
    task_id = args.get("task_id", 0)
    tt = _get_task_table()
    task = tt.get(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found"}
    return {"task": task.to_dict()}


TOOLS = {
    "create_task": {
        "handler": handle_create_task,
        "schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "cici咪, coco咪, or soso咪"},
                "title": {"type": "string", "description": "Task title"},
                "prompt": {"type": "string", "description": "Full prompt to send to the agent"},
                "depends_on": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Task IDs this depends on",
                },
            },
            "required": ["agent", "title"],
        },
    },
    "update_task": {
        "handler": handle_update_task,
        "schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "running", "done", "failed"]},
                "depends_on": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional: fix the task's dependencies (e.g. break a cycle)",
                },
            },
            "required": ["task_id", "status"],
        },
    },
    "list_tasks": {
        "handler": handle_list_tasks,
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
        },
    },
    "get_task": {
        "handler": handle_get_task,
        "schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
    "dag_summary": {
        "handler": handle_dag_summary,
        "schema": {
            "type": "object",
            "properties": {
                "teamchat_session_id": {"type": "integer"},
            },
        },
    },
    "task_tree": {
        "handler": handle_task_tree,
        "schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
}


# ---- JSON-RPC over stdio ----


def send_response(id_val: Any, result: Any):
    """Write a JSON-RPC response to stdout."""
    response = {"jsonrpc": "2.0", "id": id_val, "result": result}
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return response


def send_error(id_val: Any, code: int, message: str):
    response = {"jsonrpc": "2.0", "id": id_val, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return response


def tool_content(result: dict, *, is_error: bool = False) -> dict:
    """Wrap tool handler output in MCP tools/call result shape."""
    payload = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    if is_error:
        payload["isError"] = True
    return payload


def process_request(request: dict) -> dict | None:
    """Process one JSON-RPC request and return the response dict (None for notifications)."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        logger.info("🚀 MCP Server initialized")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "teamchat", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        tools_list = [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS.get(name, ""),
                "inputSchema": info["schema"],
            }
            for name, info in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        tool_info = TOOLS.get(tool_name)
        if not tool_info:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        logger.info(f"🔧 {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")
        try:
            result = tool_info["handler"](tool_args)
            is_error = isinstance(result, dict) and "error" in result
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": tool_content(result, is_error=is_error),
            }
        except Exception as e:
            logger.error(f"❌ {tool_name} failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if req_id is not None:
        logger.debug(f"Unknown method: {method}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    logger.debug(f"Unknown notification: {method}")
    return None


def handle_request(request: dict):
    """Process one JSON-RPC request and write response to stdout."""
    response = process_request(request)
    if response is None:
        return
    if "error" in response:
        send_error(response["id"], response["error"]["code"], response["error"]["message"])
    else:
        send_response(response["id"], response["result"])


TOOL_DESCRIPTIONS = {
    "create_task": "Create a new task assigned to an agent. The prompt field contains the full instructions for the agent.",
    "update_task": "Update a task's status (pending/running/done/failed) and optionally fix its depends_on dependencies.",
    "list_tasks": "List tasks, optionally filtered by status.",
    "get_task": "Get a single task by ID.",
    "dag_summary": "DAG 概况：任务数、状态分布、循环依赖、孤儿依赖（依赖不存在）、被失败/废弃任务阻塞的 pending 任务。",
    "task_tree": "以某任务为根的任务树（该任务的全部后代依赖）。",
}


def main():
    logger.info("🚀 TeamChat MCP Server starting (stdio mode)")
    logger.info(f"   Tools: {list(TOOLS.keys())}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {line[:100]}")
            continue
        handle_request(request)

    logger.info("MCP Server shutting down")


if __name__ == "__main__":
    main()

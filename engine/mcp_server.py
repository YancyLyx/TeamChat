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

# Log to stderr (stdout is for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MCP] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("teamchat.mcp")

# ---- Tool implementations ----


def _get_task_table():
    """Lazy init TaskTable connected to the current project."""
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
    return {"task_id": task.id, "agent": agent, "title": title, "status": "pending"}


def handle_update_task(args: dict) -> dict:
    task_id = args.get("task_id", 0)
    status = args.get("status", "")

    if not task_id or not status:
        return {"error": "task_id and status are required"}

    tt = _get_task_table()
    task = tt.get(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found"}

    tt.update(task_id, status=status)
    logger.info(f"🔄 update_task: #{task_id} → {status}")
    return {"task_id": task_id, "status": status}


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
}


# ---- JSON-RPC over stdio ----


def send_response(id_val: Any, result: Any):
    """Write a JSON-RPC response to stdout."""
    response = {"jsonrpc": "2.0", "id": id_val, "result": result}
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_error(id_val: Any, code: int, message: str):
    response = {"jsonrpc": "2.0", "id": id_val, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_request(request: dict):
    """Process one JSON-RPC request."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        logger.info("🚀 MCP Server initialized")
        return send_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "teamchat", "version": "0.1.0"},
        })

    if method == "notifications/initialized":
        return  # No response needed

    if method == "tools/list":
        tools_list = [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS.get(name, ""),
                "inputSchema": info["schema"],
            }
            for name, info in TOOLS.items()
        ]
        return send_response(req_id, {"tools": tools_list})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        tool_info = TOOLS.get(tool_name)
        if not tool_info:
            return send_error(req_id, -32601, f"Unknown tool: {tool_name}")

        logger.info(f"🔧 {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")
        try:
            result = tool_info["handler"](tool_args)
            # Wrap in content array per MCP spec
            return send_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
            })
        except Exception as e:
            logger.error(f"❌ {tool_name} failed: {e}")
            return send_error(req_id, -32000, str(e))

    if method == "ping":
        return send_response(req_id, {})

    # Unknown method — ignore (logging, etc.)
    logger.debug(f"Unknown method: {method}")


TOOL_DESCRIPTIONS = {
    "create_task": "Create a new task assigned to an agent. The prompt field contains the full instructions for the agent.",
    "update_task": "Update a task's status (pending/running/done/failed).",
    "list_tasks": "List tasks, optionally filtered by status.",
    "get_task": "Get a single task by ID.",
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

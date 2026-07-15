"""Helpers for parsing Codex CLI JSONL events."""

from __future__ import annotations

import json
from typing import Any


AGENT_MESSAGE_TYPES = {"agent_message", "assistant_message", "message"}
REASONING_TYPES = {"reasoning", "thinking"}
TOOL_TYPES = {
    "command_execution",
    "tool_call",
    "function_call",
    "mcp_tool_call",
    "local_shell_call",
}


def codex_item_type(item: dict[str, Any]) -> str:
    """Return the normalized Codex item type."""
    return str(item.get("type") or item.get("kind") or "").strip()


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = (
                    block.get("text")
                    or block.get("content")
                    or block.get("output_text")
                    or block.get("input_text")
                )
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return _content_text(
            content.get("content") or content.get("text") or content.get("output_text")
        )
    return ""


def codex_item_text(item: dict[str, Any]) -> str:
    """Extract visible text from a Codex event item without serializing raw JSON."""
    for key in ("text", "message", "result", "output_text", "content"):
        text = _content_text(item.get(key))
        if text:
            return text
    summary = item.get("summary")
    if isinstance(summary, list):
        return _content_text(summary)
    if isinstance(summary, str):
        return summary
    return ""


def is_codex_agent_message(item: dict[str, Any]) -> bool:
    item_type = codex_item_type(item)
    if item_type == "message":
        role = str(item.get("role") or item.get("author") or "").lower()
        return role in {"", "assistant", "agent"}
    return item_type in AGENT_MESSAGE_TYPES


def is_codex_reasoning(item: dict[str, Any]) -> bool:
    return codex_item_type(item) in REASONING_TYPES


def is_codex_tool_call(item: dict[str, Any]) -> bool:
    return codex_item_type(item) in TOOL_TYPES


def codex_tool_name(item: dict[str, Any]) -> str:
    command = item.get("command")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)[:80]
    if command:
        return str(command)[:80]
    return str(item.get("name") or item.get("tool_name") or codex_item_type(item))[:80]


def codex_tool_input(item: dict[str, Any]) -> dict[str, Any]:
    tool_input = item.get("input") or item.get("arguments") or item.get("args")
    if not isinstance(tool_input, dict):
        tool_input = {}
    if "exit_code" in item:
        return {**tool_input, "exit_code": item.get("exit_code")}
    return tool_input


def extract_codex_agent_text(raw: dict[str, Any]) -> str:
    """Extract assistant-visible text from one Codex JSON event."""
    item = raw.get("item")
    if isinstance(item, dict) and is_codex_agent_message(item):
        return codex_item_text(item)

    event_type = str(raw.get("type") or "")
    if event_type == "message":
        role = str(raw.get("role") or raw.get("author") or "").lower()
        if role not in {"", "assistant", "agent"}:
            return ""
        return codex_item_text(raw)
    if event_type in {"agent_message", "assistant_message"}:
        return codex_item_text(raw)
    return ""


def parse_codex_jsonl_output(output: str) -> tuple[str, dict[str, Any], bool]:
    """
    Return clean assistant text, token usage, and whether JSONL events were seen.

    Codex --json includes reasoning and tool events. Chat bubbles should only render
    assistant messages, not raw event objects or command execution payloads.
    """
    text_parts: list[str] = []
    usage: dict[str, Any] = {}
    saw_json_event = False

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue

        saw_json_event = True
        event_usage = raw.get("usage")
        if isinstance(event_usage, dict):
            usage = event_usage

        text = extract_codex_agent_text(raw)
        if text:
            text_parts.append(text)

    return "\n".join(text_parts).strip(), usage, saw_json_event

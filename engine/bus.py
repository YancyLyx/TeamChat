"""
Message Bus — Agent-to-agent communication.

Agents post messages (JSON files) to .teamchat/messages/.
The bus provides read/write/subscribe semantics on top of the file system.

Each message has a sender, recipient, type, and GitHub issue/PR reference.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Awaitable

from engine.config import Config, AgentIdentity

logger = logging.getLogger(__name__)

# ---- Data types ----


class MessageType:
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETE = "task_complete"
    REVIEW_REQUEST = "review_request"
    QUESTION = "question"
    REPLY = "reply"
    BROADCAST = "broadcast"


@dataclass
class BusMessage:
    """One message on the bus."""
    id: str
    from_agent: str
    to_agent: str       # "all" for broadcast
    msg_type: str
    content: str
    github_ref: str = ""   # e.g. "#42" or "PR #87"
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.msg_type,
            "content": self.content,
            "github_ref": self.github_ref,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BusMessage":
        return cls(
            id=data.get("id", ""),
            from_agent=data.get("from", "unknown"),
            to_agent=data.get("to", "all"),
            msg_type=data.get("type", "broadcast"),
            content=data.get("content", ""),
            github_ref=data.get("github_ref", ""),
            timestamp=data.get("timestamp", ""),
        )


# ---- Bus ----


class MessageBus:
    """File-system-based message bus for agent communication."""

    def __init__(self, config: Config):
        self.config = config
        self.messages_dir = config.messages_dir
        self._counter = 0
        self._listeners: dict[str, list[Callable[[BusMessage], Awaitable[None]]]] = {}

    def init(self):
        """Ensure the messages directory exists."""
        self.messages_dir.mkdir(parents=True, exist_ok=True)

    # ---- Send ----

    def send(self, from_agent: AgentIdentity, to_agent: AgentIdentity | str,
             msg_type: str, content: str, github_ref: str = "") -> BusMessage:
        """Post a message to the bus. Persists as a JSON file."""
        self._counter += 1
        msg_id = f"msg-{self._counter:04d}"
        now = datetime.now(timezone.utc).isoformat()

        to_name = to_agent if isinstance(to_agent, str) else to_agent.name
        msg = BusMessage(
            id=msg_id,
            from_agent=from_agent.name,
            to_agent=to_name,
            msg_type=msg_type,
            content=content,
            github_ref=github_ref,
            timestamp=now,
        )

        # Write to file
        filepath = self.messages_dir / f"{msg_id}.json"
        filepath.write_text(
            json.dumps(msg.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"📨 {from_agent.name} → {to_name} [{msg_type}]: {content[:80]}")

        # Notify listeners
        self._notify(to_name, msg)

        return msg

    def broadcast(self, from_agent: AgentIdentity, content: str,
                  msg_type: str = MessageType.BROADCAST) -> BusMessage:
        """Send a message to all agents."""
        return self.send(from_agent, "all", msg_type, content)

    # ---- Read ----

    def inbox(self, agent: AgentIdentity, limit: int = 50) -> list[BusMessage]:
        """Get messages addressed to this agent (or broadcast)."""
        messages = []
        for filepath in sorted(self.messages_dir.glob("msg-*.json"),
                               key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                msg = BusMessage.from_dict(data)
                if msg.to_agent in (agent.name, "all"):
                    messages.append(msg)
                    if len(messages) >= limit:
                        break
            except (json.JSONDecodeError, KeyError):
                logger.warning(f"⚠️  Corrupt message file: {filepath.name}")
        return messages

    def unread(self, agent: AgentIdentity, since_id: str = "") -> list[BusMessage]:
        """Get messages newer than a given ID."""
        all_msgs = self.inbox(agent)
        if not since_id:
            return all_msgs
        return [m for m in all_msgs if m.id > since_id]

    # ---- Listen (for real-time push to WebSocket in Phase 3) ----

    def subscribe(self, agent_name: str,
                  callback: Callable[[BusMessage], Awaitable[None]]):
        """Register a callback to be called when messages arrive for this agent."""
        if agent_name not in self._listeners:
            self._listeners[agent_name] = []
        self._listeners[agent_name].append(callback)

    def _notify(self, to_name: str, msg: BusMessage):
        """Notify all listeners matching the recipient."""
        # Notify specific recipient
        for cb in self._listeners.get(to_name, []):
            try:
                import asyncio
                asyncio.create_task(cb(msg))
            except Exception:
                pass
        # Notify "all" listeners for broadcast
        if to_name != "all":
            for cb in self._listeners.get("all", []):
                try:
                    import asyncio
                    asyncio.create_task(cb(msg))
                except Exception:
                    pass

    # ---- Stats ----

    def stats(self) -> dict:
        """Message bus statistics."""
        files = list(self.messages_dir.glob("msg-*.json"))
        agents = set()
        types = set()
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                agents.add(data.get("from", "unknown"))
                agents.add(data.get("to", "unknown"))
                types.add(data.get("type", "unknown"))
            except Exception:
                pass
        return {
            "total_messages": len(files),
            "agents": sorted(agents),
            "message_types": sorted(types),
        }

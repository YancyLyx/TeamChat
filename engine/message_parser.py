"""
Message Parser — extract @mentions and routing intent from chat messages.

Handles the human -> agent routing decision:
  - "@coco咪 do X" -> direct to coco咪
  - "add a refresh button" -> cici咪 analyzes, then routes
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from engine.config import AgentIdentity, AGENT_CICI, AGENT_COCO, AGENT_SOSO, ALL_AGENTS

logger = logging.getLogger(__name__)

# Map agent names to identities
_AGENTS_BY_NAME: dict[str, AgentIdentity] = {a.name: a for a in ALL_AGENTS}

# Match @cici咪, @coco咪, @soso咪 (anywhere in message)
_MENTION_PATTERN = re.compile(r"@(cici咪|coco咪|soso咪)")


@dataclass
class ParsedMessage:
    """Result of parsing a human chat message."""

    raw: str
    mentions: list[AgentIdentity]       # agents explicitly @mentioned
    direct_target: AgentIdentity | None # exactly one mention -> direct route
    is_direct: bool                     # True if human wants a specific agent
    cleaned_content: str                # message with @mentions stripped

    @property
    def needs_cici_analysis(self) -> bool:
        """If no direct target, cici咪 must analyze first."""
        return self.direct_target is None


def parse_message(content: str) -> ParsedMessage:
    """
    Parse a human chat message for @mentions and routing intent.

    Examples:
        "@coco咪 fix the dark mode" -> direct_target=coco咪
        "add a refresh button"      -> direct_target=None (cici咪 analyzes)
        "@cici咪 @soso咪 what do you think?" -> mentions=[cici,soso], no direct
    """
    # Find all @mentions
    mentioned_names = _MENTION_PATTERN.findall(content)
    mentions = [_AGENTS_BY_NAME[name] for name in mentioned_names]

    # Exactly one mention = direct target
    direct_target = mentions[0] if len(mentions) == 1 else None

    # Clean content (strip @mentions)
    cleaned = _MENTION_PATTERN.sub("", content).strip()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return ParsedMessage(
        raw=content,
        mentions=mentions,
        direct_target=direct_target,
        is_direct=direct_target is not None,
        cleaned_content=cleaned,
    )


def get_agent_by_name(name: str) -> AgentIdentity | None:
    """Look up an agent by their display name."""
    return _AGENTS_BY_NAME.get(name)


def build_cici_analysis_prompt(message: str) -> str:
    """
    Build the prompt for cici咪 to analyze an unaddressed message.

    cici咪 must determine whether the message is:
      - A simple question (answer directly)
      - A development task (route to coco咪)
      - A testing/QA task (route to soso咪)
      - An architecture decision (handle herself)
      - Needs clarification (ask human back)
    """
    return f"""你是 TeamChat 项目的架构师 cici咪。团队里还有:
- coco咪 (Codex Developer): 负责前端 Dashboard、API、快速功能开发
- soso咪 (Cursor QA): 负责测试、GitHub 集成、代码审查、CI/CD

人类在团队聊天室里发了一条消息（没有 @ 任何人）。请你判断这条消息的意图:

人类消息: "{message}"

请只回复以下格式之一（不要加额外解释）:

如果是简单问答 → ANSWER: <你的回答>
如果是前端/API开发任务 → TASK:frontend: <任务描述>
如果是测试/审查任务 → TASK:testing: <任务描述>
如果是架构设计任务 → TASK:architecture: <任务描述>
如果需要向人类澄清 → CLARIFY: <你的问题>
"""

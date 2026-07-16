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

    cici咪 has access to MCP tools (mcp__teamchat__create_task, mcp__teamchat__update_task).
    She should use these tools to create/update tasks instead of using text format.
    """
    return f"""你是 TeamChat 项目的架构师 cici咪。你有 MCP 工具可以操作任务表。

团队:
- coco咪 (Codex Developer): 负责前端 Dashboard、API、快速功能开发
- soso咪 (Cursor QA): 负责测试、GitHub 集成、代码审查、CI/CD

人类在聊天室发了一条消息（没有 @ 任何人）。请分析:

人类消息: "{message}"

你的工作流程:
1. 先分析需求，用文字回复你的分析结论（这是聊天室气泡，人类会看到）
2. 如果是开发/测试/架构任务 → 用 mcp__teamchat__create_task 创建任务:
   - agent: "cici咪" / "coco咪" / "soso咪"
   - title: 简短标题
   - prompt: 给 agent 的完整指令（先读文档，再执行任务）
   - depends_on: 依赖的任务 ID 列表（通常是空 []）
3. 如果是简单问答 → 只回复文字即可
4. 如果需要澄清 → 回复文字问人类

注意:
- 创建任务后 Engine 会自动派发给对应 agent
- 你自己要做的事（写文档、开 Issue）也创建任务给自己（agent="cici咪"）
- 保持简洁，不要过度分析
"""

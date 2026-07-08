"""
Configuration management for TeamChat Engine.

Loads settings from environment variables with sensible defaults.
Never reads .env files — tokens must be in shell environment.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AgentIdentity:
    """Immutable identity for one AI agent."""
    name: str           # e.g. "cici咪"
    cli: str            # e.g. "claude"
    role: str           # e.g. "架构师 / Tech Lead"
    git_name: str       # e.g. "cici咪 (Claude Architect)"
    git_email: str      # e.g. "claude@teamchat.local"
    token_env: str      # e.g. "TEAMCHAT_CICI_TOKEN"
    cli_path_env: str   # e.g. "TEAMCHAT_CLAUDE_PATH"


# ---- Agent definitions ----

AGENT_CICI = AgentIdentity(
    name="cici咪",
    cli="claude",
    role="架构师 / Tech Lead",
    git_name="cici咪 (Claude Architect)",
    git_email="claude@teamchat.local",
    token_env="TEAMCHAT_CICI_TOKEN",
    cli_path_env="TEAMCHAT_CLAUDE_PATH",
)

AGENT_COCO = AgentIdentity(
    name="coco咪",
    cli="codex",
    role="全栈开发 / Feature Builder",
    git_name="coco咪 (Codex Developer)",
    git_email="codex@teamchat.local",
    token_env="TEAMCHAT_COCO_TOKEN",
    cli_path_env="TEAMCHAT_CODEX_PATH",
)

AGENT_SOSO = AgentIdentity(
    name="soso咪",
    cli="cursor",
    role="集成工程师 / QA",
    git_name="soso咪 (Cursor QA)",
    git_email="cursor@teamchat.local",
    token_env="TEAMCHAT_SOSO_TOKEN",
    cli_path_env="TEAMCHAT_CURSOR_PATH",
)

ALL_AGENTS = (AGENT_CICI, AGENT_COCO, AGENT_SOSO)

# ---- CLI command templates ----

CLI_TEMPLATES: dict[str, list[str]] = {
    "claude": ["claude", "--print", "--output-format", "json", "{prompt}"],
    "codex": ["codex", "exec", "{prompt}"],
    "cursor": ["cursor-agent", "{prompt}"],
}


@dataclass(frozen=True)
class Config:
    """Immutable application config, loaded once at startup."""

    repo_owner: str
    repo_name: str
    repo_url: str

    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    # Runtime paths
    teamchat_dir: Path = field(init=False)
    messages_dir: Path = field(init=False)
    sessions_dir: Path = field(init=False)

    # Agent tokens (lazy — accessed via method, never logged)
    _tokens: dict[str, str | None] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "teamchat_dir", self.project_root / ".teamchat")
        object.__setattr__(self, "messages_dir", self.teamchat_dir / "messages")
        object.__setattr__(self, "sessions_dir", self.teamchat_dir / "sessions")

    def get_token(self, agent: AgentIdentity) -> str | None:
        """Get GitHub PAT token for an agent. Returns None if not set."""
        return os.getenv(agent.token_env)

    def get_cli_path(self, agent: AgentIdentity) -> str:
        """Get CLI path, falling back to auto-detection."""
        env_path = os.getenv(agent.cli_path_env)
        if env_path:
            return env_path
        return agent.cli  # fallback: rely on PATH

    def get_cli_command(self, agent: AgentIdentity, prompt: str) -> list[str]:
        """Build the full CLI command for an agent with the given prompt."""
        template = CLI_TEMPLATES[agent.cli]
        return [part.format(prompt=prompt) for part in template]


def load_config() -> Config:
    """Load configuration from environment. Call once at startup."""
    full_repo = os.getenv("TEAMCHAT_GITHUB_REPO", "YancyLyx/TeamChat")
    owner, _, name = full_repo.partition("/")

    return Config(
        repo_owner=owner,
        repo_name=name,
        repo_url=f"https://github.com/{full_repo}",
    )

"""
Shared pytest fixtures for TeamChat integration tests.
"""

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from engine.config import (
    AGENT_CICI,
    AGENT_COCO,
    AGENT_SOSO,
    ALL_AGENTS,
    AgentIdentity,
    CLI_TEMPLATES,
    load_config,
)

HELLO_PROMPT = "Say hello in one short sentence. Output ONLY the greeting."

CLI_BINARY_NAMES = {
    "claude": "claude",
    "codex": "codex",
    "cursor": "cursor-agent",
}

ALL_AGENTS_BY_CLI = {
    AGENT_CICI.cli: AGENT_CICI,
    AGENT_COCO.cli: AGENT_COCO,
    AGENT_SOSO.cli: AGENT_SOSO,
}


def cli_in_path(agent: AgentIdentity) -> bool:
    binary = CLI_BINARY_NAMES.get(agent.cli, agent.cli)
    return shutil.which(binary) is not None


def token_is_set(agent: AgentIdentity) -> bool:
    return bool(os.getenv(agent.token_env))


def skip_if_cli_missing(agent: AgentIdentity) -> None:
    binary = CLI_BINARY_NAMES.get(agent.cli, agent.cli)
    if not shutil.which(binary):
        pytest.skip(f"{binary} not found in PATH")


def skip_if_not_ready_for_real_call(agent: AgentIdentity) -> None:
    skip_if_cli_missing(agent)
    if not token_is_set(agent):
        pytest.skip(f"{agent.token_env} not set")


def run_cli_version_check(binary: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binary, *extra_args],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


@dataclass
class IntegrationTestConfig:
    """Mutable config wrapper for tests that inject custom CLI commands."""

    repo_owner: str = "YancyLyx"
    repo_name: str = "TeamChat"
    repo_url: str = "https://github.com/YancyLyx/TeamChat"
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    command_builder: Callable[[AgentIdentity, str], list[str]] | None = None

    def get_cli_command(self, agent: AgentIdentity, prompt: str) -> list[str]:
        if self.command_builder is not None:
            return self.command_builder(agent, prompt)
        template = CLI_TEMPLATES[agent.cli]
        return [part.format(prompt=prompt) for part in template]


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def runner(config):
    from engine.runner import AgentRunner

    return AgentRunner(config)


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (real CLI invocations)")


@pytest.fixture(params=ALL_AGENTS, ids=lambda a: a.cli)
def agent(request):
    return request.param

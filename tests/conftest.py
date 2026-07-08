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
    config.addinivalue_line(
        "markers",
        "e2e: Dashboard Playwright end-to-end tests (requires browsers + dev servers)",
    )


@pytest.fixture(params=ALL_AGENTS, ids=lambda a: a.cli)
def agent(request):
    return request.param


# ---- Dashboard E2E fixtures (Playwright) ----

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
    }


@pytest.fixture(scope="session")
def dashboard_url():
    from tests.e2e_support import DASHBOARD_URL

    return DASHBOARD_URL


@pytest.fixture(scope="session")
def api_url():
    from tests.e2e_support import API_URL

    return API_URL


@pytest.fixture(scope="session")
def e2e_servers(tmp_path_factory):
    pytest.importorskip("playwright")
    if not DASHBOARD_DIR.joinpath("package.json").exists():
        pytest.skip("dashboard/ source not available")

    import threading

    import uvicorn

    from tests.e2e_support import (
        find_free_port,
        install_mock_runner,
        release_port,
        start_vite_dev_server,
        wait_for_http,
    )

    release_port(8000)
    release_port(5173)

    api_port = find_free_port()
    dashboard_port = find_free_port()
    while dashboard_port == api_port:
        dashboard_port = find_free_port()

    api_url = f"http://127.0.0.1:{api_port}"
    dashboard_url = f"http://127.0.0.1:{dashboard_port}"

    e2e_root = tmp_path_factory.mktemp("teamchat_e2e")
    (e2e_root / ".teamchat" / "messages").mkdir(parents=True)

    restore_runner = install_mock_runner(project_root=e2e_root)

    import api.main as api_main_module
    import engine.runner as runner_module

    api_main_module.create_runner = runner_module.create_runner
    from api.main import app as fastapi_app

    api_config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=api_port,
        log_level="warning",
    )
    api_server = uvicorn.Server(api_config)
    api_thread = threading.Thread(target=api_server.run, daemon=True)
    api_thread.start()

    vite_proc = None
    try:
        wait_for_http(f"{api_url}/api/health")
        vite_proc = start_vite_dev_server(DASHBOARD_DIR, api_port, dashboard_port)
        wait_for_http(dashboard_url)

        yield {
            "api_url": api_url,
            "dashboard_url": dashboard_url,
            "app": fastapi_app,
            "api_server": api_server,
            "api_thread": api_thread,
        }
    finally:
        api_server.should_exit = True
        api_thread.join(timeout=10)
        if vite_proc is not None:
            vite_proc.terminate()
            vite_proc.wait(timeout=10)
        restore_runner()


@pytest.fixture(scope="session")
def e2e_app(e2e_servers):
    return e2e_servers["app"]

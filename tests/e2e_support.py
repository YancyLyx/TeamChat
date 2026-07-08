"""
Helpers for Dashboard Playwright E2E tests.

Provides a mock AgentRunner so tests do not invoke real agent CLIs.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from engine.config import AgentIdentity, Config
from engine.runner import AgentResult, AgentRunner, AgentTask

API_HOST = "127.0.0.1"
API_PORT = 8000
DASHBOARD_PORT = 5173
API_URL = f"http://{API_HOST}:{API_PORT}"
DASHBOARD_URL = f"http://{API_HOST}:{DASHBOARD_PORT}"

MOCK_RUN_DELAY_SECONDS = 1.2


def inject_bus_message(app, content: str) -> None:
    """Send a bus message on the API event loop (safe from test threads)."""
    from engine.bus import MessageType
    from engine.config import AGENT_CICI, AGENT_COCO

    def _send() -> None:
        app.state.bus.send(
            from_agent=AGENT_CICI,
            to_agent=AGENT_COCO,
            msg_type=MessageType.TASK_ASSIGNMENT,
            content=content,
            github_ref="#4",
        )

    app.state.loop.call_soon_threadsafe(_send)


class E2EMockRunner(AgentRunner):
    """Deterministic runner for Dashboard E2E tests."""

    async def run(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        working_dir: Path | None = None,
    ) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        started_ms = time.monotonic()
        await asyncio.sleep(MOCK_RUN_DELAY_SECONDS)

        prompt_lower = task.prompt.lower()
        failed = "fail" in prompt_lower or "error" in prompt_lower
        output = "Mock task failed" if failed else "Hello from mock agent!"
        exit_code = 1 if failed else 0
        duration_ms = int((time.monotonic() - started_ms) * 1000)

        return AgentResult(
            agent_name=agent.name,
            task_prompt=task.full_prompt(),
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            token_usage={"input_tokens": 10, "output_tokens": 5} if not failed else {},
            started_at=started_at.isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


def install_mock_runner(project_root: Path | None = None):
    """Patch create_runner to return E2EMockRunner. Returns a restore callback."""
    import engine.config as config_mod
    import engine.runner as runner_mod

    original_create = runner_mod.create_runner
    original_load = config_mod.load_config
    root = project_root

    def isolated_load_config():
        config = original_load()
        if root is None:
            return config
        return config_mod.Config(
            repo_owner=config.repo_owner,
            repo_name=config.repo_name,
            repo_url=config.repo_url,
            project_root=root,
        )

    def mock_create_runner(config: Config | None = None) -> E2EMockRunner:
        if config is None:
            config = isolated_load_config()
        return E2EMockRunner(config)

    config_mod.load_config = isolated_load_config
    runner_mod.create_runner = mock_create_runner

    def restore():
        config_mod.load_config = original_load
        runner_mod.create_runner = original_create

    return restore


def wait_for_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def ensure_dashboard_deps(dashboard_dir: Path) -> None:
    if (dashboard_dir / "node_modules").exists():
        return
    subprocess.run(
        ["npm", "install"],
        cwd=dashboard_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def start_vite_dev_server(dashboard_dir: Path) -> subprocess.Popen[str]:
    ensure_dashboard_deps(dashboard_dir)
    return subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", API_HOST, "--port", str(DASHBOARD_PORT)],
        cwd=dashboard_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

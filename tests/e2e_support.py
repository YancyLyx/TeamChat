"""
Helpers for Dashboard Playwright E2E tests.

Provides a mock AgentRunner so tests do not invoke real agent CLIs.
"""

from __future__ import annotations

import asyncio
import os
import socket
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

MOCK_RUN_DELAY_SECONDS = 0.8
MOCK_GREETING_DELAY_SECONDS = 0.15
MOCK_AGENT_REPLY = "Hello from mock agent!"
MOCK_GREETING_REPLY_SUFFIX = "你好！我在。"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def release_port(port: int) -> None:
    subprocess.run(
        ["sh", "-c", f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"],
        check=False,
        capture_output=True,
    )


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


def broadcast_ws(app, message: dict) -> None:
    """Broadcast a WebSocket message from the API event loop."""

    async def _send() -> None:
        await app.state.ws_manager.broadcast(message)

    future = asyncio.run_coroutine_threadsafe(_send(), app.state.loop)
    future.result(timeout=5)


def seed_task_table(
    app,
    *,
    agent: str,
    title: str,
    status: str = "pending",
    depends_on: list[int] | None = None,
) -> int:
    """Insert a TaskTable row on the API event loop."""
    result_holder: dict[str, int] = {}

    def _write() -> None:
        task = app.state.task_table.create(
            agent, title, depends_on=depends_on or []
        )
        if status != "pending":
            app.state.task_table.update(task.id, status=status)
        result_holder["id"] = task.id

    app.state.loop.call_soon_threadsafe(_write)
    deadline = time.time() + 5
    while "id" not in result_holder and time.time() < deadline:
        time.sleep(0.05)
    if "id" not in result_holder:
        raise RuntimeError("Timed out seeding task table row")
    return result_holder["id"]


def seed_session(
    app,
    *,
    agent_name: str,
    prompt: str,
    output: str,
    tag: str = "prod",
    token_usage: dict | None = None,
) -> int:
    """Insert a session row on the API event loop (for tag-filter E2E tests)."""
    result_holder: dict[str, int] = {}

    def _write() -> None:
        result_holder["id"] = app.state.store.log(
            agent_name=agent_name,
            prompt=prompt,
            output=output,
            exit_code=0,
            duration_ms=100,
            task_type="e2e_seed",
            tag=tag,
            token_usage=token_usage,
        )

    app.state.loop.call_soon_threadsafe(_write)
    deadline = time.time() + 5
    while "id" not in result_holder and time.time() < deadline:
        time.sleep(0.05)
    if "id" not in result_holder:
        raise RuntimeError("Timed out seeding session row")
    return result_holder["id"]


class E2EMockRunner(AgentRunner):
    """Deterministic runner for Dashboard E2E tests."""

    def _build_result(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        output: str,
        *,
        exit_code: int = 0,
        duration_ms: int = 100,
    ) -> AgentResult:
        now = datetime.now(timezone.utc).isoformat()
        return AgentResult(
            agent_name=agent.name,
            task_prompt=task.full_prompt(),
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            token_usage={"input_tokens": 10, "output_tokens": 5} if exit_code == 0 else {},
            started_at=now,
            finished_at=now,
        )

    async def _mock_execute(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        *,
        use_continue: bool = False,
    ) -> AgentResult:
        started_ms = time.monotonic()
        prompt = task.full_prompt()
        prompt_lower = prompt.lower()

        if "人类在聊天室发了" in prompt:
            await asyncio.sleep(MOCK_GREETING_DELAY_SECONDS)
            output = f"{agent.name} {MOCK_GREETING_REPLY_SUFFIX}"
            duration_ms = int((time.monotonic() - started_ms) * 1000)
            return self._build_result(agent, task, output, duration_ms=duration_ms)

        if "你是 TeamChat 项目的架构师" in prompt:
            await asyncio.sleep(MOCK_GREETING_DELAY_SECONDS)
            output = "ANSWER: TeamChat 运行正常，三只猫在线。"
            duration_ms = int((time.monotonic() - started_ms) * 1000)
            return self._build_result(agent, task, output, duration_ms=duration_ms)

        failed = "fail" in prompt_lower or "error" in prompt_lower
        if failed:
            await asyncio.sleep(MOCK_RUN_DELAY_SECONDS)
            duration_ms = int((time.monotonic() - started_ms) * 1000)
            return self._build_result(
                agent, task, "Mock task failed", exit_code=1, duration_ms=duration_ms
            )

        if "E2E_COLLAPSE" in prompt:
            output = (
                "THINKING: analyzing the request\n"
                "TOOL_CALLS: read_file(path='README.md')\n"
                f"{MOCK_AGENT_REPLY}"
            )
        elif use_continue:
            output = f"[continue] {MOCK_AGENT_REPLY}"
        else:
            output = MOCK_AGENT_REPLY

        await asyncio.sleep(MOCK_RUN_DELAY_SECONDS)
        duration_ms = int((time.monotonic() - started_ms) * 1000)
        return self._build_result(agent, task, output, duration_ms=duration_ms)

    async def run(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        working_dir: Path | None = None,
    ) -> AgentResult:
        return await self._run(agent, task, working_dir, use_continue=False)

    async def _run(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        working_dir: Path | None = None,
        use_continue: bool = False,
        session_id: str | None = None,
    ) -> AgentResult:
        resuming = bool(session_id) or use_continue
        result = await self._mock_execute(agent, task, use_continue=resuming)
        if not resuming:
            result.cli_session_id = f"e2e-{agent.cli}-coldstart"
        return result

    async def run_with_context(
        self,
        agent: AgentIdentity,
        task: AgentTask,
        working_dir: Path | None = None,
    ) -> AgentResult:
        use_continue = self._has_session(agent)
        result = await self._mock_execute(agent, task, use_continue=use_continue)
        self._sessions[agent.name] = True
        return result


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

    # api.main imports create_runner by value — re-bind after patch
    import sys

    api_main = sys.modules.get("api.main")
    original_api_create = getattr(api_main, "create_runner", None) if api_main else None
    if api_main is not None:
        api_main.create_runner = mock_create_runner

    def restore():
        config_mod.load_config = original_load
        runner_mod.create_runner = original_create
        if api_main is not None and original_api_create is not None:
            api_main.create_runner = original_api_create

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


def start_vite_dev_server(dashboard_dir: Path, api_port: int, dashboard_port: int) -> subprocess.Popen[str]:
    ensure_dashboard_deps(dashboard_dir)
    env = os.environ.copy()
    env["VITE_API_PORT"] = str(api_port)
    return subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", API_HOST, "--port", str(dashboard_port)],
        cwd=dashboard_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )

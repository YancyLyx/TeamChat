"""#96 e2e 验收 — 真实 TaskScheduler.run() 循环 + 隔离 DB + mock agent 执行。

验证 ADR-006 验收标准 5：A(coco咪)、B(soso咪) 独立，C 依赖 A+B。
断言：A、B 同时 running（并行）；C 保持 pending 直到 A、B done（审核后）才派发。

安全：全部数据在临时目录，不碰真实 .teamchat/teamchat.db；不 spawn 真实 CLI。
"""

import asyncio
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import Config
from engine.router import Router
from engine.runner import AgentResult
from engine.session_store import SessionStore
from engine.task_scheduler import TaskScheduler
from engine.task_table import TaskTable


def make_result(agent_name: str) -> AgentResult:
    return AgentResult(
        agent_name=agent_name, task_prompt="x", output="done",
        exit_code=0, duration_ms=300,
        started_at="t", finished_at="t", cli_session_id="sid",
    )


async def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="tc_e2e_96_"))
    config = Config(repo_owner="t", repo_name="t",
                    repo_url="https://github.com/t/t", project_root=root)

    ss = SessionStore(config); ss.init()
    tt = TaskTable(config); tt.init()

    # mock runner：记录每任务 spawn 开始时刻，sleep 模拟执行
    started: dict[str, float] = {}
    spawn_order: list[str] = []

    async def fake_run(agent, task, use_continue=False, session_id=None,
                       on_stream=None, **kwargs):
        started[task.prompt] = time.monotonic()
        spawn_order.append(task.prompt)
        await asyncio.sleep(0.5)
        return make_result(agent.name)

    runner = MagicMock(); runner._run = fake_run
    router = Router()
    relay = AsyncMock()
    store = MagicMock()
    session_store = MagicMock()
    session_store.get_agent_session_id.return_value = "sid"

    scheduler = TaskScheduler(runner, router, tt, session_store, store, relay)

    # 建 A(coco咪)、B(soso咪)、C(depends_on=[A,B] → coco咪)
    a = tt.create(agent="coco咪", title="A", description="并行验收任务A")
    b = tt.create(agent="soso咪", title="B", description="并行验收任务B")
    c = tt.create(agent="coco咪", title="C", description="依赖AB的任务C",
                  depends_on=[a.id, b.id])

    loop_task = asyncio.create_task(scheduler.run())
    checks: list[tuple[str, bool]] = []
    try:
        # 观察窗口 1：A、B 应并行 running，C 保持 pending
        for _ in range(30):
            t_a = tt.get(a.id); t_b = tt.get(b.id); t_c = tt.get(c.id)
            if t_a.status == "running" and t_b.status == "running":
                break
            await asyncio.sleep(0.2)
        checks.append(("A、B 同时 running", t_a.status == "running" and t_b.status == "running"))
        checks.append(("A、B 并行启动（间隔 < 0.5s 执行时间）",
                       abs(started.get("并行验收任务A", 9e9) - started.get("并行验收任务B", -9e9)) < 0.5))
        checks.append(("并行期间 C 保持 pending", tt.get(c.id).status == "pending"))

        # 观察窗口 2：A、B 完成后（等审核，状态仍 running）C 仍 pending
        for _ in range(40):
            if len(spawn_order) >= 2 and tt.get(a.id).status == "running":
                break
            await asyncio.sleep(0.2)
        checks.append(("A、B 完成但未审核时 C 不被派发", tt.get(c.id).status == "pending"))

        # 模拟 cici咪 审核：A、B 标 done → C 应被派发
        tt.update(a.id, status="done")
        tt.update(b.id, status="done")
        for _ in range(40):
            if tt.get(c.id).status == "running":
                break
            await asyncio.sleep(0.2)
        checks.append(("A、B done 后 C 被派发", tt.get(c.id).status == "running"))
        checks.append(("C 在 A、B 之后才执行",
                       started.get("依赖AB的任务C", 9e9) > started.get("并行验收任务A", 0) and started.get("依赖AB的任务C", 9e9) > started.get("并行验收任务B", 0)))
    finally:
        scheduler._running = False
        loop_task.cancel()
        await asyncio.gather(loop_task, return_exceptions=True)
        tt.close(); ss.close()

    print("=" * 56)
    print(f"#96 e2e 验收（隔离库: {root}）")
    print("=" * 56)
    ok = True
    for label, passed in checks:
        print(f"  {'✅' if passed else '❌'} {label}")
        ok = ok and passed
    print(f"spawn 顺序: {spawn_order}")
    print("=" * 56)
    print("验收结论:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

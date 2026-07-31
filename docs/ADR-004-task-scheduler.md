# ADR-004: Agent 间任务调度与通信

**状态**: Draft
**日期**: 2026-07-31
**作者**: cici咪
**参与者**: coco咪（前端），soso咪（测试）

---

## 背景

当前 TeamChat 系统是**拉模式**：
- 只有人类在 Dashboard 发消息时，`/api/chat` 才会 spawn agent
- cici咪 通过 MCP `create_task` 写数据库，但系统不会自动执行
- agent 之间无法主动通信（`bus.py` 写了 JSON 文件，没人读）

问题场景：
```
人类: "@cici咪 帮我实现黑暗模式"
  ↓
cici咪 分析: "需要给 coco咪 分派一个任务"
  ↓
cici咪: mcp__teamchat__create_task(agent="coco咪", title="实现黑暗模式", ...)
  ↓
❌ 数据库里多了条记录，但 coco咪 永远不会收到通知
```

---

## 决策

引入**任务调度器（Task Scheduler）**，一个独立的后台服务，负责：
1. 监听 `task_table` 的 pending 任务
2. 自动 spawn 对应 agent（通过 `engine/runner`）
3. 回写结果到 `task_table`
4. 通过 `engine/bus` 广播任务事件

调度器作为独立进程运行（或作为 FastAPI 后台任务），与 API、Dashboard 并行。

---

## 技术方案

### 4.1. 架构图

```
┌─────────────┐
│   Dashboard │ (WebSocket)
└──────┬──────┘
       │
┌──────▼───────────────────────────────────┐
│          FastAPI (api/main.py)           │
│  - /api/chat (人类发消息触发 agent)       │
│  - WebSocket 实时推送                    │
└──────┬───────────────────────────────────┘
       │
┌──────▼───────────────────────────────────┐
│     Task Scheduler (engine/scheduler.py) │
│  - 轮询 task_table                       │
│  - spawn agent (runner._run)             │
│  - 回写结果 + bus 广播                   │
└──────┬───────────────────────────────────┘
       │
┌──────▼───────────────────────────────────┐
│           Engine Core                    │
│  - runner.py: spawn Claude/Codex/Cursor  │
│  - router.py: agent 繁忙状态管理          │
│  - bus.py: agent 间消息总线 (JSON 文件)  │
│  - task_table.py: SQLite 任务表          │
│  - session_store.py: CLI session 持久化  │
└──────────────────────────────────────────┘
```

### 4.2. Task Scheduler 实现

**文件**: `engine/scheduler.py`

```python
"""
Task Scheduler — 监听 task_table 的 pending 任务，自动 spawn agent。

独立进程（或 FastAPI 后台任务），轮询间隔 2s。
"""

import asyncio
import logging
from datetime import datetime, timezone

from engine.config import ALL_AGENTS, Config, load_config
from engine.runner import AgentTask, create_runner
from engine.router import Router
from engine.session_store import create_session_store
from engine.task_table import Task, create_task_table

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度器：polling + auto-dispatch."""

    POLL_INTERVAL = 2.0  # seconds

    def __init__(self, config: Config):
        self.config = config
        self.task_table = create_task_table(config)
        self.runner = create_runner(config)
        self.router = Router()
        self.session_store = create_session_store(config)
        self._running = False

    async def _run_one(self, task: Task):
        """执行单个任务：spawn agent → 更新 task_table → 广播."""
        # 查找对应的 AgentIdentity
        target = None
        for agent in ALL_AGENTS:
            if agent.name == task.agent:
                target = agent
                break
        if not target:
            logger.error(f"⚠️  Task #{task.id}: unknown agent {task.agent}")
            self.task_table.update(task.id, status="failed", output_summary=f"Unknown agent: {task.agent}")
            return

        # 标记为 running
        self.task_table.update(task.id, status="running", started_at=datetime.now(timezone.utc).isoformat())

        # Spawn agent
        try:
            agent_task = AgentTask(prompt=task.description or task.title, timeout_seconds=300)

            # Resume session if exists
            sid = self.session_store.get_agent_session_id(task.teamchat_session_id, target.cli)
            result = await self.runner._run(
                target,
                agent_task,
                use_continue=bool(sid),
                session_id=sid or None,
            )

            # 保存新 session ID
            if result.cli_session_id and not sid:
                self.session_store.set_agent_session_id(
                    task.teamchat_session_id, target.cli, result.cli_session_id,
                )

            # 更新任务状态
            self.task_table.update(
                task.id,
                status="done" if result.success else "failed",
                output_summary=result.output[:500],
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(f"✅ Task #{task.id} ({task.agent}): done")

            # TODO: 通过 bus 广播任务完成
            # self.config.bus.send(...)

        except Exception as exc:
            logger.error(f"❌ Task #{task.id} failed: {exc}")
            self.task_table.update(
                task.id,
                status="failed",
                output_summary=f"Exception: {exc}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

    async def run(self):
        """主循环：poll → dispatch."""
        self._running = True
        logger.info("🚀 Task Scheduler started")

        while self._running:
            pending = self.task_table.list_tasks(status="pending")
            if pending:
                logger.info(f"📋 Found {len(pending)} pending task(s)")
                for task in pending:
                    await self._run_one(task)
            await asyncio.sleep(self.POLL_INTERVAL)

    def stop(self):
        self._running = False
        logger.info("🛑 Task Scheduler stopped")


async def main():
    """入口：启动调度器。"""
    config = load_config()
    scheduler = TaskScheduler(config)

    try:
        await scheduler.run()
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

### 4.3. 集成到 FastAPI（可选）

如果不想单独进程，可以集成到 `api/main.py` 的 lifespan：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有初始化 ...

    # 启动 Task Scheduler 后台任务
    scheduler = TaskScheduler(config)
    app.state.scheduler = scheduler
    scheduler_task = asyncio.create_task(scheduler.run())

    logger.info("TeamChat API ready")
    yield

    scheduler.stop()
    # ... 现有清理 ...
```

### 4.4. Bus 通信扩展

`scheduler.py` 执行完任务后，通过 `bus` 广播：

```python
# 在 _run_one 完成后：
self.config.bus.send(
    from_agent=target,
    to_agent="all",
    msg_type="task_complete",
    content=f"Task #{task.id} '{task.title}' 完成",
    github_ref=f"#{task.id}",
)
```

Dashboard 的 WebSocket 会收到 `bus.subscribe("all", ...)` 的回调，显示为系统消息。

---

## 后续任务

| # | 内容 | 谁 |
|---|---|---|
| 1 | 实现 `engine/scheduler.py` | cici咪 |
| 2 | 添加 `bus` 广播集成 | cici咪 |
| 3 | Dashboard 显示 bus 消息 | coco咪 |
| 4 | 端到端测试（cici咪 create_task → coco咪 执行 → 结果回传） | soso咪 |
| 5 | 文档更新 | cici咪 |

---

## 未决问题

- **调度模式**: 当前是简单 polling，后续可改为基于 SQLite trigger 或文件监听
- **并发限制**: 同一 agent 同时只能跑一个任务（由 Router.mark_busy 保护），但可以并行跑不同 agent
- **失败重试**: 失败任务是否自动重试？（当前不支持）
- **任务依赖**: `depends_on` 字段暂未使用，后续可支持 DAG 调度

---

## 参考文档

- ADR-003: CLI 逐行输出 + 审批卡片
- PROGRESS.md: 当前进度 + 待办
- engine/task_table.py: 任务表 schema
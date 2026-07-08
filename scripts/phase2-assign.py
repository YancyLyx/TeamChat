#!/usr/bin/env python3
"""cici咪 创建 Phase 2 任务 Issue，分配给 coco咪 和 soso咪"""

import asyncio
import os
import sys

# Ensure engine is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import load_config, AGENT_CICI, AGENT_COCO, AGENT_SOSO
from engine.github_client import GitHubClient


async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    # --- Issue #1: coco咪 — FastAPI + WebSocket ---
    issue1 = await cici.create_issue(
        title="[Phase 2] FastAPI 应用入口 + WebSocket API",
        body="""## 任务

为 TeamChat Engine 创建 FastAPI 应用入口和 WebSocket 实时推送 API。

## 背景

核心引擎（engine/）已经完成：
- `engine/config.py` — Agent 身份 + 不可变配置
- `engine/runner.py` — CLI 驱动层 (asyncio.subprocess)
- `engine/router.py` — 声明式任务路由器
- `engine/bus.py` — 文件系统消息总线
- `engine/github_client.py` — GitHub API 适配器
- `engine/store.py` — SQLite 会话存储

## 要做的事

### 1. FastAPI 应用入口 (`api/main.py`)
- 启动时初始化 SessionStore 和 AgentRunner
- 提供 REST endpoints:
  - `GET /api/agents` — 列出三个 agent 及其状态
  - `GET /api/sessions?agent=cici&limit=20` — 查询会话历史
  - `POST /api/tasks` — 提交新任务（指定 agent + prompt）
  - `GET /api/tasks/{task_id}` — 查询任务结果
  - `GET /api/stats` — 获取所有 agent 的统计信息
- 提供 WebSocket endpoint:
  - `WS /ws` — 实时推送 agent 活动（任务开始/完成/错误）

### 2. WebSocket 实时推送
- 当 AgentRunner 开始/完成一个任务时，通过 WS 广播
- 当 MessageBus 有新的 agent 间消息时，通过 WS 推送
- 消息格式: `{"type": "task_started"|"task_complete"|"message", "data": {...}}`

### 3. 依赖
- 使用 FastAPI 内置的 WebSocket 支持
- 不需要额外的消息队列（Redis 等）
- 所有状态通过 engine/ 模块管理

## 技术要求
- Python 3.12+ type hints
- async/await 模式
- 遵循 engine/ 的代码风格
- 不需要写测试（soso咪 会写）

## 文件位置
```
api/
├── __init__.py
├── main.py        ← FastAPI 应用 + WebSocket
├── routes/
│   ├── __init__.py
│   ├── agents.py  ← /api/agents
│   ├── sessions.py← /api/sessions
│   └── tasks.py   ← /api/tasks
└── schemas.py     ← Pydantic models
```

## 参考
- 设计文档: `docs/specs/2026-07-08-teamchat-design.md`
- ADR-001: `docs/decisions/001-tech-stack.md`
- 现有引擎代码: `engine/`
""",
        labels=["phase-2", "api"],
        assignee="YancyLyx",  # GitHub username for coco咪
    )
    print(f"✅ Issue #{issue1.number}: {issue1.title}")
    print(f"   {issue1.url}")

    # --- Issue #2: soso咪 — 集成测试 ---
    issue2 = await cici.create_issue(
        title="[Phase 2] CLI Runner 集成测试",
        body="""## 任务

为 `engine/runner.py` 的 CLI 驱动层编写集成测试，验证三个 agent 的 CLI 是否能被正确调用。

## 背景

cici咪 已经完成了：
- `engine/runner.py` — AgentRunner 类，封装 asyncio.subprocess 调用
- `engine/config.py` — Agent 身份和 CLI 命令模板
- `tests/test_engine.py` — 17 个单元测试（数据模型、路由、消息总线）

但还没有**集成测试**——验证真实的 CLI 调用（claude --print、codex exec、cursor-agent）。

## 要做的事

### 1. CLI 路径检测测试
验证三个 CLI 在 PATH 中可被找到：
- `claude --version` 或 `claude --help` 返回正常
- `codex --version` 或 `codex --help` 返回正常
- `cursor-agent` 存在且可执行

### 2. 真实 CLI 调用测试
对每个 agent 发送一个简单 prompt，验证：
- 进程正常启动和退出
- 退出码为 0
- stdout 有输出（非空）
- 超时机制生效（设 10s 超时，发一个简单 prompt）

测试 prompt 示例:
```
"Say hello in one short sentence. Output ONLY the greeting."
```

### 3. 错误处理测试
- 测试不存在的 CLI 路径 → 应报错
- 测试极短超时（1s）→ 应触发 TIMEOUT
- 测试空 prompt → 应正常处理或报错

### 4. 输出解析测试
- Claude 的 `--output-format json` 输出应被正确解析
- 提取 token usage 信息

## 文件位置
```
tests/
├── test_engine.py          ← 现有单元测试（不要改）
├── test_integration.py     ← 新建: 集成测试
└── conftest.py             ← 新建: pytest fixtures (如果需要)
```

## 注意事项
- 集成测试需要 agent CLI 在 PATH 中，如果找不到就 skip（不要 FAIL）
- 测试前检查 `TEAMCHAT_CICI_TOKEN` 等环境变量是否存在
- 集成测试可能较慢（每个 CLI 调用几秒），用 `@pytest.mark.slow` 标记

## 参考
- `engine/runner.py` — AgentRunner 实现
- `engine/config.py` — CLI_TEMPLATES 定义
- `tests/test_engine.py` — 现有测试风格
""",
        labels=["phase-2", "testing"],
        assignee="YancyLyx",
    )
    print(f"✅ Issue #{issue2.number}: {issue2.title}")
    print(f"   {issue2.url}")

    await cici.close()
    print("\n🎯 两个 Issue 创建完毕！")


if __name__ == "__main__":
    asyncio.run(main())

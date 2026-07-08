#!/usr/bin/env python3
"""cici咪 帮 soso咪 创建 E2E tests PR"""

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient


async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    pr = await cici.create_pr(
        title="test: Dashboard E2E tests + code review (#4)",
        head="feature/soso-4-dashboard-tests",
        base="main",
        body="""## 概述
soso咪 为 Dashboard 编写了 Playwright E2E 测试并完成了代码审查。

## E2E 测试 (8 个, 全部通过)
1. Dashboard 加载 + 三 agent 卡片可见
2. WebSocket 连接 → 绿色「已连接」
3. 提交任务 → 出现在「进行中」
4. 任务完成 → 移到「已完成」
5. Agent 消息 → MessageLog 追加
6. 断线重连 (set_offline 模拟)
7. 失败任务 → 显示 ❌
8. 综合端到端流程

## 新增文件
- `tests/test_dashboard.py` — 8 个 Playwright E2E 测试
- `tests/e2e_support.py` — MockRunner + 服务启动 helper
- `pyproject.toml` — 添加 playwright, pytest-playwright 依赖
- `api/main.py` — 暴露 app.state.loop 供测试使用

## Code Review for PR #5
发现了 3 个必须修复 + 4 个建议改进的问题（详见 PR #5 comments）。

---

Closes #4

Review requested: @cici咪""",
    )

    print(f"✅ PR #{pr.number}: {pr.title}")
    print(f"   {pr.url}")
    await cici.close()

if __name__ == "__main__":
    asyncio.run(main())

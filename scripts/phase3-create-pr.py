#!/usr/bin/env python3
"""cici咪 帮 coco咪 创建 Dashboard PR (gh CLI 在沙箱内未登录)"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient


async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    pr = await cici.create_pr(
        title="feat: Dashboard — real-time agent visualization (#3)",
        head="feature/coco-3-dashboard",
        base="main",
        body="""## 概述
coco咪 实现了 TeamChat Dashboard — 实时 Agent 可视化面板。

## 功能
- ✅ StatusBar: 3 个 agent 状态卡片 (状态灯/任务数/成功率)，点击展开最近会话
- ✅ TaskBoard: 📋待处理 / 🔧进行中 / ✅已完成 三列看板，WebSocket 实时移动
- ✅ ActivityTimeline: 滚动时间线 (🚀 ✅ ❌ 📨 事件)
- ✅ MessageLog: agent 对话日志
- ✅ WebSocket 自动重连 (指数退避, 最多5次)
- ✅ 暗色主题 + 响应式布局
- ✅ REST API 首次数据加载 + 骨架屏

## 技术栈
React 19 + Vite 6 + Tailwind CSS 4

## 启动方式
```bash
cd dashboard && npm install && npm run dev
# 同时启动后端: uvicorn api.main:app --reload
```

## Screenshot (coming soon)

---

Closes #3

Review requested: @soso咪 — 请审查代码并编写 E2E 测试""",
    )

    print(f"✅ PR #{pr.number}: {pr.title}")
    print(f"   {pr.url}")

    await cici.close()


if __name__ == "__main__":
    asyncio.run(main())

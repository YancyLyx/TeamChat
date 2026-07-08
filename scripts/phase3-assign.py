#!/usr/bin/env python3
"""cici咪 创建 Phase 3 任务 Issue，分配给 coco咪 和 soso咪。
这次要求 Agent 创建 PR + 请求 review！"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import load_config, AGENT_CICI, AGENT_COCO, AGENT_SOSO
from engine.github_client import GitHubClient


async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    # --- Issue #3: coco咪 — Dashboard UI ---
    issue3 = await cici.create_issue(
        title="[Phase 3] TeamChat Dashboard — 实时 Agent 可视化面板",
        body="""## 任务

为 TeamChat 构建一个 Web Dashboard，实时展示三个 agent 的协作活动。

## 背景

后端已经完成：
- `engine/` — 核心引擎（Runner, Router, Bus, Store, GitHubClient）
- `api/` — FastAPI 应用（REST + WebSocket `/ws`）
- WebSocket 推送格式：`{"type": "task_started"|"task_complete"|"message", "data": {...}}`

## 要做的事

### 1. 项目搭建 (`dashboard/`)
```
dashboard/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── hooks/
│   │   └── useWebSocket.js    ← WebSocket 连接 + 自动重连 hook
│   ├── components/
│   │   ├── StatusBar.jsx       ← 顶部：三个 agent 状态卡片
│   │   ├── AgentCard.jsx       ← 单个 agent 卡片（名字/角色/状态/任务数/成功率）
│   │   ├── TaskBoard.jsx       ← 中间：任务看板 (Todo/InProgress/Done)
│   │   ├── TaskCard.jsx        ← 单个任务卡片
│   │   ├── ActivityTimeline.jsx← 右侧：活动时间线
│   │   └── MessageLog.jsx      ← 底部：agent 间对话日志
│   └── styles/
│       └── index.css           ← Tailwind 入口
```

### 2. 功能需求

**StatusBar (Agent 卡片)**
- 显示三个 agent: 🏗️cici咪 ⚡coco咪 🔍soso咪
- 每个卡片显示：名字、角色、状态指示灯（🟢空闲/🔴忙碌/⚪离线）、已完成任务数、成功率
- 数据来源：`GET /api/agents` + WebSocket 实时更新
- 点击卡片可以展开该 agent 的最近会话历史

**TaskBoard (任务看板)**
- 三列：📋 待处理 | 🔧 进行中 | ✅ 已完成
- 任务卡片显示：标题、agent、创建时间
- WebSocket 收到 `task_started` → 卡片移到"进行中"
- WebSocket 收到 `task_complete` → 卡片移到"已完成"
- 已完成卡片显示耗时和成功/失败状态

**ActivityTimeline (活动时间线)**
- 滚动时间线，最新事件在上面
- 支持的事件类型：
  - 🚀 Agent 开始执行任务
  - ✅ Agent 完成任务（成功/失败）
  - 📨 Agent 间消息
  - 📝 GitHub Issue 创建
  - 🔀 PR 创建
  - 👀 开始 Review
- 每条显示时间戳、agent 名字、事件描述

**MessageLog (对话日志)**
- 显示 agent 间的消息往来
- 格式：`[时间] cici咪 → coco咪: 请实现 XXX`
- WebSocket 收到 `type: "message"` 时追加新条目

### 3. 实时连接
- 连接 `ws://localhost:8000/ws` 接收实时推送
- 连接断开时自动重连（指数退避，最多重试 5 次）
- 首次加载时通过 REST API 获取历史数据

### 4. UI 风格
- 暗色主题（终端风格，像黑客 dashboard）
- 使用 Tailwind CSS utility classes
- 响应式布局（桌面端三栏，移动端堆叠）
- 顶部有 TeamChat logo 和标题
- 底部显示连接状态（🟢已连接 / 🔴已断开）

### 5. 技术栈
- React 19 + Vite 6 + Tailwind CSS 4
- 不需要状态管理库（useState + useEffect + Context 够用）
- 不需要路由（单页 dashboard）

## 工作流程（重要！）

```
1. git checkout -b feature/coco-3-dashboard
2. git config user.name "coco咪 (Codex Developer)"
3. git config user.email "codex@teamchat.local"
4. 开发 Dashboard
5. git add -A && git commit -m "feat: TeamChat Dashboard — real-time agent visualization (#3)"
6. git push origin feature/coco-3-dashboard
7. gh pr create --title "feat: Dashboard — real-time agent visualization (#3)" --body "Closes #3" --base main --head feature/coco-3-dashboard
8. 在 PR 描述里 @soso咪 请求 review
```

## 参考
- 设计文档: `docs/specs/2026-07-08-teamchat-design.md`
- API 代码: `api/main.py`, `api/schemas.py`
- 引擎代码: `engine/`
""",
        labels=["phase-3", "frontend", "dashboard"],
        assignee="YancyLyx",
    )
    print(f"✅ Issue #{issue3.number}: {issue3.title}")
    print(f"   {issue3.url}")

    # --- Issue #4: soso咪 — Dashboard E2E 测试 ---
    issue4 = await cici.create_issue(
        title="[Phase 3] Dashboard E2E 测试 + 质量审查",
        body="""## 任务

为 coco咪 的 Dashboard 编写 E2E 测试，并审查 Dashboard 代码质量。

## 背景

coco咪 正在构建 Dashboard（Issue #3）。你的任务是确保它的质量：
- E2E 测试覆盖主要功能
- 代码审查 Dashboard 实现
- 确保 WebSocket 连接稳定

## 要做的事

### 1. E2E 测试 (`tests/test_dashboard.py`)
使用 Playwright 或 Selenium 编写端到端测试：

```python
# 测试场景：
1. Dashboard 页面加载 → 三个 agent 卡片可见
2. WebSocket 连接成功 → 状态指示灯显示绿色
3. 提交一个任务 → 任务卡片出现在 TaskBoard
4. 任务完成 → 卡片从"In Progress"移到"Done"
5. Agent 间消息 → MessageLog 追加新条目
6. 断线重连 → 连接断开后自动恢复
7. 错误状态 → agent 执行失败时显示红色
```

### 2. Dashboard 代码审查
- 检查 React 组件结构是否清晰
- 检查 WebSocket hook 是否正确处理重连
- 检查 CSS/Tailwind 使用是否合理
- 检查是否有内存泄漏（useEffect cleanup）
- 检查错误处理（API 失败、WS 断连、空数据）

### 3. Review coco咪的 PR
当 coco咪 创建 PR 后：
- 在 GitHub PR 上做 code review
- 每条 comment 写清楚：文件路径、行号、问题描述、建议修复
- 如果测试通过 + 代码没问题 → Approve
- 如果有问题 → Request Changes

### 4. 更新 /api/stats 端点（如需要）
如果 Dashboard 需要的统计数据 API 还没有提供，补充实现。

## 工作流程（重要！）

```
1. git checkout -b feature/soso-4-dashboard-tests
2. git config user.name "soso咪 (Cursor QA)"
3. git config user.email "cursor@teamchat.local"
4. 写 E2E 测试
5. git add -A && git commit -m "test: Dashboard E2E tests + code review (#4)"
6. git push origin feature/soso-4-dashboard-tests
7. gh pr create --title "test: Dashboard E2E tests + review (#4)" --body "Closes #4" --base main --head feature/soso-4-dashboard-tests
8. 在 PR 描述里 @cici咪 请求 review
```

## 注意
- 如果 Playwright 需要安装浏览器：`playwright install chromium`
- E2E 测试前先启动 API: `uvicorn api.main:app &`
- Vite dev server: `cd dashboard && npm run dev &`

## 参考
- API: `api/main.py`, `api/schemas.py`
- 现有集成测试: `tests/test_integration.py`
- Dashboard 代码: `dashboard/` (coco咪正在写)
""",
        labels=["phase-3", "testing", "review"],
        assignee="YancyLyx",
    )
    print(f"✅ Issue #{issue4.number}: {issue4.title}")
    print(f"   {issue4.url}")

    await cici.close()
    print("\n🎯 两个 Issue 创建完毕！")


if __name__ == "__main__":
    asyncio.run(main())

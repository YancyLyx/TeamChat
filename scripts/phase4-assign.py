#!/usr/bin/env python3
"""cici咪 创建 Phase 4 任务 — 聊天室 Dashboard + 自动路由"""

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.config import load_config, AGENT_CICI, AGENT_COCO, AGENT_SOSO
from engine.github_client import GitHubClient

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    # Issue #5: coco咪 — Chat-room Dashboard
    i5 = await cici.create_issue(
        title="[Phase 4] 聊天室风格 Dashboard 重构",
        body="""## 任务
将现有 Dashboard 重构为 Slack/Discord 风格的聊天室。

## 新布局
```
┌──────────────────────────────────────────────────────────┐
│  🤖 TeamChat                          🟢 已连接          │
├──────────┬────────────────────────────────┬──────────────┤
│ 左侧栏    │        中间 主聊天区            │  右侧栏       │
│ Agent    │                                │  任务看板      │
│ 状态卡片  │  🏗️ cici咪: 创建了 Issue      │              │
│          │  ⚡ coco咪: 领取了 Issue       │              │
│ 🏗️cici咪 │  🔍 soso咪: PR Review ✅       │              │
│ 🟢/🔴    │                                │              │
│ ⚡coco咪 │                                │              │
│ 🟢/🔴    │                                │              │
│ 🔍soso咪 │                                │              │
│ 🟢/🔴    ├────────────────────────────────┤              │
│          │  💬 消息输入框...      [发送]    │              │
└──────────┴────────────────────────────────┴──────────────┘
```

## 功能需求

### 1. 聊天消息流（核心）
- 所有 agent 活动以聊天消息形式呈现
- 每条消息：头像/emoji + 名字 + 时间 + 内容
- 消息类型样式：
  - 🏗️ cici咪 说了什么 → 蓝色左边框
  - ⚡ coco咪 说了什么 → 绿色左边框
  - 🔍 soso咪 说了什么 → 紫色左边框
  - 📝 系统消息 → 灰色居中（Issue 创建、PR 合并等）
  - 🧑‍💻 人类消息 → 右对齐，白色气泡
- 自动滚到最新消息，向上滚动时不自动滚
- WebSocket 接收新消息时实时追加

### 2. 人类输入框（关键！）
- 输入框在底部，像 Slack
- 支持 `@cici咪` `@coco咪` `@soso咪` 语法高亮
- 按 Enter 发送，Shift+Enter 换行
- 消息发送后：
  1. 前端 POST `/api/chat` → Engine 解析、路由、调用 agent
  2. Engine 推 WebSocket 消息 → 前端显示 agent 响应
- 发送中显示 loading 状态

### 3. 左侧 Agent 状态栏
- 保留现有 StatusBar 功能，但改为紧凑竖排
- 每个 agent：头像 + 名字 + 角色 + 状态灯
- 点击可展开该 agent 的统计

### 4. 右侧任务看板（折叠式）
- 保留 TaskBoard，但更紧凑
- 可折叠/展开
- 显示每个列的前 5 个任务
- 点击任务卡片 → 打开 GitHub Issue

### 5. 向后兼容
- 不删除现有 `dashboard/src/` 组件
- 新建组件用 `ChatRoom.jsx`、`ChatMessage.jsx`、`ChatInput.jsx`
- App.jsx 改为聊天室布局

## 技术注意
- 消息数据结构: `{type, agent, content, timestamp, kind: 'agent_message'|'system'|'human'}`
- WebSocket 通道不变，只是前端展示逻辑改变
- Vite proxy 已配置好 `/api` 和 `/ws`

## 工作流
```
1. git checkout -b feature/coco-5-chatroom  (从 main 最新)
2. git config user.name "coco咪 (Codex Developer)"
3. git config user.email "codex@teamchat.local"
4. 开发
5. git add -A && git commit -m "feat: chat-room Dashboard redesign (#5)"
6. git push origin feature/coco-5-chatroom
7. gh pr create ... (如未登录，告知摘要我来创建 PR)
```
""", labels=["phase-4", "frontend", "dashboard"], assignee="YancyLyx")
    print(f"✅ Issue #{i5.number}: {i5.title}\n   {i5.url}")

    # Issue #6: cici咪 — Message routing + API
    i6 = await cici.create_issue(
        title="[Phase 4] 消息路由引擎 + /api/chat 端点",
        body="""## 任务
实现聊天消息解析、路由和 agent 调用链条。

## 要做的事

### 1. `/api/chat` 端点 (api/routes/chat.py)
```python
POST /api/chat
Body: {"content": "@coco咪 修复 Dark Mode", "sender": "human"}

Response: {"status": "routed", "agent": "coco咪", "session_id": 42}
```

流程：
1. 接收消息 → 提取 `@mention`
2. 有 @mention → Router.dispatch(preferred_agent=mentioned_agent)
3. 无 @mention → 先让 cici咪 分析
4. cici咪 分析结果 → 如果是任务，Router 分配给对应 agent
5. 提交到 AgentRunner 执行
6. WebSocket 广播整个过程

### 2. Message Parser (engine/message_parser.py)
```python
def parse_mentions(content: str) -> list[AgentIdentity]:
    """Extract @cici咪 @coco咪 @soso咪 from message."""

def get_direct_target(content: str) -> AgentIdentity | None:
    """If exactly one agent is @mentioned, return it."""
```

### 3. cici咪 Bot 响应（简单问答）
当人类发没 @mention 的消息时，cici咪 用 `claude --print` 分析：
- prompt 模板: "你是 TeamChat 的架构师 cici咪。人类问你: {message}。如果是简单问答，直接回答。如果是开发任务，回复: TASK:frontend:任务描述 或 TASK:testing:任务描述 或 TASK:architecture:任务描述。如果是需要澄清的问题，回复: CLARIFY:你的问题"

### 4. WebSocket 消息扩展
新增消息类型:
- `chat_message` — agent 在聊天室说了什么
- `system_message` — 系统通知（Issue 创建、PR 等）

### 5. Engine → API 桥接
- AgentRunner.run() 完成后 → 通过 WebSocket 广播结果
- 区分"agent 内部日志"和"agent 公开回复"
- Agent 的输出如果是给人类看的 → 推送到聊天室
- Agent 的输出如果是内部操作 → 推送到系统通知

## 文件
```
engine/message_parser.py    ← 新建: @mention 解析
api/routes/chat.py          ← 新建: POST /api/chat
api/main.py                 ← 修改: 注册 chat router
```

## 实现者
cici咪 — 这是引擎层改动，架构师的主场。
""", labels=["phase-4", "engine", "api"], assignee="YancyLyx")
    print(f"✅ Issue #{i6.number}: {i6.title}\n   {i6.url}")

    # Issue #7: soso咪 — Chat E2E
    i7 = await cici.create_issue(
        title="[Phase 4] 聊天室 E2E 测试 + 集成验证",
        body="""## 任务
为聊天室 Dashboard 写 E2E 测试，验证端到端消息流。

## 测试场景
1. 发送消息 `@coco咪 say hello` → coco咪 回复出现在聊天区
2. 发送消息不加 @mention → cici咪 先分析再路由
3. 发送 `hello` → cici咪 回复团队状态
4. WebSocket 断开 → 输入框禁用 + 提示
5. WebSocket 重连 → 恢复输入
6. 三个 agent 连续对话 → 消息按时间排序
7. 人类消息右对齐，agent 消息左对齐

## 与现有 E2E 测试的关系
- 扩展 `tests/test_dashboard.py`
- 复用 `tests/e2e_support.py` 的 MockRunner
- 新增 `tests/test_chat.py`

## 实现者
soso咪 — QA 主场。但等 coco咪 (聊天UI) 和 cici咪 (/api/chat) 完成后开始。
""", labels=["phase-4", "testing"], assignee="YancyLyx")
    print(f"✅ Issue #{i7.number}: {i7.title}\n   {i7.url}")

    await cici.close()
    print("\n🎯 Phase 4 三个 Issue 创建完毕！")

if __name__ == "__main__":
    asyncio.run(main())

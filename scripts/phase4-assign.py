#!/usr/bin/env python3
"""cici咪 creates Phase 4 issues."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient

ISSUE5_BODY = """## 任务
将现有 Dashboard 重构为 Slack/Discord 风格的聊天室。

## 新布局
左侧栏: Agent 状态卡片 (紧凑竖排)
中间: 主聊天区 (消息流 + 底部输入框)
右侧栏: 任务看板 (折叠式, 每列前5个任务)

## 功能需求

### 1. 聊天消息流（核心）
- 所有 agent 活动以聊天消息形式呈现
- 每条消息: 头像/emoji + 名字 + 时间 + 内容
- 消息类型样式: cici咪=蓝色, coco咪=绿色, soso咪=紫色, 系统=灰色, 人类=白色右对齐
- 自动滚到最新消息
- WebSocket 实时追加新消息

### 2. 人类输入框（关键！）
- 输入框在底部，像 Slack
- 支持 @cici咪 @coco咪 @soso咪 语法高亮
- Enter 发送，Shift+Enter 换行
- 发送后: POST /api/chat -> Engine 解析路由 -> agent 执行 -> WebSocket 推送结果
- 发送中显示 loading

### 3. 左侧 Agent 状态栏
- 紧凑竖排: 头像 + 名字 + 角色 + 状态灯
- 点击展开统计详情

### 4. 右侧任务看板
- 紧凑三列: 待处理/进行中/已完成
- 可折叠，每列最多显示5个
- 点击任务卡片打开 GitHub Issue

### 5. 向后兼容
- 新建 ChatRoom.jsx, ChatMessage.jsx, ChatInput.jsx
- App.jsx 改为聊天室布局
- 不删除现有组件

## 技术注意
- 消息数据: {type, agent, content, timestamp, kind}
- Vite proxy 已配好 /api 和 /ws

## 工作流
1. git checkout -b feature/coco-5-chatroom (从 main 最新)
2. git config user.name "coco咪 (Codex Developer)" && git config user.email "codex@teamchat.local"
3. 开发
4. git add -A && git commit -m "feat: chat-room Dashboard redesign (#5)"
5. git push origin feature/coco-5-chatroom
6. gh pr create (如未登录，告知摘要我来创建)
"""

ISSUE6_BODY = """## 任务
实现聊天消息解析、路由和 agent 调用链条。

## 要做的事

### 1. POST /api/chat 端点 (api/routes/chat.py)
接收: {"content": "@coco咪 fix Dark Mode", "sender": "human"}
返回: {"status": "routed", "agent": "coco咪", "session_id": 42}

流程:
1. 接收消息 -> 提取 @mention
2. 有 @mention -> Router.dispatch(preferred_agent=mentioned_agent)
3. 无 @mention -> 先让 cici咪 分析
4. cici咪 分析结果 -> 如果是任务，Router 分配给对应 agent
5. AgentRunner 执行
6. WebSocket 广播整个过程

### 2. Message Parser (engine/message_parser.py)
- parse_mentions(content) -> list of AgentIdentity
- get_direct_target(content) -> AgentIdentity or None

### 3. cici咪 Bot 路由分析
当无 @mention 时，用 claude --print 分析:
prompt: "你是 TeamChat 架构师 cici咪。人类问: {msg}。如果是简单问答直接回答。如果是开发任务回复 TASK:frontend:描述 或 TASK:testing:描述 或 TASK:architecture:描述。如果需要澄清回复 CLARIFY:你的问题"

### 4. WebSocket 消息扩展
新增: chat_message, system_message 类型

### 5. Engine -> API 桥接
- AgentRunner.run() 完成后通过 WS 广播
- 区分 agent 公开回复 vs 内部操作

## 文件
- engine/message_parser.py (新建)
- api/routes/chat.py (新建)
- api/main.py (修改: 注册 chat router)

## 实现者
cici咪 — 引擎层改动
"""

ISSUE7_BODY = """## 任务
为聊天室 Dashboard 写 E2E 测试。

## 测试场景
1. 发送 @coco咪 say hello -> coco咪 回复出现在聊天区
2. 不加 @mention -> cici咪 先分析再路由
3. 发 hello -> cici咪 回复团队状态
4. WebSocket 断开 -> 输入框禁用 + 提示
5. WebSocket 重连 -> 恢复输入
6. 三个 agent 连续对话 -> 消息按时间排序
7. 人类消息右对齐，agent 消息左对齐

## 与现有测试关系
- 扩展 tests/test_dashboard.py
- 复用 tests/e2e_support.py MockRunner
- 新增 tests/test_chat.py

## 实现者
soso咪 — 等 coco咪(聊天UI) + cici咪(/api/chat) 完成后开始
"""

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    i5 = await cici.create_issue(
        title="[Phase 4] 聊天室风格 Dashboard 重构",
        body=ISSUE5_BODY,
        labels=["phase-4", "frontend", "dashboard"],
        assignee="YancyLyx",
    )
    print(f"Issue #{i5.number}: {i5.title}\n   {i5.url}")

    i6 = await cici.create_issue(
        title="[Phase 4] 消息路由引擎 + /api/chat 端点",
        body=ISSUE6_BODY,
        labels=["phase-4", "engine", "api"],
        assignee="YancyLyx",
    )
    print(f"Issue #{i6.number}: {i6.title}\n   {i6.url}")

    i7 = await cici.create_issue(
        title="[Phase 4] 聊天室 E2E 测试 + 集成验证",
        body=ISSUE7_BODY,
        labels=["phase-4", "testing"],
        assignee="YancyLyx",
    )
    print(f"Issue #{i7.number}: {i7.title}\n   {i7.url}")

    await cici.close()
    print("\nPhase 4 issues created!")

if __name__ == "__main__":
    asyncio.run(main())

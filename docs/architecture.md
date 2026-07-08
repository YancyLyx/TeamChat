# TeamChat 运行时架构

> 概述系统各组件如何协作。详细设计见 `docs/specs/` 和 `docs/decisions/`。

## 系统启动

```
uvicorn api.main:app
    │
    ├── load_config() → 读取环境变量（无 .env 文件）
    ├── SessionStore.init() → SQLite .teamchat/sessions.db
    ├── MessageBus.init() → .teamchat/messages/
    ├── WorkerPool.startup() → 启动三个 Persistent Worker
    │     ├── cici咪 Worker → claude --print --continue 进程
    │     ├── coco咪 Worker → codex exec 进程
    │     └── soso咪 Worker → cursor-agent 进程
    └── FastAPI 监听 :8000
```

## 消息流

```
人类发送 "大家好"
    ↓
POST /api/chat → parse_message()
    ↓
检测到打招呼 → 三只猫都回复:
    ├── WorkerPool.send(cici, "打招呼: 大家好")
    ├── WorkerPool.send(coco, "打招呼: 大家好")
    └── WorkerPool.send(soso, "打招呼: 大家好")
    ↓
WebSocket 推送三条 chat_message
    ↓
ChatRoom 显示三条回复
```

## 目录结构

```
TeamChat/
├── engine/           ← Python 核心引擎
│   ├── config.py     ← Agent 身份 + CLI 模板
│   ├── runner.py     ← AgentRunner → WorkerPool
│   ├── worker.py     ← PersistentAgentWorker
│   ├── router.py     ← 任务类型 → 最佳 agent
│   ├── bus.py        ← 文件系统消息总线
│   ├── github_client.py ← GitHub API
│   ├── store.py      ← SQLite 会话存储
│   └── message_parser.py ← @mention 解析
├── api/              ← FastAPI 后端
│   ├── main.py       ← 应用入口 + WebSocket + lifespan
│   └── routes/
│       ├── agents.py ← /api/agents
│       ├── sessions.py ← /api/sessions
│       ├── tasks.py  ← /api/tasks
│       └── chat.py   ← /api/chat
├── dashboard/        ← React + Vite + Tailwind
│   └── src/
│       ├── App.jsx
│       ├── hooks/useWebSocket.js
│       └── components/
│           ├── ChatRoom.jsx
│           ├── ChatMessage.jsx
│           ├── ChatInput.jsx
│           ├── AgentPanel.jsx
│           └── CompactTaskBoard.jsx
├── tests/            ← pytest
├── scripts/          ← 工具脚本
├── docs/             ← 文档
├── .teamchat/        ← 运行时数据（不手动编辑）
└── .gitignore
```

## 数据流

```
ChatRoom ←→ WebSocket ←→ FastAPI ←→ WorkerPool ←→ CLI 子进程
    │                          │
    │                          ├── SessionStore (SQLite)
    │                          ├── MessageBus (.teamchat/)
    │                          └── GitHubClient (REST API)
    │
    └── Vite proxy → /api → FastAPI
```

## Agent Worker 生命周期

```
WorkerPool.startup()
  └── 为每个 agent 创建 PersistentAgentWorker
        ├── 启动 CLI 子进程 (asyncio.subprocess)
        ├── 发送初始 prompt（设定角色）
        └── 等待消息

WorkerPool.send(agent, prompt)
  └── worker.send_message(prompt)
        ├── 构建完整 prompt（context + history + new message）
        ├── 写入子进程 stdin
        ├── 读取 stdout → 解析 THINKING/TOOL_CALLS/RESULT
        └── 返回 ParsedOutput

WorkerPool.shutdown()
  └── 每个 worker.send_exit()
        ├── 等进程优雅退出（5s 超时）
        └── 强杀
```

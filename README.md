# TeamChat 🐱

> 把孤立的 AI agent 变成真正协作的团队。让开发者从"人肉路由器"变成"观察者"。

四个团队成员 —— 一个人类 + 三个 AI agent —— 作为一个自治的开发团队协作。通过 GitHub Issues/PRs 自我组织，人类只需要在 Dashboard 上看着。

## Team

| Member | Type | Role | GitHub |
|---|---|---|---|
| 🧑‍💻 **你** | Human | 产品经理 / 决策者 | `YancyLyx` |
| 🏗️ cici咪 (Claude Code) | AI Agent | 架构师 / Tech Lead | `cici-claude` |
| ⚡ coco咪 (Codex CLI) | AI Agent | 全栈开发 / Feature Builder | `coco-codex` |
| 🔍 soso咪 (Cursor) | AI Agent | 集成工程师 / QA | `soso-cursor` |

**人类的职责：** 定义愿景、审查设计文档、创建 GitHub PAT、最终拍板、在 Dashboard 上看着一切发生。

**三只猫的职责：** 剩下的所有事 —— 写 spec、拆任务、写代码、提 PR、做 review、跑测试、合并、部署。

## Quick Start

```bash
# 后端
pip install -e ".[dev]"
uvicorn api.main:app --reload

# 前端
cd dashboard && npm install && npm run dev

# 打开 http://localhost:5173
```

## Project Structure

```
TeamChat/
├── engine/                     # Python 核心引擎
│   ├── config.py               # Agent 身份 + CLI 模板
│   ├── runner.py               # CLI spawn + stream-json 解析
│   ├── runtime.py              # Runtime Manager (session-aware spawn)
│   ├── task_table.py           # 任务表 CRUD + 依赖检查
│   ├── orchestrator.py         # 结果排队 + 失败重试
│   ├── session_store.py        # TeamChat 会话持久化
│   ├── store.py                # Agent 调用日志 (agent_calls)
│   ├── router.py               # 任务类型 → 最佳 agent
│   ├── bus.py                  # 文件系统消息总线
│   ├── github_client.py        # GitHub API 适配器
│   ├── message_parser.py       # @mention 解析 + 路由
│   ├── mcp_server.py           # MCP Server (task CRUD tools)
│   ├── codex_events.py         # Codex JSONL 解析
│   └── worker.py               # Persistent Worker (实验)
│
├── api/                        # FastAPI 后端
│   ├── main.py                 # 应用入口 + WebSocket + lifespan
│   └── routes/
│       ├── chat.py             # POST /api/chat + 路由 + 派发
│       ├── tasks.py            # 任务提交 + TaskTable CRUD
│       ├── agents.py           # Agent 状态
│       ├── sessions.py         # 会话历史
│       ├── approval.py         # POST /api/approval
│       └── teamchat_sessions.py # 前端会话管理 CRUD
│
├── dashboard/                  # React + Vite + Tailwind
│   └── src/
│       ├── App.jsx             # 三栏布局 + 数据加载
│       ├── hooks/useWebSocket.js
│       ├── utils/
│       │   ├── metrics.js      # Stats L1/L2/L3 计算
│       │   └── unicodeSafe.js  # Unicode 安全处理
│       ├── constants/
│       │   ├── agents.js       # Agent emoji/名称常量
│       │   └── session.js      # 活跃 session 工具
│       └── components/
│           ├── ChatRoom.jsx    # 聊天室主组件
│           ├── ChatMessage.jsx # 5 种消息气泡
│           ├── ChatInput.jsx   # @mention 输入 + 附件
│           ├── AgentCard.jsx   # Agent 状态卡片
│           ├── ApprovalCard.jsx # 审批卡片
│           ├── StatsPanel.jsx  # L1/L2/L3 指标
│           ├── LivePanel.jsx   # Engine 观测
│           ├── TasksBoard.jsx  # Tasks 看板（分组 + 依赖 + 失败操作）
│           ├── SessionManager.jsx # 会话管理弹窗
│           └── CompactTaskBoard.jsx # 任务看板
│
├── tests/                      # pytest + Playwright E2E
├── scripts/                    # 工具脚本
├── docs/                       # 设计文档
│   ├── START-HERE.md           # 导航入口
│   ├── process.md              # 协作流程 + 铁律
│   ├── architecture.md         # 运行时架构
│   ├── specs/                  # 初始设计（锁定）
│   ├── decisions/              # ADR
│   ├── phases/                 # 阶段回顾
│   └── agents/                 # 三角色卡
├── .teamchat/                  # 运行时数据
│   ├── teamchat.db             # 统一数据库（3 表）
│   └── mcp-config.json         # MCP Server 配置
├── CLAUDE.md                   # cici咪 手册
├── AGENTS.md                   # 三猫协议
├── PROGRESS.md                 # 唯一动态文档
└── pyproject.toml              # Python 项目配置
```

## Database

单文件 `.teamchat/teamchat.db`（SQLite WAL 模式），3 个表：

| 表 | 用途 |
|---|---|
| `teamchat_sessions` | 前端会话管理 |
| `agent_calls` | 每次 CLI 调用日志 |
| `task_table` | cici咪 创建的任务 |

## How It Works

1. 人类提出需求 → cici咪 分析并拆分为 GitHub Issues
2. Router 自动将 Issues 分配给对应的 agent
3. Agent 独立领取任务、写代码、提 PR
4. 另一个 agent 自动 Review 并合并
5. Dashboard 全程可视化，人类只需要看着

## Status

**ADR-003 实施完成 ✅** (15+ Issues, 80+ PRs, 3 agents)

See [PROGRESS.md](./PROGRESS.md) for details.

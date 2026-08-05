# TeamChat 🐱

> 把孤立的 AI agent 变成真正协作的团队。让开发者从"人肉路由器"变成"观察者"。

一个人类 + 三个 AI agent 作为一个自治的开发团队协作：人类在聊天室提需求、做审批，Agent 自动完成拆任务、派发、执行、审查、验收。**人类只保留两件事：提需求、做审批。**

## Team

| Member | Type | Role | GitHub |
|---|---|---|---|
| 🧑‍💻 **你** | Human | 产品经理 / 决策者 | `YancyLyx` |
| 🏗️ cici咪 (Claude Code) | AI Agent | 架构师 / Tech Lead / 编排者 | `cici-claude` |
| ⚡ coco咪 (Codex CLI) | AI Agent | 全栈开发 / Feature Builder | `coco-codex` |
| 🔍 soso咪 (Cursor) | AI Agent | 集成工程师 / QA / 独立审查 | `soso-cursor` |

**人类的职责：** 提需求、点审批、最终合并。**三只猫的职责：** 剩下的所有事——拆任务、写 prompt、写代码、做 review、跑测试、验收。

## Quick Start

```bash
# 后端
pip install -e ".[dev]"
uvicorn api.main:app          # ⚠️ 不要用 --reload（agent 改代码会触发重启，WS 全断）

# 前端
cd dashboard && npm install && npm run dev

# 打开 http://localhost:5173
```

> 约定：改引擎代码后**手动重启** uvicorn，不用 `--reload`（真实事故：热重载在任务执行中重启，WebSocket 断开、任务状态丢失）。

## Project Structure

```
TeamChat/
├── engine/                     # Python 核心引擎
│   ├── config.py               # Agent 身份 + CLI 模板
│   ├── runner.py               # CLI spawn + stream-json 逐行解析 + 流式回调
│   ├── task_table.py           # 任务表（依赖/feature_id/task_type）
│   ├── task_scheduler.py       # 调度器（轮询派发、并行、重试、watchdog 广播）
│   ├── result_relay.py         # 结果回流 + 排队审核（双模式 prompt）
│   ├── task_planner.py         # DAG 校验（环/孤儿）+ session/树修复
│   ├── dispatch.py             # spawn_with_session（会话续接 + codex 轮换）
│   ├── session_store.py        # CLI session ID 持久化
│   ├── store.py                # Agent 调用日志 (agent_calls)
│   ├── router.py               # 忙闲管理（is_busy/mark_busy）
│   ├── message_parser.py       # @mention 解析 + 路由
│   ├── mcp_server.py           # MCP Server（create_task/update_task/...）
│   ├── codex_events.py         # Codex JSONL 解析
│   └── ...
│
├── api/                        # FastAPI 后端
│   ├── main.py                 # 应用入口 + WebSocket + lifespan
│   └── routes/
│       ├── chat.py             # POST /api/chat + 流式广播
│       ├── tasks.py            # 任务 CRUD + features 聚合
│       ├── stats.py            # Stats L1/L2/L3
│       ├── approval.py         # 审批端点（control_request 写回）
│       └── ...
│
├── dashboard/                  # React + Vite + Tailwind
│   └── src/
│       ├── App.jsx             # 三栏布局 + 1s 数据同步
│       ├── hooks/useWebSocket.js
│       ├── utils/metrics.js    # Stats L1/L2/L3 计算
│       └── components/
│           ├── ChatRoom.jsx    # 聊天室（段落级流式气泡）
│           ├── ChatMessage.jsx # 气泡渲染（Markdown + XSS 加固）
│           ├── ChatInput.jsx   # @mention 输入
│           ├── AgentCard.jsx   # Agent 状态卡片
│           ├── ApprovalCard.jsx # 审批卡片
│           ├── StatsPanel.jsx  # L1/L2/L3（需求树：agent 着色 + 平铺）
│           ├── DagGraph.jsx    # 需求树 DAG 图（并行分支/审查虚线框）
│           ├── LivePanel.jsx   # Engine 观测
│           ├── TasksBoard.jsx  # Tasks 看板（分组/依赖/失败操作）
│           └── SessionManager.jsx
│
├── tests/                      # pytest（单测 + 集成 + E2E 隔离）
├── scripts/                    # 验收脚本（真实引擎 e2e）
├── docs/                       # 设计文档
│   ├── START-HERE.md           # 导航入口
│   ├── decisions/              # ADR（001 技术栈 / 002 常驻[已 revert] / 003 真实 CLI / 004 Phase 4）
│   ├── phases/                 # 阶段状态跟踪（对照 decisions）
│   ├── interview/              # 面试准备（local-only，不进 git）
│   └── agents/                 # 三角色卡
├── .teamchat/                  # 运行时数据（不进 git）
│   └── teamchat.db             # 统一数据库（3 表）
├── CLAUDE.md                   # cici咪 手册
├── AGENTS.md                   # 三猫协议
├── PROGRESS.md                 # 唯一动态文档
└── pyproject.toml
```

## Database

单文件 `.teamchat/teamchat.db`（SQLite WAL 模式），3 个表：

| 表 | 用途 |
|---|---|
| `teamchat_sessions` | 前端会话（绑定各 agent 的 CLI session ID） |
| `agent_calls` | 每次 CLI 调用日志（token/耗时/输出） |
| `task_table` | 任务编排（depends_on / feature_id 需求树 / task_type 节点类型） |

## How It Works（当前工作流）

```
人类在聊天室提需求
→ cici咪 分析 → MCP create_task 拆 DAG（依赖 + 需求树）
→ TaskScheduler 自动派发（不同 agent 并行，#96）
→ agent 执行（--resume 延续上下文，段落级流式输出）
→ ResultRelay 结果回流 → cici咪 审核
→ 开发节点 done → cici咪 基于真实产出创建 soso咪 审查节点（#97）
→ soso咪 审查/测试 → 回流 → 通过 done / 发现问题 → 修复 → 复审循环
→ 需求树全部 done → 完成（L2 可观测全流程）
```

**关键机制**：
- **DAG 任务树**：cici咪 拆任务（feature_id 需求树 + depends_on 依赖），调度器按依赖自动派发
- **并行派发**（#96）：不同 agent 的独立任务同时执行；同 agent 串行（CLI session 保护）
- **审查闭环**（#97）：任何开发节点 done 后必须经 soso咪 独立审查（审查节点是正式 DAG 节点）；修复 → 复审循环直到通过
- **段落级流式**：agent 输出边写边长，气泡不干等
- **审批卡**：Claude 危险工具操作弹卡片，人类点允许/拒绝
- **Stats L1/L2/L3**：效能 / 流程（需求树拓扑图）/ 解放度（自动化率、人工介入）

## Status

**ADR-004（Phase 4）实施中** —— 核心闭环、DAG 编排、并行派发（#96）、审查闭环（#97）、流式输出、Stats 观测均已落地（见 [PROGRESS.md](./PROGRESS.md)）。

- 待办：终止正在执行的 agent、GitHub Adapter（阻塞于 GitHub 账号恢复）、数据库归档
- 测试：195+ passed（单测 + 集成，E2E 隔离不污染真实库）
- GitHub 暂停期间：本地开发正常，gitee 备份

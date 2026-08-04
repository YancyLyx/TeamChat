# 02. 架构与技术栈

## 架构全景

```
┌─────────────────────────────────────────────────────┐
│               Dashboard (React + Vite)               │
│  聊天室 · Agent状态 · Stats L1/L2/L3 · Live · 任务   │
└───────────────┬─────────────────────────────────────┘
                │ REST + WebSocket
┌───────────────┴─────────────────────────────────────┐
│                FastAPI 后端                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │ /api/chat │ │ /api/stats│ │ /api/approval     │  │
│  │ 路由+派发  │ │ L1/L2/L3  │ │ 审批卡片          │  │
│  └───────────┘ └───────────┘ └───────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │            Engine (Python)                     │  │
│  │  Runner(CLI驱动) · MCP Server · TaskTable      │  │
│  │  SessionStore · Router · Orchestrator          │  │
│  └───────────────────────────────────────────────┘  │
└───────────────┬─────────────────────────────────────┘
                │ spawn + stream-json
   ┌────────────┼────────────┐
   ▼            ▼            ▼
 claude      codex       agent(Cursor)
 (cici咪)    (coco咪)     (soso咪)
```

## 技术栈选型（每个都有为什么）

### Python + FastAPI（后端）

| 为什么选 | 为什么不选 |
|---|---|
| `asyncio.subprocess` 管理 CLI 进程最顺手（本项目的核心）| TypeScript：`child_process` 对长交互进程控制弱 |
| WebSocket 原生支持（Dashboard 实时推送）| Django：太重，不需要 ORM/admin |
| SQLite 原生、零依赖部署 | Go：三个 agent 中没人擅长，协作成本高 |

### React + Vite + Tailwind（前端）

| 为什么选 | 为什么不选 |
|---|---|
| 开发 agent（coco咪）最擅长 | Vue/Svelte：开发 agent 不熟练，拖慢迭代 |
| 生态最全（WebSocket、Markdown、动画库）| — |
| Tailwind 让 agent 不用切 CSS 文件 | — |

### SQLite 单文件

| 为什么选 | 为什么不选 |
|---|---|
| 零配置、单文件可迁移 | Postgres/MySQL：本地开发阶段没必要 |
| 一个 `teamchat.db` 三个表可 JOIN | 早期三库三连接，无法 JOIN，已合并 |

### 三个 CLI 的接入方式（核心决策）

**选 stream-json，不选 PTY：**

```
PTY 方式（放弃）:
  伪终端模拟交互式对话
  ❌ 输出是混杂文本，无法结构化
  ❌ 审批只能模拟按键

Stream-json 方式（采用）:
  claude --print --output-format stream-json
  codex exec --json
  agent --print --output-format stream-json
  ✅ 每行一个 JSON 事件: text/thinking/tool_use 天然分离
  ✅ 审批是 control_request 结构化事件
  ✅ 会话用 --resume <id> 延续
```

**为什么用 CLI 而不是官方 API：**

| CLI | API |
|---|---|
| 复用用户已有的订阅（Claude Max/ChatGPT Plus）| 需要额外计费 |
| 自带 MCP、工具调用、文件操作 | 要自己实现 agent 循环 |
| 三个 agent 统一的接入范式 | 三个 SDK 各自为政 |

## 数据层设计

```
.teamchat/teamchat.db (单文件 SQLite)
├── teamchat_sessions   ← 前端会话（多目录多会话）
├── agent_calls         ← 每次 CLI 调用日志（含 token、tool_calls）
└── task_table          ← 任务编排（依赖、状态、prompt）

关键设计:
- 所有表带 teamchat_session_id FK → 会话数据隔离
- tool_calls 存 JSON → 可统计每只咪的工具使用
- token_usage 存 JSON → Stats L1 token 指标
```

## 面试高频问题速答

**Q: 为什么不用现成的 Agent 框架（LangChain 等）？**
A: 我们要驱动的是三个**本地 CLI**（复用订阅、带 MCP），不是纯 API。LangChain 对 CLI 进程管理没有帮助，反而引入抽象层。核心价值在进程管理 + 任务编排，自己写更可控。

**Q: 三个 CLI 的接入有什么坑？**
A: 三个格式完全不同。Claude 用 `stream-json`（`--verbose` 才能用），Codex 用 `--json` JSONL，Cursor 也是 `stream-json` 但命令名是 `agent` 不是 `cursor-agent`。全部实测验证过才能写进代码。

**Q: 为什么需要统一事件模型？**
A: 三个 CLI 输出格式不同，但业务只需要关心 text/thinking/tool_use/result 四类事件。统一为 `AgentEvent` 后，上层（聊天室、审批、统计）完全不感知底层是哪个 CLI。

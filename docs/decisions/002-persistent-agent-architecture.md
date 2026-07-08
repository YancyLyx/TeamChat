# ADR-002: Persistent Agent Architecture

**Date:** 2026-07-08
**Status:** Proposed
**Decider:** cici咪 (Claude Architect)

---

## Context

当前 AgentRunner 是 one-shot 模式：每次消息都创建新子进程 → 调用 CLI → 等结果 → 杀进程。这导致：

1. **延迟高** — 每次冷启动 CLI + 建立 API 连接（3-7 秒）
2. **无上下文** — 每条消息之间没有记忆，agent 不记得上一句说了什么
3. **不像"团队"** — 更像每次打电话叫醒 agent，说完再挂断

## Decision

### 1. Persistent Agent Workers

每个 agent 在系统启动时创建一个 **PersistentAgentWorker**，长期运行：

```
api lifespan startup
  ├── WorkerPool.startup()
  │     ├── cici咪 Worker: 维持 claude --print --continue 会话
  │     ├── coco咪 Worker: 维持 codex exec 会话
  │     └── soso咪 Worker: 维持 cursor-agent 会话
  │
  ... 系统运行中 ...
  │
  api lifespan shutdown
  └── WorkerPool.shutdown()
        ├── 发 "exit" 信号
        ├── 等进程优雅退出
        └── 超时强杀
```

### 2. Worker 通信协议

每个 Worker 维护自己的 conversation history，通过 CLI 原生会话机制保持上下文：

```
人类: @coco咪 写一个 API
Worker: 构建 prompt = history + 新消息 → CLI call → 解析输出 → 返回
        ↓
人类: 再加个参数校验
Worker: history 已有上一条 → context 完整 → CLI call → 快速响应
```

| Agent | 上下文保持方式 |
|---|---|
| Claude | `claude --print --continue <session-id>` 复用会话 |
| Codex | `codex exec resume --last` 继续上一条 |
| Cursor | `cursor-agent --continue` |

### 3. 消息路由规则

```
parse_message(content)
    │
    ├── 是打招呼? (大家好/hi/hello/在吗/有人在吗)
    │   └── BROADCAST → 三只猫都回复
    │
    ├── 有 @mention (单个)
    │   └── DIRECT → 发给指定 agent
    │
    ├── 有 @mention (多个)
    │   └── BROADCAST → 发给所有被 @ 的 agent
    │
    └── 没有 @mention
        └── CICI_ANALYZE → cici咪 分析 → 按类型路由
```

| 人类输入 | 发生什么 |
|---|---|
| `大家好` | 三条猫各回复一句自我介绍 |
| `hello` | 同上 |
| `@coco咪 写一个 API` | 只有 coco咪 回复 |
| `@cici咪 @soso咪 review PR` | cici咪 + soso咪 回复 |
| `加个刷新按钮` | cici咪 分析 → 是前端任务 → 派给 coco咪 |

### 4. CLI 输出处理

Agent CLI 的输出包含折叠的部分（思考、工具调用、最终文本）。Worker 需要：

- **折叠的思考/工具调用** → 聊天室显示为可展开区域（类似 CLI 的折叠效果）
- **最终文本** → 直接显示
- **JSON 响应** → 解析提取 `result` 字段（已修）

输出格式约定：
```
<THINKING>
思考内容...
</THINKING>
<TOOL_CALLS>
工具调用...
</TOOL_CALLS>
<RESULT>
最终回复文本（显示在聊天室）
</RESULT>
```

Worker 解析这些标签，前端 ChatMessage 组件渲染：
- THINKING → 灰色小字，默认折叠，点击展开
- TOOL_CALLS → 灰色小字，显示用了什么工具
- RESULT → 正常聊天气泡

### 5. 会话数据隔离

| 类型 | 标签 | 用途 |
|---|---|---|
| `test` | `tag=test` | E2E 测试、调试 |
| `production` | `tag=prod` | 真实人类使用 |

- 聊天室只加载 `tag=prod` 的历史消息
- 测试脚本使用 `tag=test`
- Dashboard 的 `/api/sessions?tag=prod` 过滤

### 6. 完整架构图

```
┌─────────────────────────────────────────────────────────┐
│                    ChatRoom (聊天室)                      │
│  人类 ←→ 输入框 @mention → POST /api/chat               │
│  显示 ← WebSocket ← 三只猫的回复                          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                   api/routes/chat.py                     │
│  解析 → 打招呼? → broadcast                              │
│  解析 → @mention → direct                                │
│  解析 → 无@ → cici咪 分析 → route                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                   engine/worker_pool.py                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ cici咪 Worker│  │ coco咪 Worker│  │ soso咪 Worker│     │
│  │ (长期运行)   │  │ (长期运行)   │  │ (长期运行)   │     │
│  │ history: [] │  │ history: [] │  │ history: [] │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                   engine/runner.py                       │
│  AgentRunner.send(agent, prompt) → result               │
│  - 复用 worker 进程                                      │
│  - 维持 conversation history                            │
│  - 解析 THINKING/TOOL_CALLS/RESULT 标签                  │
└─────────────────────────────────────────────────────────┘
```

## Consequences

### Positive
- 延迟降低：首次调用后进程在内存中，后续调用秒级响应
- 上下文保持：agent 记得之前说了什么
- 真正的"团队聊天"：三只猫像三个终端一样一直在后台等
- 人类只需一个浏览器标签

### Negative
- 三个后台进程占用内存（每个 ~200MB）
- 长连接管理复杂（心跳、重连、超时重启）
- CLI 会话有时间限制，需要自动续期

### Risks
- CLI 更新后 API 格式可能变 → 用户锁定 CLI 版本
- 进程可能僵死 → 加心跳检测 + 自动重启

## Implementation Order

1. `engine/worker.py` — PersistentAgentWorker 类
2. `engine/runner.py` — AgentRunner 改造为 WorkerPool
3. `api/main.py` — lifespan 管理 WorkerPool
4. `api/routes/chat.py` — 打招呼路由 + 输出解析
5. `engine/store.py` — 会话 tagging
6. ChatRoom 前端 — 折叠区展开、历史过滤

---

**签字:** cici咪 (待确认)

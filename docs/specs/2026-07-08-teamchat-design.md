# TeamChat Design Document

**Date:** 2026-07-08
**Status:** Locked (Phase 1 design baseline)
**Author:** Human + cici咪 (Claude Code)

---

## 1. Vision

**问题：** 使用多个 AI coding agent（Claude Code、Codex CLI、Cursor）时，开发者变成了"人肉路由器"——在聊天窗口之间复制粘贴上下文，手动追踪谁说了什么，大量时间花在"帮 AI 传话"上。

**目标：** 把孤立的 AI agent 变成真正协作的团队，让开发者从"路由器"变成"观察者"。

## 2. Why TeamChat — 与现有方案的关键差异

2025–2026 年，多 AI agent 协作生态正在爆发。以下是与 TeamChat 愿景最相关的先行项目：

| 项目 | 核心思路 | 仍存在的局限 |
|---|---|---|
| gojaja (过家家) | 文件系统协调层，角色分配 | 人类仍是仲裁者 |
| Murmur | 通信总线，agent @mention | 停留在消息层，不管理完整工作流 |
| Polynoia | IM 风格界面 + 角色库 | 人类驱动对话，agent 不会自主行动 |
| Crewly | Web Dashboard + 技能系统 | 人类分配任务，没有自治争议解决 |
| Agor | Canvas 式多 agent 画布 | 可视化为主，缺少自主协作逻辑 |
| Agent Kanban | Agent-first 任务板 | 人类创建和分配任务 |

### 现有方案的三个共同局限

**1. 人类仍然是路由器**

几乎所有项目都是"给你一个协调框架 + 你自己手动管理 agent"。人类负责分配任务、仲裁冲突、决定谁做什么。工具让沟通更方便了，但没有真正把人从"传话"中解放出来。

**2. 没有自治的争议解决**

Agent A 和 Agent B 意见不合时，现有方案无一提供自动化的辩论→投票→裁决机制。冲突最终还是要人类介入。

**3. 没有真 GitHub 原生**

Agent 不会自己开 Issue、自己 @ 队友、自己 assign、自己 Review PR、自己 close。GitHub 只是存储代码的地方，不是 agent 协作的战场。

### TeamChat 的不同

> **三个 agent 作为平等的团队成员自治协作 — 各自拥有 GitHub 身份，能自发开 Issue 讨论分歧、提 PR 竞争实现、通过 PR Review 投票裁决，像一个真正的开源团队一样工作。人类只需要在 Dashboard 上看着。**

| | 现有方案 | TeamChat |
|---|---|---|
| 任务分配 | 人类分配 | **Agent 自己认领 + Router 自动分配** |
| 冲突解决 | 人类仲裁 | **辩论 → 投票 → 自动裁决** |
| GitHub 行为 | 人类操作 | **Agent 自主开 Issue/PR/Review/Merge** |
| 人类角色 | 路由器 | **观察者** |

## 3. Team Members

| Agent | Name | CLI | Role | GitHub Identity |
|---|---|---|---|---|
| Claude Code | **cici咪** | `claude --print` | 架构师 / Tech Lead | `cici-claude <claude@teamchat.local>` |
| Codex CLI | **coco咪** | `codex exec` | 全栈开发 / Feature Builder | `coco-codex <codex@teamchat.local>` |
| Cursor | **soso咪** | `cursor-agent` | 集成工程师 / QA | `soso-cursor <cursor@teamchat.local>` |

### 角色职责

**cici咪 (Claude) — 架构师：**
- 系统设计文档与技术决策
- 核心引擎实现（Router、Message Bus）
- 任务拆分与 GitHub Issue 管理
- PR 审查与合并把关
- Cursor 的 CLI 驱动层

**coco咪 (Codex) — 开发：**
- 前端 Dashboard UI
- REST/WebSocket API 层
- 各 agent CLI 的命令封装层
- 快速功能迭代

**soso咪 (Cursor) — 集成/QA：**
- GitHub App/Webhook 集成
- E2E 测试套件
- CI/CD pipeline
- 项目文档一致性
- Bug 修复

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Dashboard (Web UI)                  │
│         实时任务板 · Agent 状态 · 对话日志 · 活动时间线  │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket / REST API
┌──────────────────────┴──────────────────────────────┐
│               TeamChat Engine (核心引擎)              │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Router  │  │  Message │  │  GitHub Adapter   │  │
│  │ 任务路由器 │  │ 消息总线  │  │ Issue/PR/Webhook  │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Agent    │  │  Session │  │  Conflict         │  │
│  │  Runner   │  │  Store   │  │  Resolver         │  │
│  │ CLI 驱动层 │  │ 会话存储  │  │ 辩论→投票→裁决    │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ CLI 调用 (subprocess)
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                  ▼
┌─────────┐     ┌─────────┐      ┌─────────┐
│ cici咪  │     │ coco咪  │      │ soso咪  │
│ Claude  │     │ Codex   │      │ Cursor  │
│ 架构师   │     │ 开发    │      │ 集成/QA │
└─────────┘     └─────────┘      └─────────┘
```

### 核心模块

**Agent Runner — CLI 驱动层**
- 封装 `claude --print`、`codex exec`、`cursor-agent` 的调用
- 统一输入：task (prompt + context) → 统一输出：result (text + artifacts)
- 处理超时、重试、session 恢复
- 每个 agent 运行在隔离的 git worktree 中（Phase 3+）

**Router — 任务路由器**
- 声明式路由规则：任务类型 → 目标 agent
- 支持直接指派（人类指定）和自动路由（基于规则）
- 负载感知：agent 忙时不分配新任务

**Message Bus — 消息总线**
- Agent 间消息传递：请求、响应、广播
- 消息持久化到 `.teamchat/` 目录
- 支持 `@mention` 风格的定向消息

**GitHub Adapter — GitHub 适配器**
- 以不同 agent 身份创建/管理 Issue、PR
- 处理 Webhook 事件（新 Issue → 自动分配、新 PR → 通知 reviewer）
- 身份映射：agent name → GitHub commit author

**Session Store — 会话存储**
- 每次 agent 调用的完整日志（prompt、output、耗时、token 用量）
- SQLite 存储，提供查询接口给 Dashboard

**Conflict Resolver — 争议解决（Phase 4）**
- Agent A 和 B 意见不合时：辩论 → 投票 → 裁决
- 裁决结果自动转换为 Issue 或 PR comment

### 设计原则

1. **引擎层不做 AI 推理** — 只做路由、消息、调度、GitHub 操作
2. **Agent 平等** — 没有主 agent，路由规则声明式配置
3. **文件系统是共享内存** — Agent 通过 git repo 文件 + `.teamchat/` 通信
4. **GitHub 是真相来源** — 任务=Issue, 实现=PR, 审查=Review, 合并=完成

## 5. GitHub Identity Model

技术方案：Fine-grained PAT × 3（token 名称区分身份）

```
Token: teamchat-cici    → git config user.name "cici咪 (Claude Architect)"
Token: teamchat-coco    → git config user.name "coco咪 (Codex Developer)"
Token: teamchat-soso    → git config user.name "soso咪 (Cursor QA)"
```

GitHub 上所有操作（Issue、PR、Review、Comment）都能看到哪个 agent 在执行。

## 6. Communication Protocol

### Agent-to-Agent 通信

所有通信通过 GitHub Issues/PRs + `.teamchat/` 目录：

```
.teamchat/
├── messages/          ← 消息文件（JSON）
│   ├── msg-001.json
│   └── msg-002.json
├── sessions/          ← 会话日志
│   ├── cici-2026-07-08-001.json
│   └── coco-2026-07-08-001.json
└── state.json         ← 全局状态（当前任务、agent 状态）
```

### 消息格式

```json
{
  "id": "msg-001",
  "from": "cici咪",
  "to": "coco咪",
  "type": "task_assignment",
  "github_issue": "#42",
  "content": "请实现 WebSocket 断连重连机制",
  "timestamp": "2026-07-08T10:00:00Z"
}
```

### 工作流

```
人类/系统提需求
    ↓
cici咪 分析 → 写 spec → 创建 GitHub Issues
    ↓
Router 根据 Issue 标签 → 分配 Issue 给对应 agent
    ↓
Agent 领取 Issue → 创建分支 → 写代码 → 提 PR
    ↓
Reviewer agent 被自动 assign → Review PR
    ↓
cici咪 最终审查 → 合并 → 关闭 Issue
    ↓
Dashboard 全程可视化
```

## 7. Four-Phase Roadmap

### Phase 1: Handshake (握手)
**目标：** 三只猫能在 GitHub 上以独立身份行动

| 任务 | 负责人 |
|---|---|
| 初始化 Git repo，关联 GitHub remote | Human |
| 创建三个 Fine-grained PAT | Human |
| 写 CLAUDE.md + AGENTS.md，定义三角色 | cici咪 |
| 写 agent 角色卡文档 (`docs/agents/`) | cici咪 |
| 验证每个 agent 能独立 git commit & push | soso咪 |
| 创建 `PROGRESS.md` 进度追踪 | cici咪 |

**完成标志：** 三个 agent 都能以各自身份在 GitHub 上 commit

### Phase 2: Collaborate (协作)
**目标：** Agent 通过 GitHub Issues/PRs 协作开发核心引擎

| 模块 | 负责人 |
|---|---|
| Agent Runner (CLI 驱动层) | cici咪 |
| GitHub Adapter | soso咪 |
| Router (任务路由器) | cici咪 |
| Message Bus (消息总线) | coco咪 |
| Session Store (会话存储) | coco咪 |

**完成标志：** 命令行能跑通 agent 间任务分发（cici咪发 Issue → coco咪领任务 → soso咪 review）

### Phase 3: Visualize (可视化)
**目标：** 建 Dashboard，实时展示 agent 工作状态

| 任务 | 负责人 |
|---|---|
| Dashboard UI 设计 | coco咪 |
| WebSocket API 层 | coco咪 |
| 实时任务板组件 | coco咪 |
| Agent 状态面板 | coco咪 |
| 对话日志时间线 | coco咪 |
| E2E 测试 | soso咪 |

**完成标志：** 在浏览器中能实时看到三只猫的协作活动

### Phase 4: Autonomy (自治)
**目标：** 实现完整的自治协作闭环

| 任务 | 负责人 |
|---|---|
| Conflict Resolver (辩论→投票→裁决) | cici咪 |
| 自动任务分配 (基于 agent 负载和能力) | cici咪 |
| 自愈机制 (agent 失败自动重试/转派) | soso咪 |
| 完整的 Git Worktree 隔离 | soso咪 |
| 对外的 MCP 接口（让其他项目也能接入） | coco咪 |

**完成标志：** 你可以完全作为观察者，agent 自主完成开发循环

## 8. Documentation System

```
TeamChat/
├── README.md               ← 项目门面（是什么 + 怎么跑）
├── PROGRESS.md              ← 唯一动态文档（当前进度 + 下一步）
├── docs/
│   ├── specs/               ← 设计文档（写后锁定，只读）
│   │   └── 2026-07-08-teamchat-design.md
│   ├── phases/              ← 各 phase 独立计划
│   │   ├── phase-1-handshake.md
│   │   ├── phase-2-collaborate.md
│   │   ├── phase-3-visualize.md
│   │   └── phase-4-autonomy.md
│   ├── decisions/           ← 架构决策记录 (ADR)
│   └── agents/              ← agent 角色卡
│       ├── cici-claude.md
│       ├── coco-codex.md
│       └── soso-cursor.md
└── .teamchat/               ← 运行时目录（不手动编辑）
```

### 三条铁律

1. **写后锁定** — `specs/` 下文档写完只读。新想法 → 写新 ADR 到 `decisions/`
2. **单页进度** — `PROGRESS.md` 是唯一频繁修改的文档
3. **新想法 = 新文件** — 不在旧文档追加，而是创建新的 ADR 记录

## 9. Tech Stack (Phase 2-3 decisions)

| 层面 | 候选技术 | 决策者 |
|---|---|---|
| 核心引擎语言 | Python / TypeScript / Go | cici咪 |
| Dashboard 前端 | React + Tailwind / Vue / Svelte | coco咪 |
| 实时通信 | WebSocket (FastAPI / Express / Go) | coco咪 |
| 数据存储 | SQLite | cici咪 |
| 进程隔离 | Git worktree | soso咪 |

技术栈具体选型在 Phase 2 开始时由 cici咪 写 ADR 决定。

## 10. Success Metrics

- **Phase 1:** 三个 agent 各自的 commit 出现在 GitHub 贡献图上
- **Phase 2:** 一个完整的 Issue→PR→Review→Merge 循环，无需人类介入中间步骤
- **Phase 3:** Dashboard 上能实时看到 agent 在做什么
- **Phase 4:** 你提一个 feature request，agent 自己讨论、实现、测试、部署

---

**签字确认：** Human ✅ | cici咪 (待) | coco咪 (待) | soso咪 (待)

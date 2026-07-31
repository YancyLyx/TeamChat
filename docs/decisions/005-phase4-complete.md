# ADR-005: Phase 4 完整规划 — 从"推模式"到"拉模式"

**状态**: Draft
**日期**: 2026-07-31
**作者**: cici咪
**参与者**: coco咪（前端），soso咪（集成/QA）

---

## 背景

### 当前状态（Phase 1-3）

| 模块 | 实现状态 | 说明 |
|---|---|---|
| GitHub 身份 | ✅ 完成 | 三个 PAT，能以不同身份 commit |
| Agent Runner | ✅ 完成 | Claude/Codex/Cursor CLI 封装 |
| Router | ⚠️ 基础版 | 支持直接指派，无智能路由 |
| Message Bus | ⚠️ 半完成 | 文件系统，但没人读 |
| Session Store | ✅ 完成 | SQLite 存储 |
| Dashboard | ✅ 完成 | WebSocket + 聊天室 |
| /api/chat | ✅ 完成 | @mention 路由 |
| 审批系统 | ✅ 完成 | permission-prompt-tool stdio |

### 愿景差距（spec 2026-07-08）

| spec 愿景 | 当前实现 | 差距 |
|---|---|---|
| Agent 自己认领 | ❌ 无 | 人类必须指定 agent |
| Router 自动分配 | ⚠️ 部分支持 | 只有 @mention 路由，无任务类型路由 |
| 辩论 → 投票 → 自动裁决 | ❌ 无 | 没有 Conflict Resolver |
| Agent 自主开 Issue/PR/Review/Merge | ❌ 无 | 没有 GitHub Adapter |
| 任务拆分（大需求 → Issues） | ❌ 无 | 只能创建单任务 |
| 人类变成观察者 | ❌ 无 | 人类仍需主导流程 |
| Git Worktree 隔离 | ❌ 无 | 所有 agent 在同一 cwd |

---

## 核心问题：当前是"推模式"，愿景是"拉模式"

### 推模式（当前）

```
人类发消息
  ↓
/api/chat (cici咪 分析)
  ↓
create_task(指定 agent)
  ↓
Task Scheduler 跑任务
  ↓
agent 执行
```

**问题**：
- 任务来源单一（人类发消息）
- agent 无法自主产生新任务
- 没有协作机制（agent 不会互相 @）

### 拉模式（愿景）

```
GitHub 新 Issue (人类/cici咪)
  ↓
Issue Parser 解析
  ↓
Task Planner 拆分任务
  ↓
Agent Bids（竞拍/认领）
  ↓
Task 分配
  ↓
执行
  ↓
Result + 新 Issue（迭代）
```

**核心差异**：
| 推模式 | 拉模式 |
|---|---|
| 任务是"推给" agent | 任务是"被认领"的 |
| 来源单一 | 多来源（GitHub / chat / 其他 agent） |
| 无协作 | 有协作（辩论→投票） |
| 无迭代 | 有迭代（产生新 Issue） |

---

## 完整架构（Phase 4）

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Layer                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ GitHub Adapter (engine/github_adapter.py)                    │  │
│  │ - 监听 Webhook (新 Issue, 新 PR, Review, Comment)          │  │
│  │ - 以 agent 身份开 Issue/PR/Review/Merge                      │  │
│  │ - 同步 GitHub 状态到内部 task_table                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ webhook / read
┌─────────────────────┴───────────────────────────────────────────────┐
│                      Coordination Layer                            │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐│
│  │  Issue Parser    │  │  Task Planner    │  │  Agent Bids        ││
│  │  解析 GitHub     │  │  拆分任务        │  │  竞拍/认领         ││
│  │  Issue → Task    │  │  需求 → DAG      │  │  任务分配          ││
│  └──────────────────┘  └──────────────────┘  └────────────────────┘│
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Conflict Resolver (engine/conflict_resolver.py)            │  │
│  │  辩论 → 投票 → 裁决 → 转为 Issue/PR comment                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ task_table / bus
┌─────────────────────┴───────────────────────────────────────────────┐
│                      Execution Layer                               │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐│
│  │  Task Scheduler  │  │  Agent Runner    │  │  Git Worktree     ││
│  │  轮询 + 执行     │  │  CLI 驱动        │  │  隔离环境         ││
│  │  任务回写        │  │  Session 恢复    │  │  并发安全         ││
│  └──────────────────┘  └──────────────────┘  └────────────────────┘│
└─────────────────────┬───────────────────────────────────────────────┘
                      │ stdout / events
┌─────────────────────┴───────────────────────────────────────────────┐
│                      Presentation Layer                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Dashboard (React) + WebSocket                               │  │
│  │  聊天室 / 任务板 / 状态面板 / Live Timeline                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 分段实施计划

### Phase 4.1: GitHub Adapter（外部接入）

**目标**：GitHub 和内部系统打通，task_table 能反映 GitHub 状态。

**交付物**：
- `engine/github_adapter.py`
- GitHub Webhook 端点（`/api/github/webhook`）
- Issue ↔ Task 双向同步

**场景**：
```
人类在 GitHub 开 Issue #1: "实现黑暗模式"
  ↓
Webhook → GitHub Adapter
  ↓
在 task_table 创建任务: {id=1, title="实现黑暗模式", source="github_issue", github_ref="#1", status="pending"}
  ↓
Task Scheduler 执行（沿用 ADR-004）
  ↓
执行完成 → GitHub Adapter 回复 Issue #1: "✅ 已完成 PR #42"
```

**优先级**：最高（这是拉模式的基础）

**预估工作量**：3-4 天

---

### Phase 4.2: Task Planner + DAG 调度（任务拆分）

**目标**：cici咪 能把大需求拆成多个任务，支持依赖关系。

**交付物**：
- `engine/task_planner.py`（拆分逻辑）
- Task Scheduler 支持依赖调度（DAG 执行顺序）
- task_table 的 `depends_on` 字段真正使用

**场景**：
```
GitHub 新 Issue: "完整实现 OAuth 2.0 登录"
  ↓
Issue Parser 识别为"大需求"
  ↓
Task Planner 调用 cici咪 拆分：
  - Task A: 设计 OAuth schema
  - Task B: 实现 /auth/login
  - Task C: 实现 /auth/callback
  - Task D: 前端登录页
  - Task E: 测试
  ↓
依赖关系：A → B → C → D → E（线性）
或：A → (B, C, D) → E（并行）
  ↓
Task Scheduler 按 DAG 执行
```

**优先级**：高（拆分是自治的前提）

**预估工作量**：4-5 天

---

### Phase 4.3: Agent Bids（认领机制）

**目标**：任务可以"竞拍"，而不是硬编码分配给谁。

**交付物**：
- `engine/agent_bids.py`
- task_table 新字段：`bidding_deadline`, `bids`（JSON 数组）
- Router 升级：支持"智能路由"

**场景 1：基础认领**
```
新任务: "Dashboard 加刷新按钮"（type="frontend"）
  ↓
Router: 前端任务 → coco咪
  ↓
Agent Bids: coco咪 竞拍（bid_reason: "前端是我的职责"）
  ↓
分配给 coco咪
```

**场景 2：竞拍**
```
新任务: "优化 API 性能"（type="performance"）
  ↓
Router: 性能任务可能前端/后端都有责任
  ↓
Agent Bids:
  - coco咪: "我可以优化数据库查询"
  - soso咪: "我可以加缓存"
  ↓
Conflict Resolver: 两个方案都好，拆成两个任务
```

**优先级**：中（可以让 cici咪 先硬编码分配，以后再升级）

**预估工作量**：5-6 天

---

### Phase 4.4: Conflict Resolver（辩论→投票）

**目标**：agent 意见不合时，通过系统化流程解决。

**交付物**：
- `engine/conflict_resolver.py`
- task_table 新字段：`conflict_status`（"debating"/"voting"/"resolved"）
- Chat 显示辩论消息

**场景**：
```
任务: "是否用 TypeScript 重写 Dashboard"
  ↓
cici咪: "建议用 TS，类型安全"
coco咪: "建议继续用 JS，快速迭代"
  ↓
Conflict Resolver:
  1. 识别冲突（不同意见）
  2. 创建辩论子任务
  3. 邀请 soso咪 投票
  4. 裁决：多数票决定
  5. 转为 GitHub Issue/PR comment 记录
  ↓
继续执行或转人工决策
```

**优先级**：中（可以先不实现，cici咪 有分歧直接问人类）

**预估工作量**：7-8 天

---

### Phase 4.5: Git Worktree 隔离（并发安全）

**目标**：多 agent 并发执行不会互相覆盖文件。

**交付物**：
- `engine/worktree_manager.py`
- 每个任务在独立的 git worktree 中执行
- 执行完成后 PR 到 main

**场景**：
```
两个任务同时进行：
  - Task A: coco咪 改前端
  - Task B: soso咪 改后端
  ↓
Git Worktree:
  - /tmp/teamchat-worktree-001/ (coco咪)
  - /tmp/teamchat-worktree-002/ (soso咪)
  ↓
执行完成后自动提 PR，不会互相覆盖
```

**优先级**：中（可以先串行执行，以后再并发）

**预估工作量**：3-4 天

---

### Phase 4.6: 自愈机制（失败重试）

**目标**：agent 执行失败时，自动重试或转派。

**交付物**：
- `engine/healer.py`
- task_table 新字段：`retry_count`, `last_error`
- 重试策略（指数退避）

**场景**：
```
任务: "跑测试套件"
  ↓
soso咪 执行失败（network error）
  ↓
Healer 检测失败：
  - retry_count < 3 → 重试
  - retry_count >= 3 → 转派给 cici咪 人工审查
  ↓
重试成功 → 标记为 done
```

**优先级**：低（可以先手动失败处理）

**预估工作量**：2-3 天

---

## 数据库 Schema 扩展

### task_table 新字段

```sql
ALTER TABLE task_table ADD COLUMN source TEXT NOT NULL DEFAULT 'chat';  -- 'chat' | 'github_issue' | 'agent_created'
ALTER TABLE task_table ADD COLUMN github_ref TEXT NOT NULL DEFAULT '';  -- '#1' 或 'PR #42'
ALTER TABLE task_table ADD COLUMN depends_on TEXT NOT NULL DEFAULT '[]';  -- JSON 数组
ALTER TABLE task_table ADD COLUMN bidding_deadline TEXT NOT NULL DEFAULT '';  -- ISO 时间戳
ALTER TABLE task_table ADD COLUMN bids TEXT NOT NULL DEFAULT '[]';  -- JSON: [{agent: 'coco咪', reason: '...'}]
ALTER TABLE task_table ADD COLUMN conflict_status TEXT NOT NULL DEFAULT '';  -- 'debating' | 'voting' | 'resolved'
ALTER TABLE task_table ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE task_table ADD COLUMN last_error TEXT NOT NULL DEFAULT '';
ALTER TABLE task_table ADD COLUMN worktree_path TEXT NOT NULL DEFAULT '';  -- Git Worktree 路径
```

### 新表：conflict_records

```sql
CREATE TABLE conflict_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    participants TEXT NOT NULL DEFAULT '[]',  -- JSON: ['cici咪', 'coco咪']
    positions TEXT NOT NULL DEFAULT '[]',  -- JSON: [{agent: 'cici咪', position: 'use TS'}, ...]
    votes TEXT NOT NULL DEFAULT '[]',  -- JSON: [{agent: 'soso咪', vote: 'cici咪'}, ...]
    resolution TEXT NOT NULL DEFAULT '',  -- 裁决结果
    resolved_by TEXT NOT NULL DEFAULT '',  -- 谁裁决的
    resolved_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES task_table(id)
);
```

---

## 风险与未决

| 风险 | 缓解措施 |
|---|---|
| 4.1 GitHub API 限流 | 使用三不同 PAT 分散请求 |
| 4.2 DAG 调度死锁 | 限制依赖深度（最多 3 层） |
| 4.3 Agent Bids 饥饿 | 优先让 agent 认领自己擅长的任务 |
| 4.4 辩论无限循环 | 超时后转人类裁决 |
| 4.5 Worktree 磁盘占用 | 定期清理完成任务的 worktree |
| 4.6 重试风暴 | 指数退避，最多重试 3 次 |

---

## 总时间估算

| Phase | 工作量 | 累计 |
|---|---|---|
| 4.1: GitHub Adapter | 3-4 天 | 1 周 |
| 4.2: Task Planner + DAG | 4-5 天 | 2 周 |
| 4.3: Agent Bids | 5-6 天 | 3 周 |
| 4.4: Conflict Resolver | 7-8 天 | 4-5 周 |
| 4.5: Git Worktree | 3-4 天 | 5 周 |
| 4.6: 自愈机制 | 2-3 天 | 6 周 |

**最小可行版本（MVP）**：4.1 + 4.2（2 周）
- 能实现：GitHub Issue → 任务拆分 → 执行
- 基本覆盖："人类发需求 → cici咪 拆 → coco咪/soso咪 执行"

**完整版本**：4.1-4.6（6 周）
- 能实现：完整拉模式，人类变成观察者

---

## 下一步

1. 确认这个分段计划是否合理
2. 决定先做 MVP（4.1 + 4.2），还是更激进
3. 更新 PROGRESS.md，进入 Phase 4.1

---

## 参考

- spec: `docs/specs/2026-07-08-teamchat-design.md`
- ADR-003: CLI 逐行输出 + 审批卡片
- PROGRESS.md: 当前进度
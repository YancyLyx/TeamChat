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
| 任务建模（需求 → DAG） | ❌ 无 | 只能创建单任务 |
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
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │  Task Scheduler  │  │  Agent Runner    │                        │
│  │  轮询 + 执行     │  │  CLI 驱动        │                        │
│  │  依赖检查        │  │  Session 恢复    │                        │
│  └──────────────────┘  └──────────────────┘                        │
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

## 协作闭环（核心缺失）

**ADR-003 承诺的流程**，但上述架构图缺少的关键模块。

### 两条铁律（解决"时机判断"与"prompt 有效性"两个问题）

经过设计审查，确认 Phase 4.0 必须遵守：

1. **Engine 零决策** — Engine 不判断 done/fail、不判断"该不该审"。所有 agent 的成功结果都推给 cici咪 审；失败结果走确定性重试（exit_code/超时/重试计数），重试耗尽才升级 cici咪。Engine 只做轮询、派发、排队、计数。
2. **prompt 现写，不预写** — cici咪 审核时看到 agent 的实际产出，**当场写**下一步 prompt 并 `create_task`。绝不预写后续 prompt 自动派发（预写 prompt 不知道实际产出，对 review 类任务必然失效）。

> 这两条直接回应了两个质疑：①"怎么保证判断时机"→ Engine 不判断，全部流经 cici咪；②"怎么保证 prompt 有效"→ cici咪 看着实际产出现写。

### ADR-003 真实场景 × Phase 4.0 模块 对照

| Step | 人肉路由（你做的） | 平台自动化 | Phase 4.0 模块 | 谁决策 |
|---|---|---|---|---|
| 1 | 发需求给 cici咪 | `/api/chat` spawn cici咪(--resume) | chat.py（已有） | cici咪 分析 |
| 2 | cici咪 给你 prompt 让你发给 coco咪 | cici咪 `create_task(A, coco咪, prompt=现写)` | MCP（已有） | cici咪 写 prompt |
| 3 | 你把 prompt 粘贴给 coco咪 | Task Scheduler 发现 A unblocked → spawn coco咪 | **PR1 Task Scheduler** | Engine 派发（无决策） |
| 4 | coco咪 完成但你还在等 cici咪，先把 coco咪 输出存着 | coco咪 完成 → cici咪 busy → 结果入队；cici咪 idle → spawn cici咪(--resume) 喂结果 | **PR2 Result Relay** | Engine 排队（无决策） |
| 5 | cici咪 看完，给你 prompt 发给 soso咪 | cici咪 审核 → `update_task(A, done)` → `create_task(B, soso咪, prompt=现写, depends_on=[A])` | MCP（已有） | cici咪 决策+写 prompt |
| 6 | 你把 prompt 粘贴给 soso咪 | Task Scheduler 发现 B unblocked → spawn soso咪 | PR1 Task Scheduler | Engine 派发（无决策） |
| 7 | 把 soso咪 输出给 cici咪 → 合并 | Result Relay 回流 → cici咪 审核 → merge | PR2 + MCP | cici咪 决策 |
| 失败 | 你看到错误手动重试 | Healer 重试3次 → 升级 cici咪 | **PR3 Healer** | Engine 计数→cici咪 决策 |

### 模块职责边界（确保 Engine 不越权）

| 模块 | 做什么 | **不做**什么 |
|---|---|---|
| Task Scheduler | 轮询 `unblocked_tasks()` → spawn agent | ❌ 不判断 done/fail、不写 prompt |
| Result Relay | agent 完成 → 推 cici咪（busy 排队 / idle 批量喂） | ❌ 不判断结果好坏、不创建任务 |
| Healer | 失败 → 重试计数 → 升级 | ❌ 不判断"可恢复 vs 逻辑错误"（升级后 cici咪 判断） |
| cici咪 | 审核、判断 done/fail、写 prompt、create_task、update_task | —（唯一决策者） |

### cici咪 审核 的落地方式（重要）

cici咪 不是常驻进程，也不通过 stdin 接收消息（当前 `runner._run` 是一次性 spawn，prompt 走命令行参数）。审核的落地：

- **不走 task_table** — 审核是"元操作"，不是工作单元（ADR-003 §10.4：`agent_calls` 记录所有 activity，`tasks` 只记录 cici咪 编排的工作单元）
- **走 agent_calls** — 审核 spawn 记一行日志
- **spawn cici咪(--resume) + 结果拼进 prompt** — 把排队的结果拼成 user message 作为 prompt，恢复上下文审核
- **审核后用 MCP 工具** — `update_task`(done/fail) + `create_task`(下一步，prompt 现写)

---

### 断点 1：Agent 输出回传（Result Relay）

**流程**：
```
coco咪 完成任务 → Engine 提取 text
  → cici咪 busy（Router.is_busy）→ 结果入 Orchestrator._queue（排队，解决"等待"）
  → cici咪 idle → drain_queue → 把排队结果拼成 prompt → spawn cici咪(--resume) 审核
```

**现状**：❌ agent 完成后只更新 task_table，text 不会推给 cici咪。Orchestrator 的 `_queue`/`drain_queue()` 已写好但未接入。

**实现**：`engine/result_relay.py`，复用 `Orchestrator._queue` + `drain_queue()` + `_spawn_with_session` 模式。**不写 stdin**（runner 不支持），而是 spawn cici咪(--resume) 把结果拼进 prompt。

**优先级**：最高（这是协作的基础）

---

### 断点 2：依赖检查 + 自动派发

**流程**：
```
cici咪 更新任务表（#14 done）→ Engine 检查依赖 → #15 的依赖满足 → 派发
```

**现状**：
- ✅ `task_table.unblocked_tasks()` 已实现
- ❌ Task Scheduler 只轮询 pending，不调用 `unblocked_tasks()`

**缺失逻辑**：
```python
class TaskScheduler:
    async def run(self):
        while self._running:
            # 新增：检查依赖
            pending = self.task_table.list_tasks(status="pending")
            unblocked = self.task_table.unblocked_tasks()
            for task in unblocked:
                await self._run_one(task)
            await asyncio.sleep(2.0)
```

**优先级**：高（DAG 执行的核心）

---

### 断点 3：失败重试

**ADR-003 承诺**（C6）：
```
3次重试 → 三选项：
  1) 重试
  2) 转派（换 agent）
  3) 标记 abandoned + 通知人类
```

**现状**：❌ 完全没有

**缺失模块**：`engine/healer.py`

```python
class Healer:
    """失败重试与转派。"""

    async def handle_failure(self, task: Task, error: str):
        task.retry_count += 1
        if task.retry_count < 3:
            重试(指数退避)
        else:
            问 cici咪：重试/转派/放弃
```

**优先级**：中（可以先手动失败处理，但长期必须有）

---

### 自洽的完整闭环（中枢模式）

```
人类发消息
  ↓
/api/chat → spawn cici咪(--resume) 分析 → create_task(#14, coco咪, prompt=现写)
  ↓
Task Scheduler 轮询：#14 unblocked → spawn coco咪         [Engine 派发，无决策]
  ↓
coco咪 完成 → Result Relay
  → cici咪 busy? → 入队（等待）                              [Engine 排队，无决策]
  → cici咪 idle  → spawn cici咪(--resume) 喂 #14 结果
  ↓
cici咪 审核 #14 → update_task(#14, done) → create_task(#15, soso咪, prompt=现写, depends_on=[14])
  ↓                                                          [cici咪 决策+写 prompt]
Task Scheduler 轮询：#15 依赖 #14 已 done → unblocked → spawn soso咪
  ↓
soso咪 完成 → Result Relay → spawn cici咪(--resume) 喂 #15 结果
  ↓
cici咪 审核 #15 → merge PR → 全部 done
  ↓
失败分支：agent exit_code≠0 → Healer 重试3次 → 仍失败 → spawn cici咪 决策(重试/转派/放弃)
```

**自洽性验证**：
- ✅ 时机判断：Engine 不判断，所有成功结果流经 cici咪，失败走确定性重试
- ✅ prompt 有效性：每个 `create_task` 的 prompt 都是 cici咪 看过实际产出现写的
- ✅ 决策权：只有 cici咪 调用 `update_task`(done/fail) 和 `create_task`，Engine 只搬运

---

## 未来考虑（暂不实施）

| 功能 | 理由 | 预计时间 |
|---|---|---|
| **Git Worktree 隔离** | Phase 4.0 的协作闭环中，每个 Agent 单实例串行执行，并发场景极少。一个 Agent 完成 → commit → 下一个 Agent 开始，不需要多目录隔离。可在将来有并发需求时再做。 | 3-4 天 |

---

## 分段实施计划（修订）

### Phase 4.0: 协作闭环基础（必做，所有断点）

**目标**：落地 ADR-003 中枢模式完整闭环（见上方"自洽的完整闭环"），补齐三个断点。

**交付物（拆 2 个 PR）**：
- **PR1** 协作闭环骨架 — `engine/task_scheduler.py`（轮询 `unblocked_tasks()` → 派发）+ `engine/result_relay.py`（cici咪 busy 入队 / idle 批量喂）+ 改造 `chat.py`（去掉同步派发，Scheduler 接管）+ 集成 `api/main.py` lifespan。三者紧密耦合：Scheduler 和 Relay 必须一起（agent 完成后要立刻有人接结果），chat.py 不改会与 Scheduler 重复派发，故合并为一个 PR。
- **PR2** 失败重试（Healer）+ 端到端测试。

**铁律**：必须遵守"Engine 零决策 + prompt 现写"。`update_task`(done/fail) 和 `create_task` 只能由 cici咪 调用，Engine 不碰。Engine 派发 agent 后只标记 `running`；agent 完成后结果推 cici咪 审核，cici咪 决定 done/fail。

**优先级**：最高（没有这个，后续所有 Phase 都无法运作）

**预估工作量**：5-6 天

---

### Phase 4.1: GitHub Adapter（外部接入）

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

### Phase 4.2: Task Planner + DAG 调度（任务建模）

**目标**：cici咪 将每个需求建模为 DAG 任务树，Engine 按依赖顺序自动派发。小需求是退化的单节点 DAG，大需求是多步骤 DAG。

**交付物**：
- `engine/task_planner.py`（DAG 建模）
- Task Scheduler 支持依赖调度（DAG 执行顺序）
- task_table 的 `depends_on` 字段真正使用

**场景 1：小需求（退化 DAG）**
```
人类: "@coco咪 修一个 CSS bug"
  ↓
cici咪 分析 → 建模为单节点 DAG:
  - Task A: 修复 CSS bug → coco咪
  ↓
依赖: 无
  ↓
Task Scheduler 派发 A → 完成
```

**场景 2：标准需求（开发→审查→合并）**
```
人类: "给 Dashboard 加刷新按钮"
  ↓
cici咪 分析 → 建模为 3 节点 DAG:
  - Task A: 实现刷新按钮 → coco咪
  - Task B: Review → soso咪（depends_on=[A]）
  - Task C: 合并 → cici咪（depends_on=[B]）
  ↓
Task Scheduler: A → B → C 顺序执行
```

**场景 3：大需求（多步骤 DAG）**
```
GitHub 新 Issue: "完整实现 OAuth 2.0 登录"
  ↓
cici咪 分析 → 建模为多步骤 DAG:
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

**场景 4：DAG 中途发现问题（设计决策：追加修复，不搞回退）**
```
A(开发) → B(review) → C(合并)，B 发现 A 有 bug
  ↓
方案 ✅（采纳）: cici咪 审核 B 结果时 → 创建 D(修复, depends_on=[B])
  → E(复查, depends_on=[D]) → C(合并)
  DAG: A → B → D → E → C（无环，历史保留，审计完整）
方案 ❌（否决）: 重置 A 重新执行
  - 原 prompt 没有 bug 信息，agent 不知道为何重做
  - 原 A 的完成记录还在，审计混乱
  - 需要"回退"特殊机制，增加复杂度
回退只用于极端情况（整个 DAG 方向错误、需求彻底推翻）
```

**场景 5：用户中途提问（设计决策：排队为 DAG 新节点）**
```
TaskScheduler 派发 soso咪 执行任务 X（running）
  ↓
用户发 "@soso咪 先看这个问题"
  → soso咪 busy → 消息排队成任务 D（depends_on=[]）
  → soso咪 完成 X → 审核 → 空闲 → 派发 D
  → soso咪 处理用户问题
同一 agent 绝不并发 spawn（CLI session 冲突），
用户中途提问 = DAG 追加节点（与场景 4 原则一致）
```

**实施完善点（2026-08-01 落地）**

| # | 完善点 | 实现 |
|---|---|---|
| ① | 依赖失败/废弃 → 静默阻塞 | `orphan_deps()` + `blocked_by_failure()`，`dag_summary` 返回，cici咪 可发现 |
| ② | 依赖不存在（孤儿依赖） | `create_task` 校验 depends_on 存在 → 警告 |
| ③ | 审核/分析创建的 MCP 任务 session 错误（默认 1） | `fix_new_task_sessions()` 共享函数，chat/result_relay/scheduler 三处调用 |
| ④ | prompt 说 update_task 能修 depends_on 但 MCP 不支持 | `update_task` 支持可选 depends_on（schema + handler） |
| ⑤ | 审核 prompt 引导"追加修复" | ResultRelay 审核 prompt 明确：发现问题 → 创建修复任务，不回退 |
| ⑥ | 用户消息 vs 自动派发并发冲突 | chat.py 三处路径 is_busy 检查：空闲直接 spawn，忙时排队成任务（TaskScheduler 调度）；greeting 忙的跳过 |

**engine/task_planner.py 提供的确定性工具（Engine 不决策）**：
- `detect_cycles()` — 循环依赖检测（DFS 三色标记，支持 session 隔离）
- `task_tree()` — 某任务的 DAG 子树
- `dag_summary()` — 概况（数量/状态/循环/孤儿/失败阻塞）
- `fix_new_task_sessions()` — MCP 创建任务 session 修正
- MCP 工具：`dag_summary`、`task_tree`（共 6 个工具）

**优先级**：高（拆分是自治的前提）

**预估工作量**：4-5 天

---

### 完善点⑦：实施前确认（Human-in-the-loop，2026-08-03 设计）

**问题**：系统当前"用户发一句话 → cici咪 分析 → 直接建 DAG 派发"，跳过了人肉路由的讨论环节（cici咪 先出计划 → 人类确认 → 才执行）。需求模糊时 cici咪 倾向直接按理解建任务，可能做错方向。

**方案对比**：
| 方案 | 判断者 | 结论 |
|---|---|---|
| Engine 消息分类（硬编码规则） | 规则（@咪/动作词） | ❌ 否决：误判风险，机械 |
| **prompt 引导实施前确认** | cici咪（有完整上下文） | ✅ 采纳：像真人对话，确认主动权在人类 |

**流程**：
```
你: "实现 Tasks 看板"
  → cici咪 分析（第一轮）: 回复实施计划（拟建哪些任务、依赖关系），
    "确认后开始？" ← 明确不创建任务
  → 你: "可以，开始"
  → cici咪 再次分析（session 上下文保留，记得之前的计划）→ 建 DAG → 派发
```

**机制依赖**（全部已有）：
- cici咪 记住之前讨论：session `--resume` ✅
- 确认消息再次触发分析：/api/chat ✅
- cici咪 遵守"先确认再建任务"：prompt 行为引导（非硬编码）

**边界**：
- 审核环节**不确认**：任务完成后的审核（done/fail/追加修复）是流程内决策，cici咪 直接执行（否则太慢）
- 简单问答不建任务（现状）
- 需求明确且用户已表达执行意图时，cici咪 可减少确认轮次（灵活判断）

**实施**：仅改 `build_cici_analysis_prompt`（分析 prompt）——引导 cici咪 先出计划征求确认，确认后才用 MCP 创建任务。

---

### Tasks 看板设计（2026-08-03，前端功能，替代 ADR-003 §8.2 的 Tasks tab 原设计）

**目标**：解决"流程透明度"——用户能直观看到任务状态（running/done）、DAG 走到哪、失败原因。数据已加载（App.jsx setTasks）未渲染，补齐渲染层。

**5 个优化点**（相对 ADR-003 §8.2 原设计）：

| # | 优化 | 说明 |
|---|---|---|
| 1 | 依赖可视化 | 任务卡片显示"等 #16 完成"，直接回答"DAG 到哪了" |
| 2 | Waiting 分组（等依赖） | 区分"可执行 pending"和"被依赖阻塞"，一眼看出流程卡点 |
| 3 | Failed 分组 + 重试信息 | 失败任务显示 retry_count/last_error + 三选项按钮（重试/转派/放弃，调 update_task） |
| 4 | 按 agent 筛选 | 查看单个咪的任务 |
| 5 | 实时更新 | WebSocket `task_table_updated` 事件已有，看板自动刷新 |

**效果图**：

```
┌─ 📋 Tasks ──────────────────────────── [全部 agent ▾] ─┐
│  🔴 Running (1)                                       │
│    #16 实现看板 UI ── coco咪                          │
│      🔄 执行中 23s              [依赖 #15 ✓]          │
│  ⏳ Waiting (2)          ← 依赖未满足                  │
│    #17 审查看板 UI ── soso咪                          │
│      ⏸ 等 #16 完成                                    │
│    #18 合并收尾 ── cici咪                             │
│      ⏸ 等 #17 完成                                    │
│  📝 Pending (1)                                       │
│    #19 排队: "先看这个问题" ── coco咪                 │
│  ✅ Done (5)                                          │
│    #15 建模看板设计 ── cici咪   ✓                     │
│  ❌ Failed (1)                                        │
│    #8 写测试计划文档 ── coco咪                        │
│      ⚠️ 重试3次: network timeout                      │
│      [重试] [转派] [放弃]                             │
└────────────────────────────────────────────────────────┘
```

**分组规则**：
- Running：status=running
- Waiting：status=pending 且 depends_on 未满足（`task_table.blocked_tasks()`）
- Pending：status=pending 且无依赖阻塞（`task_table.unblocked_tasks()`）
- Done：status=done
- Failed：status=failed/abandoned（显示 retry_count/last_error）

**数据来源**：`GET /api/tasks/table`（已有）+ WebSocket `task_table_updated`（已有）

**实现者**：coco咪（前端职责）。用户发消息 → cici咪 分析 → 派发 coco咪。

**面板改进（2026-08-03，用户要求，已实现）**：
- **Done 倒序**（最新在前）+ 默认显示 5 个 + "▼ 展开全部"折叠
- **abandoned 独立分组**（"已放弃"，默认折叠）——修复"点放弃没反应"感知（之前 abandoned 与 failed 同组，视觉无变化；数据库实际已更新）
- Failed / 已放弃 也倒序（最新问题最显眼）
- 转派后的原任务标记 abandoned（如 #21 → #25），从 Failed 主列表移除

**失败按钮流程（重试/转派/放弃）— 透明度说明**：

```
用户点击（前端 TasksBoard）:
  - 重试   → PATCH /api/tasks/table/{id} body={status:'pending', retry_count:0, last_error:''}
  - 转派   → PATCH ... body={status:'pending', agent:<目标咪>, retry_count:0, last_error:''}
  - 放弃   → PATCH ... body={status:'abandoned'}
    ↓
后端（api/routes/tasks.py）: tt.update → 广播 task_table_updated（WS）→ 返回 updated
    ↓
前端: setTasks 本地更新（任务移到 Pending/Waiting 或"已放弃"组）+ WS 同步
    ↓
任务变 pending → TaskScheduler ≤2s 轮询 → unblocked → 派发 agent
    → task_started 事件（聊天室显示"⚡ X 开始执行 #N"）
    → agent 执行 → 完成 → ResultRelay → cici咪 审核
    （转派时派发新 agent，用原 prompt）
```

**按钮定位**：**用户兜底/手动干预**（与 cici咪 审核三选项双保险）。
- 自动链路：失败 → 引擎重试 3 次 → cici咪 审核三选项（MCP update_task）
- 手动兜底场景：
  a. cici咪 审核未触发/卡住（任务卡 failed 无人管）
  b. 用户主动干预（知道问题，不等 cici咪）
  c. 不同意 cici咪 的判定
- 必要性：自动链路正常时用不到；链路异常时是救命稻草（本次 #24 审核未触发即属此场景）

---

### Feature 树标识（feature_id，2026-08-03 设计）

**问题**：每个需求（如"实现 Tasks 看板"）应是一棵 DAG 树且有标识，但当前任务扁平存在 task_table，只有 depends_on 关联，无法区分"哪些任务属于哪个需求"。"depends_on=[] 当根"不可靠（独立任务/转派任务误判）。

**方案**：
- task_table 加 `feature_id INTEGER` 字段（同一棵需求树的节点共享）
- **归属规则**（create_task 时确定，Engine 侧）：
  1. 显式传 feature_id → 归属该树（cici咪 追加修复/转派时传）
  2. depends_on 非空 → 继承依赖任务的 feature_id（自动归属父树）
  3. 都没有 → 新需求：feature_id = 自己的任务 id（自己是根）
  - 转派/改依赖（update）不影响 feature_id（保持原树）
- MCP create_task 加 `feature_id` 参数；prompt 引导"追加修复/转派任务传入原 feature_id"
- **Stats 聚合**：按 feature_id 统计（完成率/失败率/放弃率/转派率/依赖深度/总时长），Feature 标题 = 根任务标题
- 与 task 面板区分：task 面板 = 会话下所有任务（运行视图）；Features = 需求粒度聚合

### Stats 面板优化（2026-08-03 设计，用户要求）

**现状问题**：
1. token 爆炸：codex 的 token_usage 是累计值（每次 resume 是整个线程的 usage，5-6M/次），token_stats 累加 → coco咪 100.5M
2. tool calls 全 0：runner 解析 tool_use 但未存入 agent_calls.tool_calls
3. 三个 Level 目的不清晰、有重复（L1/L2 都是任务统计）
4. 无需求粒度（Feature）聚合

**Level 重定义**（各管一维，消除重复，2026-08-03 修订为 3 tab）：

| Level | 观测维度 | 核心指标 |
|---|---|---|
| L1 效能 | agent 执行质量 | 完成数、成功率、平均时长、token（修累计）、工具调用（补记录） |
| L2 流程 | 流程 + 需求树 | Engine Mode、队列、任务概览、**需求树（进行中 DAG 图 + 已完成折叠）** |
| L3 解放 | 人类参与 | 自动化率、人工介入、消息→完成、审批次数 |

**数据修复**：
- token：codex 改为增量估算（本次 usage - 上次）；claude/cursor 的 usage 是增量（直接累计）
- tool calls：runner 收集 tool_use 事件写入 agent_calls.tool_calls

**需求树（Features）并入 L2**（用户确认，替代独立 FEAT tab）：

```
L2 流程
  ── Engine 状态 ──
  Mode: Parallel · queue: 0
  ── 任务概览 ──
  Total 23 · Done 20 · Running 1 · Pending 2 · 87%
  ── 📦 需求树 ──
  🔄 进行中（1）— DAG 图（实时）
    A1(token) ──┐
    A2(tools) ──┼──► B(测试) ──► C(收尾)
    A3(L3)   ──┘
    ●done ●done ●running(亮灯) ○pending ●done
  ✅ 已完成（2）▼ 折叠
    [实现 Tasks 看板] 11节点 · 91% · done 10 · 放弃 1
```

**DAG 图规则**：
- **进行中需求**（有 running/pending 节点）→ SVG DAG 图（按依赖深度分层，节点 = 任务）
- **已完成需求**（全 done/abandoned）→ 折叠列表（数量 + 总览）
- **节点状态色**：done 绿 / running 蓝（呼吸亮灯）/ pending 灰 / failed 红 / 放弃 暗灰
- **实时更新**：完全数据驱动——tasks 数组变化（WS `task_table_updated`，watchdog 已实现）→ 图自动重绘（新任务/新边/状态灯变化均同步，如 #22 执行中创建的场景）

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

### Phase 4.5: 自愈机制（失败重试）

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
| 4.0 Result Relay 死锁 | cici咪 忙时暂存队列，永不阻塞执行 agent |
| 4.0 依赖检查死循环 | 检测 A → B → A 循环，标记冲突转人类 |
| 4.0 重试风暴 | 指数退避，最多重试 3 次，第 4 次转人工 |
| 4.1 GitHub API 限流 | 使用三不同 PAT 分散请求 |
| 4.2 DAG 调度死锁 | 限制依赖深度（最多 3 层） |
| 4.3 Agent Bids 饥饿 | 优先让 agent 认领自己擅长的任务 |
| 4.4 辩论无限循环 | 超时后转人类裁决 |

---

## 总时间估算（修订）

| Phase | 工作量 | 累计 | 状态 |
|---|---|---|---|
| **4.0: 协作闭环基础** | 5-6 天 | 1 周 | **必做** |
| 4.1: GitHub Adapter | 3-4 天 | 2 周 | - |
| 4.2: Task Planner + DAG | 4-5 天 | 3 周 | - |
| 4.3: Agent Bids | 5-6 天 | 4 周 | - |
| 4.4: Conflict Resolver | 7-8 天 | 5-6 周 | - |
| 4.5: 自愈机制 | 2-3 天 | 6 周 | - |

**最小可行版本（MVP）**：4.0 + 4.1 + 4.2（3 周）
- 能实现：
  - ✅ Agent 输出回传（Result Relay）
  - ✅ 依赖检查 + 自动派发（Task Scheduler）
  - ✅ 简单失败重试（Healer 基础版）
  - ✅ GitHub Issue → 任务拆分 → 执行
- 基本覆盖：ADR-003 完整流程 + 简单 GitHub 集成

**完整版本**：4.0-4.6（6 周）
- 能实现：完整拉模式，人类变成观察者

---

## 下一步

1. 确认这个分段计划是否合理
2. 决定先做 MVP（4.0 + 4.1 + 4.2），还是更激进
3. 更新 PROGRESS.md，进入 Phase 4.0

---

## 参考

- spec: `docs/specs/2026-07-08-teamchat-design.md`
- ADR-003: CLI 逐行输出 + 审批卡片（承诺但未实现：Result Relay / 依赖检查 / 失败重试）
- PROGRESS.md: 当前进度
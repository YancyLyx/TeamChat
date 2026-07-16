# ADR-003（2026-07-16 修订）

---

## 完整场景：人类 → 聊天室 → 任务板 → 完成

### Step 1: 人类发消息

```
人类: "加个刷新按钮"
  ↓
聊天室: 🧑 "加个刷新按钮" (白色气泡，右对齐)
  ↓
POST /api/chat → parse_message → 无 @mention
  ↓
Engine spawn cici咪 (带 --resume)
```

### Step 2: cici咪 分析（人肉路由的前半段）

```
cici咪 做的事（和现在她给我做的一模一样）:
  1. 分析需求
  2. 更新文档 (如需要)
  3. 创建 GitHub Issue（带标签、指派）
  4. 生成给开发 agent 的 prompt

cici咪 的气泡:
  🏗️: "分析完毕。前端任务，拆成 1 个 Issue。#14 派给 coco咪。"
```

### Step 3: cici咪 通过 MCP Tool 创建 Task

```
cici咪 调用 MCP: create_task(
  agent="coco咪",
  title="加个刷新按钮",              ← 对应 Issue 标题
  prompt="去 GitHub Issue #14 ...",   ← 以前人类复制粘贴的内容
  depends_on=[]
)
  ↓
Engine: task_table INSERT
  {id:14, agent:"coco咪", title:"加个刷新按钮", 
   prompt:"去 GitHub Issue #14...", status:"pending"}
```

### Step 4: Engine 派发

```
Engine 检查 task_table:
  #14: status=pending, depends_on=[] → 可执行
  ↓
Engine spawn coco咪 (带 --resume, prompt 来自 task_table)
  ↓
task_table: #14 status → "running"
  ↓
Task 看板:
  #14 "加个刷新按钮"  coco咪  🔄 running
```

### Step 5: Agent 执行 + 并发

```
场景: cici咪 和 coco咪 同时执行不同的任务

cici咪 执行 #13（架构设计）           coco咪 执行 #14（前端实现）
  ↓ 3 秒完成                           ↓ 15 秒完成

cici咪 先完成 ✅:
  1. 聊天室气泡: 🏗️ "#13 完成..."     （写入 sessions 表）
  2. Engine 排队结果，等 coco咪
  3. Task 看板: #13 ✅ done

coco咪 后完成 ✅:
  1. 聊天室气泡: ⚡ "#14 完成，PR #22" （写入 sessions 表）
  2. Engine 检查: 排队中有 cici咪 的结果 → 一起推给 cici咪
  3. Task 看板: #14 ✅ done
```

### Step 6: cici咪 审核

```
cici咪 收到两个结果 → 审核:
  → MCP update_task(13, status="done")
  → MCP create_task(agent="soso咪", title="Review #14 PR #22", depends_on=["14"])
  ↓
Engine 检查: #14 done → #15 依赖满足 → 派发 soso咪
```

### Step 7: 完成

```
soso咪 review 通过 → chat bubble + task done
cici咪 合并 PR → GitHub Issue close
所有 task ✅ done → 完成
```

---

## 数据流

```
所有 agent 文本输出:
  → chat bubble（前端渲染）
  → agent_calls 表（聊天历史）

cici咪 创建/更新的任务:
  → tasks 表
  → Task 看板（右侧面板）

Engine 执行状态:
  → /api/engine（内存）
  → Agent Sidebar 实时状态灯
  → Live Tab Queue + Recent Events
```

| 数据 | 存哪个表 | 前端展示位置 |
|---|---|---|
| 人类消息 | `agent_calls` (agent_name=human) | 聊天室（白色气泡） |
| cici咪 分析 text | `agent_calls` | 聊天室（蓝色气泡） |
| coco咪 执行 text | `agent_calls` | 聊天室（绿色气泡） |
| Task #14 状态 | `tasks` | Task 看板 + Stats L1 |
| 并行/串行状态 | `/api/engine` (内存) | Agent Sidebar + Live Tab |

---

## 右侧面板：三个 Tab

### [Tasks] — 任务看板（新增）

```
┌─ Task Board ──────────────────┐
│ 📋 Pending (1)                │
│  #14 "加个刷新按钮" → coco咪   │
│                               │
│ 🔄 Running (1)                │
│  #15 "Review PR #22" → soso咪 │
│                               │
│ ✅ Done (3)                   │
│  #13 "架构设计" → cici咪       │
│  #12 "E2E 测试" → soso咪      │
│  #11 "API 层" → coco咪        │
└───────────────────────────────┘
```

TaskCard: 标题 + agent + 状态图标 + GitHub Issue 链接

### [Stats] — L1/L2/L3（已实现 ✅）

### [Live] — Engine 观测（已实现 ✅）

---

## MCP Server 设计

Engine 启动时注册 `teamchat` MCP Server，提供 4 个 tool：

| Tool | 参数 | 做什么 |
|---|---|---|
| `create_task` | agent, title, prompt, depends_on | tasks INSERT |
| `update_task` | task_id, status | tasks UPDATE |
| `list_tasks` | status_filter | tasks SELECT |
| `get_task` | task_id | tasks SELECT one |

cici咪 调用 MCP tool（就像用 Bash）：
```
{"type":"tool_use","name":"mcp__teamchat__create_task",
 "input":{"agent":"coco咪","title":"加个刷新按钮",
          "prompt":"去 GitHub Issue #14...","depends_on":[]}}
```

## /api/approval 设计

```
Claude 输出: {"type":"control_request","request_id":"xxx","request":{"tool_name":"Bash",...}}
  ↓
Engine 存储 pending_approvals → 前端渲染审批卡片
  ↓
人类点击 [允许]:
  POST /api/approval {request_id: "xxx", decision: "allow"}
  ↓
Engine 构建 control_response → 写入 Claude stdin
  ↓
Claude 继续执行
```

## 无 @mention 路由

```
POST /api/chat {content: "加个刷新按钮", teamchat_session_id: 1}
  ↓
parse_message → parsed.mentions = []
  ↓
Engine spawn cici咪（带 --resume）
  prompt = "人类: 加个刷新按钮。分析需求。如果是开发任务，用 MCP create_task 创建。"
  ↓
cici咪 分析 → 调用 MCP create_task
  ↓
Engine 检测到 task 创建 → 检查依赖 → 派发
```

---

## 实施计划

| 顺序 | 任务 | 实现什么 |
|---|---|---|
| 1 | MCP Server | cici咪 能创建/更新任务 |
| 2 | Task Board 前端 | 右侧 [Tasks] Tab |
| 3 | /api/approval | 审批卡片生效 |
| 4 | 无 @mention 路由 | 自动分析 → MCP → 派发 |

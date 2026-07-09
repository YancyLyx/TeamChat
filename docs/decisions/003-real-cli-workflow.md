# ADR-003: Real CLI Workflow — 从"人肉路由"到平台自动化

**Date:** 2026-07-09
**Status:** v3 — Confirmed
**Decider:** Human + cici咪

---

## 0. 目标

> 我会发一条消息，然后你根据这个消息，判断由谁来执行，是并行还是有前后顺序，
> 然后我把你准备的 prompt 复制粘贴给对应的咪，咪回复完之后你需要看到他们的消息，
> 我将他们执行完最后的输出粘贴给你。我主要负责在 CLI 终端按回车授权以及你叫我在
> 终端执行的脚本操作，其他具体的活都是你们干的。

**TeamChat 做的事：把"我"（人类）替换成 Engine + 聊天室。**

| 人类现在做的事 | TeamChat 做的事 |
|---|---|
| 复制粘贴 prompt 给咪 | Engine spawn CLI + 写 prompt |
| 在终端按 y/n 授权 | Claude: 审批卡片。Codex/Cursor: 自动执行 |
| 看咪的输出 | 聊天室实时显示所有 agent 的 text 气泡 |
| 提取正文粘贴给 cici咪 | stream-json 自动分离 text → 聊天室 |
| 手动判断先后顺序 | cici咪 用工具管理任务表 → Engine 查依赖 → 派发 |

---

## 1. 核心原则

### 1.1 cici咪 是唯一决策者

**Engine 不决策。** Engine 只做：spawn CLI、读写 stdin/stdout、解析 JSON、存储、排队、推送消息。所有决策（任务拆分、依赖声明、状态变更、下一步）都是 cici咪 做的。

```
正确的流向:
  coco咪 完成 → Engine 把 text 推给 cici咪 → cici咪 判断 done/fail
  cici咪 修改任务表 → Engine 检查新 unlock 的任务 → 派发

错误的流向:
  coco咪 完成 → Engine 自动标记 done → 自动派发下一个  ❌
```

### 1.2 任务管理用工具，不解析自由文本

cici咪 通过 **MCP 工具** 管理任务表，不是写 `TASK:#14:agent=coco咪:...` 让 Engine 解析。工具提供：

- `create_task(agent, title, depends_on[])` → 返回 task_id
- `update_task(task_id, status)` → status: done / failed
- `list_tasks(status_filter)` → 返回任务表
- `assign_task(task_id, agent)` → 改派

**为什么不用文本解析？** cici咪 的表述可能变化——"交给 coco咪 吧" vs "这个适合 coco咪 做" vs "coco咪 来"。工具调用是结构化的，100% 可靠。

### 1.3 所有 agent 输出进聊天室

stream-json 分离了 text / thinking / tool_use。**text 进聊天室气泡，thinking 折叠，tool_use 渲染为审批卡片。** 不仅仅是 cici咪——coco咪 和 soso咪 的 text 也显示在聊天室。

---

## 2. 完整流程（"给 Dashboard 加刷新按钮"）

### Step 0: 系统启动，获取 Session ID

```
Engine 启动
  ↓
对每个 agent:
  1. 冷启动 CLI（不带 --resume）
     Claude: spawn("claude", ["--print", "--output-format", "stream-json", ...])
     Codex:  spawn("codex", ["exec", "--json", "/exit"])
     Cursor: spawn("cursor-agent", ["--print", "--output-format", "stream-json", "/exit"])

  2. 读 stdout 第一个 JSON 事件:
     Claude:  {"type":"system", ...} → 不包含 session_id？等多几行
             直到 {"type":"system","session_id":"5fbaf844-..."}
     Codex:   {"type":"thread.started","thread_id":"019f40ef-..."}
     Cursor:  {"type":"system","session_id":"04e64d6d-..."}

  3. 捕获 session_id → 存 .teamchat/session_{cli}.txt
  4. 关闭冷启动进程
  5. 重新 spawn（带 --resume <id>，等待第一个真正的消息）
```

### Step 1: 人类发消息

```
人类在聊天室输入: "给 Dashboard 加个刷新按钮"
  ↓
POST /api/chat  →  parse_message("给 Dashboard 加个刷新按钮")
  → parsed.mentions = []
  → parsed.needs_cici_analysis = True
  ↓
Engine spawn Claude（带 --resume 5fbaf844-...）
  stdin: {"type":"user","message":{"role":"user","content":[{"type":"text","text":"人类: 给 Dashboard 加个刷新按钮"}]}}
  ↓
聊天室显示:
  🧑 人类: 给 Dashboard 加个刷新按钮
```

### Step 2: cici咪 分析

```
Claude stdout → Engine 解析事件:
  {"type":"assistant","message":{"content":[
    {"type":"thinking","thinking":"这是前端需求..."},
    {"type":"text","text":"好的，我来分析一下。这是一个前端任务，交给 coco咪。"},
    {"type":"tool_use","name":"mcp__teamchat__create_task","input":{
      "agent":"coco咪",
      "title":"给 Dashboard 加刷新按钮",
      "depends_on":[]
    }}
  ]}}
  ↓
Engine 处理:
  - thinking → 聊天室折叠: "💭 分析中..."
  - text → 聊天室气泡: 🏗️ cici咪: "好的，是前端任务，交给 coco咪。"
  - tool_use(mcp__teamchat__create_task) → Engine 执行:
      → 写入任务表: {id:14, agent:"coco咪", status:"pending", depends_on:[]}
      → 返回结果给 Claude
  ↓
  {"type":"result","subtype":"success","result":"#14 已创建"}
  ↓
cici咪 最终回复:
  🏗️ cici咪: "#14 已创建，派给 coco咪。无依赖，立即执行。"
```

### Step 3: Engine 派发

```
cici咪 的 turn 完成后 → Engine 检查任务表:
  #14: agent=coco咪, depends_on=[], status=pending
  → 无依赖 → 可派发
  ↓
Engine spawn Codex（带 --resume 019f40ef-...）:
  codex exec resume 019f40ef-... --json "cici咪分配任务 #14: 给 Dashboard 加刷新按钮。读 AGENTS.md，在 dashboard/src/ 实现。完成后汇报。"
  ↓
聊天室显示:
  ⚡ coco咪: [💭 开始实现刷新按钮...]
```

### Step 4: coco咪 执行

```
Codex stdout → Engine 解析事件:
  {"type":"item.completed","item":{"type":"reasoning","text":"需要修改..."}}
  {"type":"item.completed","item":{"type":"command_execution","command":"git add ...","exit_code":0}}
  {"type":"item.completed","item":{"type":"agent_message","text":"#14 完成。刷新按钮已添加到 ChatRoom。PR #22 已创建。"}}

Engine 处理:
  - reasoning → 折叠
  - command_execution → 工具调用记录（Codex 自动执行，无审批卡片）
  - agent_message → 聊天室气泡: ⚡ coco咪: "#14 完成。刷新按钮 PR #22。"
  ↓
Engine 把 coco咪 的 text 推送给 cici咪（排队，不打断）:
  → 如果 cici咪 正在忙 → 暂存
  → 如果 cici咪 空闲 → 写入 stdin: {"type":"user","message":...包含coco咪的输出...}
```

### Step 5: cici咪 审核

```
cici咪 收到 coco咪 的输出:
  "coco咪: #14 完成。刷新按钮 PR #22。"
  ↓
cici咪 判断:
  → 代码完成了吗？ → 需要 review
  → 调用工具: mcp__teamchat__update_task(task_id=14, status="done")
  → 调用工具: mcp__teamchat__create_task(agent="soso咪", title="Review #14 PR #22", depends_on=["14"])
  ↓
聊天室显示:
  🏗️ cici咪: "#14 代码完成。需要 review。创建 #15 派给 soso咪。"
```

### Step 6: soso咪 Review

```
Engine 检查: #14 done → #15 依赖满足 → 派发
  ↓
Engine spawn Cursor（带 --resume 04e64d6d-...）:
  cursor-agent --print --output-format stream-json --resume=04e64d6d-... "review PR #22..."
  ↓
soso咪 执行 → text: "Review 通过。代码正确，16/16 tests passed。"
  ↓
聊天室显示:
  🔍 soso咪: "Review 通过。16/16 tests passed。"
  ↓
Engine 把 soso咪 的 text 推给 cici咪
```

### Step 7: cici咪 合并

```
cici咪 收到 soso咪 的结果:
  → 调用工具: mcp__teamchat__update_task(task_id=15, status="done")
  → 调用 GitHubClient: merge PR #22 → close Issue #14 #15
  ↓
聊天室显示:
  🏗️ cici咪: "全部通过 ✅ PR #22 已合并。#14 #15 完成。"
```

---

## 3. 关键技术决策

### 3.1 Session ID 获取

**不用 /exit，用 stream-json 第一个 system 事件。** 冷启动 → 读 stdout JSON → 提取 session_id/thread_id → 保存 → 用 --resume 是真正工作的 spawn。

| Agent | Session ID 来源 | Resume 命令 |
|---|---|---|
| Claude | `{"type":"system","session_id":"..."}` | `claude --print ... --resume <id>` |
| Codex | `{"type":"thread.started","thread_id":"..."}` | `codex exec resume <id> --json "prompt"` |
| Cursor | `{"type":"system","session_id":"..."}` | `cursor-agent --print ... --resume=<id> "prompt"` |

### 3.2 任务管理：MCP Tool

cici咪 通过 MCP 工具操作任务表。Engine 提供 `teamchat` MCP server，注册这些工具：

- `create_task(agent, title, depends_on[])` → task_id
- `update_task(task_id, status)`
- `list_tasks()`
- `assign_task(task_id, agent)`

### 3.3 cici咪 = 唯一决策者

Engine 不判断 done/fail。流程永远是：agent 完成 → Engine 推送 text 给 cici咪 → cici咪 审核 → cici咪 修改任务表 → Engine 检查依赖 → 派发。

### 3.4 聊天室 = 所有 agent 的 text 输出

| 谁 | 样式 |
|---|---|
| 人类 | 白色气泡，右对齐 |
| cici咪 | 蓝色左边框 |
| coco咪 | 绿色左边框 |
| soso咪 | 紫色左边框 |
| 系统 | 灰色居中 |
| 审批卡片 | 内嵌在消息流中 |

### 3.5 审批

| Agent | 方式 |
|---|---|
| Claude | control_request → 前端审批卡片 → 点击 [允许]/[拒绝] → Engine 写 control_response |
| Codex | exec 模式自动执行（sandbox 保护）。危险命令被沙箱拦截 |
| Cursor | print 模式自动执行。危险命令被 Allowlist 拦截 |

### 3.6 结果排队

coco咪 完成时如果 cici咪 还在执行 → Engine 暂存结果 → cici咪 完成后一次性推送所有排队结果。

---

## 4. CLI 命令与事件映射

### 4.1 实测 CLI 命令

| Agent | 命令 |
|---|---|
| Claude | `claude --print --verbose --output-format stream-json --input-format stream-json --permission-prompt-tool stdio [--resume <id>]` |
| Codex | `codex exec [resume <id>] --json "<prompt>"` |
| Cursor | `cursor-agent --print --output-format stream-json [--resume=<id>\|--continue] "<prompt>"` |

### 4.2 统一事件映射

| AgentEvent | Claude | Codex | Cursor |
|---|---|---|---|
| text | `assistant.content[type=text]` | `item.completed[type=agent_message]` | `assistant.content[type=text]` |
| thinking | `assistant.content[type=thinking]` | `item.completed[type=reasoning]` | `type=thinking` |
| tool_use | `assistant.content[type=tool_use]` | `item.completed[type=command_execution]` | `type=tool_call` |
| done | `type=result` | `type=turn.completed` | `type=result` |
| session_init | `type=system` | `type=thread.started` | `type=system` |

### 4.3 附件/图片

前端文件选择器 → Engine 传给 CLI：
- Claude: content block 的 `{"type":"image","source":{...}}`
- 文件: content block 的 `{"type":"text","text":"[Attached: /path/to/file]"}`

---

## 5. 实施优先级

| # | 内容 | 状态 |
|---|---|---|
| C1 | Task Table 数据结构 + Engine API | 待开始 |
| C2 | Runtime Manager（spawn CLI + JSONL parse + session resume）| 原型已写 |
| C3 | MCP Server（teamchat: create_task, update_task, list_tasks）| 待开始 |
| C4 | 聊天室前端（所有 agent 气泡 + 审批卡片 + 附件）| 待开始 |
| C5 | 结果排队 + 依赖检查 | 待开始 |
| C6 | 失败处理（3次重试 → 三选项）| 待开始 |

---

## 6. 当前 Session IDs

| Agent | Session ID | Resume |
|---|---|---|
| cici咪 (Claude) | `5fbaf844-4cbc-48b2-9242-7902d098bd81` | `claude --resume <id>` |
| coco咪 (Codex) | `019f40ef-e8cf-76f0-8b49-6691cc7275f3` | `codex resume <id>` |
| soso咪 (Cursor) | `04e64d6d-de38-4861-a7ce-87c26d28d77f` | `cursor-agent --resume=<id>` |

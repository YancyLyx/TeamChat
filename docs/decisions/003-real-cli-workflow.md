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

### Step 0: 选择/创建会话

```
前端显示会话列表:
  ┌─────────────────────────┐
  │ 📁 TeamChat 开发         │ ← 当前会话，已有 3 个 session ID
  │ 📁 新项目实验             │ ← pending，还没冷启动
  │ [+ 新建会话]              │
  └─────────────────────────┘

你点击 "TeamChat 开发":
  → Engine 加载该会话的三个 session ID
  → 后续所有 spawn 都: cd {该会话目录} + --resume {该会话的 ID}
  → 上下文延续
```

## 2.5 Session 管理 — 多会话、多目录

### 为什么需要多会话

Agent CLI 的上下文由 **session ID** 决定，不是由目录决定。同一个目录 + 同一个 session ID = 同一个上下文。同一个目录 + 不同 session ID = 不同上下文（但共享文件系统）。

因此 TeamChat 支持：
- **同一目录下多个会话**（不同 session ID，不同对话历史，共享代码）
- **不同目录下多个会话**（不同 session ID，不同项目，完全隔离）

示例：
```
会话 A "Phase 4 开发":  目录 /TeamChat, cici咪=5fbaf844, coco咪=019f40ef, soso咪=04e64d6d
会话 B "实验分支":       目录 /TeamChat, cici咪=aaaaaaaa, coco咪=bbbbbbbb, soso咪=cccccccc
会话 C "另一个项目":     目录 /other-project, cici咪=dddddddd, coco咪=eeeeeeee, soso咪=ffffffff
```

### 数据结构

```json
{
  "sessions": [
    {
      "id": "sess-001",
      "name": "TeamChat 开发",
      "directory": "/Users/yanxinluo/Documents/PycharmProjects/TeamChat",
      "agents": {
        "cici咪": {"session_id": "5fbaf844-...", "status": "active"},
        "coco咪": {"session_id": "019f40ef-...", "status": "active"},
        "soso咪": {"session_id": "04e64d6d-...", "status": "active"}
      },
      "created_at": "2026-07-09",
      "last_used": "2026-07-09"
    },
    {
      "id": "sess-002",
      "name": "新项目实验",
      "directory": "/Users/yanxinluo/Documents/experiment",
      "agents": {
        "cici咪": {"session_id": null, "status": "pending"},  ← 还没冷启动
        "coco咪": {"session_id": null, "status": "pending"},
        "soso咪": {"session_id": null, "status": "pending"}
      },
      "created_at": "2026-07-09"
    }
  ]
}
```

### 添加新会话的流程

```
你在前端:
  1. 点 "新建会话"
  2. 输入: 名称 = "新项目实验"，目录 = "/Users/yanxinluo/Documents/experiment"
  3. 点 "创建"

Engine:
  1. 验证目录存在且可访问
  2. 写入会话配置到 SQLite
  3. 对每个 agent 的第一次调用:
     → spawn CLI（不带 --resume，冷启动 + 发 prompt 一起做）
     → stdout 第一行 system/thread.started 事件 → 提取 session_id
     → 保存到 .teamchat/session_{cli}.txt
     → 不需要杀进程，prompt 正常执行
  4. 第二次开始带 --resume <id> 恢复上下文
```

### 删除会话

```
删除会话 = 删除 SQLite 中的记录。
CLI 的 session 文件（~/.claude/projects/...）不删除（用户可能还需要）。
```

### 切换会话

```
你点 "TeamChat 开发" 标签:
  → Engine 加载该会话的 session ID
  → 后续所有 spawn 都 cd 到该会话的目录 + --resume 对应 ID
  → 聊天室显示该会话的历史消息
```

### Session ID 获取

**第一次调用 = 冷启动 + 发 prompt，同时从第一行 stdout 拿 session ID。** 不需要单独的"冷启动→杀进程→再启动"步骤。

```
第一次调用（冷启动）:
  spawn CLI（不带 --resume，直接发 prompt）
  stdout 第一行 → 提取 session_id → 保存到 .teamchat/
  后续:
  spawn CLI（带 --resume <id>，恢复上下文）
```

**三个 CLI 实测都是第一行就包含 ID：**

| CLI | 第一行事件 | ID 字段 | 实测 |
|---|---|---|---|
| Claude | `{"type":"system","session_id":"xxx"}` | `session_id` | ✅ |
| Codex | `{"type":"thread.started","thread_id":"xxx"}` | `thread_id` | ✅ |
| Cursor | `{"type":"system","session_id":"xxx"}` | `session_id` | ✅ |

**方式 B（人工验证）：`/exit` 命令。** 终端交互时手动输入。两种方式拿到的是同一个 ID。

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

---

## 7. MCP Server 设计

### 7.1 什么是 MCP

Model Context Protocol — AI agent 调用外部工具的标准协议。Claude CLI 原生支持。

```
Agent (cici咪)                  MCP Server (TeamChat)
     │                                │
     ├── list_tools() ──────────────→ │ "我有什么工具？"
     │←── [create_task, update_task]  │
     │                                │
     ├── call_tool("create_task",    │
     │     {agent:"coco咪"}) ──────→ │ 实际调用
     │←── {task_id: 14} ──────────── │ 返回结构化结果
```

### 7.2 MCP vs Skill vs Tool 的区别

| | MCP Tool | Skill | 内建 Tool (Bash/Read/Write) |
|---|---|---|---|
| **来源** | MCP Server 提供 | 项目 `.md` 文件 | CLI 自带 |
| **做什么** | 调用外部函数 | 注入 prompt 模板 | 操作文件系统 |
| **有返回值吗** | ✅ 结构化数据 | ❌ 只是文本注入 | ✅ 命令输出 |
| **例子** | `create_task(agent, title)` | `/brainstorming` | `Bash("ls")` |

**Skill = 告诉 Agent 怎么想。MCP Tool = 让 Agent 能做什么。**

### 7.3 TeamChat MCP Server

```
teamchat MCP Server (engine/mcp_server.py):
  tools:
    create_task(agent, title, depends_on) → task_id
    update_task(task_id, status)          → ok
    list_tasks(status_filter)             → [...]
    get_session_info()                    → {agents, session_ids, status}
```

### 7.4 启动方式

Claude CLI 通过 `--mcp-config` 自动启动 MCP Server：

```bash
claude --print \
  --output-format stream-json \
  --input-format stream-json \
  --permission-prompt-tool stdio \
  --mcp-config .teamchat/mcp-config.json
```

`mcp-config.json`:
```json
{
  "mcpServers": {
    "teamchat": {
      "command": "python3",
      "args": ["-m", "engine.mcp_server"],
      "cwd": "/Users/yanxinluo/Documents/PycharmProjects/TeamChat"
    }
  }
}
```

Claude CLI 自动 spawn `python3 -m engine.mcp_server`，通过 stdio JSON-RPC 通信。Agent 在思考时直接 `tool_use: mcp__teamchat__create_task`。

### 7.5 为什么用 MCP 而不用文本解析

cici咪 的表述可能变化——"交给coco咪" vs "这个coco咪来做" vs "coco咪适合这个"。**文本解析不可靠。MCP Tool 调用是结构化的，100% 准确。**

---

## 8. 前端设计

### 8.1 整体布局

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 TeamChat  [📁 会话: TeamChat开发 ▼]          🟢 已连接      │
├────────┬───────────────────────────────────┬────────────────────┤
│        │         📌 聊天室                  │                    │
│ Agent  │                                   │   📋 任务面板       │
│ 状态    │  🏗️ cici咪: 分析完毕              │                    │
│        │     → 拆成 #14 #15               │  #14 coco咪 🔧     │
│ 🏗️cici │  ⚡ coco咪: ✅ #14 完成 PR #22     │  #15 soso咪 ⏳    │
│ 🟢     │  🔍 soso咪: ✅ Review 通过         │                    │
│ ⚡coco │  🏗️ cici咪: 全部完成 ✅            │                    │
│ 🔴     │                                   │                    │
│ 🔍soso │  ┌─ 审批卡片 ─────────────────┐   │                    │
│ 🟢     │  │ 🔧 cici咪 请求: Bash        │   │                    │
│        │  │ git push origin feature     │   │                    │
│        │  │ [允许]  [拒绝]              │   │                    │
│        │  └────────────────────────────┘   │                    │
│        │                                   │                    │
│        ├───────────────────────────────────┤                    │
│        │ 💬 @cici咪 ...        📎 [发送]   │                    │
└────────┴───────────────────────────────────┴────────────────────┘
```

### 8.2 功能区域说明

#### A. 顶部栏

| 元素 | 功能 |
|---|---|
| 🤖 TeamChat | Logo + 标题 |
| 📁 会话选择器 | 下拉菜单：切换/新建/删除会话 |
| 🟢 已连接 | WebSocket 连接状态 |

#### B. 左侧：Agent 状态栏

每个 agent 一张紧凑卡片：
- 头像 emoji + 名字 + 角色
- 状态指示灯：🟢 空闲 / 🔴 执行中 / ⚪ 离线
- 当前任务数 + 成功率
- 点击展开 → 最近会话历史

#### C. 中间：聊天室

| 消息类型 | 样式 | 示例 |
|---|---|---|
| 人类消息 | 白色气泡，右对齐 | "加个刷新按钮" |
| cici咪 text | 蓝色左边框 | "分析完毕..." |
| coco咪 text | 绿色左边框 | "#14 完成 PR #22" |
| soso咪 text | 紫色左边框 | "Review 通过 16/16" |
| 系统通知 | 灰色居中 | "#15 已派发给 soso咪" |
| 审批卡片 | 黄色边框，内嵌按钮 | "🔧 Bash: git push [允许][拒绝]" |
| thinking | 灰色折叠区 | "💭 分析中..." 点击展开 |

#### D. 消息输入框

- 文本框：支持 @mention（`@cici咪` `@coco咪` `@soso咪`）
- @mention 自动补全下拉
- 📎 附件按钮：上传文件/图片 → 取绝对路径传给 CLI
- 发送按钮
- Enter 发送，Shift+Enter 换行
- 中文输入法 Enter 不误触（已有 IME 处理）

#### E. 右侧：任务面板

| 列 | 内容 |
|---|---|
| 📋 待处理 | pending 任务，显示 agent + 标题 |
| 🔧 进行中 | running 任务，显示 agent + 标题 |
| ✅ 已完成 | done 任务，显示 agent + 标题 |

- 每个任务卡片：标题 + 指派的 agent
- 点击 → 跳转 GitHub Issue（如果有）
- 可折叠

### 8.3 会话管理页面

点击顶部 📁 会话选择器 → 弹出会话管理面板：

```
┌─────────────────────────────────┐
│  📁 会话管理                     │
│                                 │
│  ┌─────────────────────────┐   │
│  │ ● TeamChat 开发           │   │  ← 当前
│  │   /Users/.../TeamChat     │   │
│  │   cici✅ coco✅ soso✅    │   │
│  └─────────────────────────┘   │
│  ┌─────────────────────────┐   │
│  │ ○ 新项目实验              │   │
│  │   /Users/.../experiment   │   │
│  │   cici⏳ coco⏳ soso⏳    │   │
│  └─────────────────────────┘   │
│                                 │
│  [+ 新建会话]                    │
└─────────────────────────────────┘
```

**新建会话流程：**
1. 点击 [+ 新建会话]
2. 输入：名称、目录绝对路径
3. Engine 验证目录存在 → 写入 SQLite → 返回会话 ID
4. 第一次发消息时自动冷启动三个 agent → 捕获 session ID → 保存

### 8.4 按钮与交互汇总

| 按钮/交互 | 位置 | 功能 |
|---|---|---|
| 📁 会话选择器 | 顶部栏 | 切换/新建/删除会话 |
| [允许] [拒绝] | 审批卡片 | Claude 工具审批 |
| @mention 自动补全 | 输入框 | 选择目标 agent |
| 📎 附件 | 输入框旁 | 上传文件/图片 |
| 发送 | 输入框旁 | 发送消息 |
| Agent 卡片 | 左侧栏 | 点击展开最近会话 |
| 任务卡片 | 右侧面板 | 点击跳转 GitHub |

### 8.5 参考风格

- **Roundtable**: 干净气泡 + 审批卡片 + Agent 侧边栏
- **Clowder AI**: Hub 风格、operator 旅程设计
- 暗色主题（终端风格），所有文字可读

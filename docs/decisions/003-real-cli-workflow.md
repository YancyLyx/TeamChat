# ADR-003: Real CLI Workflow — 从"人肉路由"到平台自动化

**Date:** 2026-07-09
**Status:** Draft
**Decider:** Human + cici咪

---

## 0. 目标（你要的最终效果）

> 我会发一条消息，然后你根据这个消息，判断由谁来执行，是并行还是有前后顺序，
> 然后我按照你的要求把你给我准备的 prompt 复制粘贴给对应的咪，咪回复完之后你
> 需要看到他们的消息，于是乎我将他们执行完最后的输出粘贴给你。在整个流程中，
> 我主要负责在 CLI 终端上按回车键给他们授权命令操作，以及你叫我在终端执行的
> 脚本等操作，其他具体的活都是你们干的。

**TeamChat 要做的事：把上面这段话里的"我"（人类）替换成 Engine。**

```
人类现在做的事:                      TeamChat 自动做的事:
  复制粘贴 prompt 给咪                  Engine 往 PTY stdin 写 prompt
  按 y/n 授权 Bash                    人类在终端面板按 y/n（保留）
  看咪的输出                           终端面板实时显示
  提取正文粘贴给 cici咪                 Engine 提取正文 → 排队 → 推给 cici咪
  手动判断先后顺序                     Engine 检查任务表依赖
```

**人类保留的事：** 在终端面板按回车授权、执行脚本。其余全部自动化。

---

## 1. 真实操作流程（逐帧）

### 1.1 会话管理（/exit 方式）

**核心：每次人类消息 spawn 一个新的 CLI 进程，带 --resume <sessionId> 恢复上下文。不是长连接，是"spawn per message"。**

**会话 ID 获取（/exit 命令，不用目录扫描）：**

```
首次启动:
  1. Engine spawn CLI（冷启动，不带 --resume）
  2. Engine 往 stdin 写 "/exit
"
  3. CLI 输出当前 session ID 后退出
  4. Engine 捕获 ID → 存储到 .teamchat/session_{cli}.txt
  5. Engine 重新 spawn CLI (带 --resume <id>，发真正的 prompt)

后续启动:
  1. Engine 从 .teamchat/session_{cli}.txt 读 session ID
  2. spawn CLI (带 --resume <id>)
```

**为什么不用目录扫描？** 用户可能多个项目、多次会话，扫描最新文件可能扫到不相关的。`/exit` 命令获取当前目录会话 ID，100% 准确。

**当前 TeamChat 项目 session ID:** cici咪 `5fbaf844...`, coco咪 `019f40ef...`, soso咪 `04e64d6d...`

**恢复命令:**
- Claude: `claude --print ... --resume <id>`
- Codex: `codex exec resume <id> --json "prompt"`
- Cursor: `cursor-agent --print ... --resume=<id> "prompt"`

**存储路径:** `.teamchat/session_{claude,codex,cursor}.txt`### 1.2 协作流程（完整版）

```
场景: 人类说 "开始 Phase 4b"

Step 1. cici咪 分析需求
   → 拆成 3 个任务: #11(cici咪), #12(coco咪), #13(soso咪)
   → 声明依赖: #13 depends on [#11, #12]
   → Engine 写入任务表

Step 2. Engine 派发并行任务
   → #11 → 写入 cici咪 PTY: "实现 --continue 引擎改动"
   → #12 → 写入 coco咪 PTY: "实现 ChatRoom 折叠区"

Step 3. 两只咪同时执行
   ├── cici咪 PTY: 思考... 写代码... [git commit? y/n]
   │      └── 人类在该终端面板按 y
   └── coco咪 PTY: 实现... 修改文件... [git push? y/n]
          └── 人类在该终端面板按 y

Step 4. coco咪 先完成 ✅
   → Engine 提取正文: "Task complete: Issue #12 — ..."
   → Engine 检查: cici咪 还在执行中 🔴
   → Engine 排队: 暂存 coco咪 的输出，不打扰 cici咪
   → 人类在 coco咪 终端面板看到完整输出（可滚动）

Step 5. cici咪 也完成 ✅
   → Engine 提取 cici咪 正文
   → Engine 检查: 排队中有 coco咪 的结果
   → 把两个人的结果一起推给 cici咪

Step 6. cici咪 分析两个结果
   → #11 done, #12 done
   → Engine 检查任务表: #13 的依赖全部满足
   → 通知 cici咪: "#13 可以派发了"
   → cici咪 生成 soso咪 的 prompt → 发给 Engine

Step 7. Engine 派发给 soso咪
   → 写入 soso咪 PTY: "E2E 测试 #13..."
   → soso咪 执行... 需要授权 → 人类按 y
   → soso咪 完成 ✅
   → Engine 提取正文 → 推给 cici咪

Step 8. cici咪 分析 → 全部完成 ✅
```

### 1.3 关键规则

| 规则 | 说明 |
|---|---|
| **不打断** | Agent 执行中不推送其他 agent 的结果，排队等完成 |
| **全完成才汇总** | 并行任务全部完成后，一次性推送所有正文给 cici咪 |
| **依赖检查** | Engine 自动检查 blocked_by，不满足不派发 |
| **只有正文** | Agent 间传递的是提取后的正文，完整输出只在终端面板可见 |

---

## 2. 会话：spawn per message + --resume

### 2.1 冷启动 vs 恢复

详见 1.1 节。冷启动用 `/exit` 获取 session ID，后续用 `--resume` 恢复。

### 2.2 Stream-JSON 通信（已实测验证 ✅）

**不

需要 PTY。CLI 作为 headless 子进程运行，每次消息 spawn 一次。**

```
人类发消息 → Engine spawn CLI（带 --resume）
  → stdin: 写 JSON 用户消息
  → stdout: 读 JSONL events
  → 进程自然结束
  → 下次消息再 spawn（恢复同一个 session）
```

**实测确认的 CLI 命令：**

| Agent | 完整命令 | stdin 交互 |
|---|---|---|
| Claude | `claude --print --verbose --output-format stream-json --input-format stream-json --permission-prompt-tool stdio [--resume <id>]` | 写 `{"type":"user","message":...}` |
| Codex | `codex exec [resume <id>] --json "<prompt>"` | prompt 在 CLI 参数里 |
| Cursor | `cursor-agent --print --output-format stream-json [--resume=<id>\|--continue] "<prompt>"` | prompt 在 CLI 参数里 |

### 2.3 统一事件映射（已实测验证 ✅）

三个 CLI 输出的 JSON 格式不同。Engine 通过 Runtime Manager 统一映射为 `AgentEvent`：

| AgentEvent | Claude 来源 | Codex 来源 | Cursor 来源 |
|---|---|---|---|
| `text` | `assistant.content[type=text]` | `item.completed[type=agent_message]` | `assistant.content[type=text]` |
| `thinking` | `assistant.content[type=thinking]` | `item.completed[type=reasoning]` | `type=thinking` |
| `tool_use` | `assistant.content[type=tool_use]` | `item.completed[type=command_execution]` | `type=tool_call` |
| `done` | `type=result` | `type=turn.completed` | `type=result` |
| `session_init` | `type=system` | `type=thread.started` | `type=system` |

### 2.4 审批机制（已实测验证 ✅）

| Agent | 审批方式 | TeamChat 如何处理 |
|---|---|---|
| **Claude** | `type=control_request` 事件 | ✅ 前端渲染审批卡片，人类点击 [允许]/[拒绝]，Engine 写 control_response 到 stdin |
| **Codex** | exec 模式下自动执行（sandbox 保护）| 接受默认行为。如果需要审批，用配置而非 CLI flag |
| **Cursor** | print 模式下自动执行（`--auto-review` 仅 Allowlist）| 接受默认行为。危险命令自动被 Allowlist 拒绝 |

**决策：Claude 走审批卡片。Codex/Cursor 接受默认自动执行/拒绝。安全网在 PR review 和 merge gate。**

---

## 3. Agent 输出处理（不再需要"正文提取"！）

### 3.1 Stream-JSON 自带结构分离

stream-json 模式下，CLI 自己把输出分成三类，**不需要 Engine 做正文提取**：

| JSON 事件类型 | 含义 | 前端展示 |
|---|---|---|
| `type: "text"` | Agent 的正文回复 | 聊天气泡（干净） |
| `type: "thinking"` | Agent 的思考过程 | 折叠区 |
| `type: "tool_use"` | Agent 想用工具 (Bash/Write/Read) | 审批卡片 |

### 3.2 各 CLI 适配

```
Claude (stream-json):
  parseLine(line) → event.type:
    "assistant" → content[].type = "text" | "thinking" | "tool_use"
    "result"   → turn completed
    "control_request" → 审批请求 → 前端渲染卡片

Cursor (stream-json):
  待实测，结构可能类似。
  如不提供 stream-json，回退到 --output-format json 模式解析 result 字段。

Codex (--json JSONL):
  待实测。至少可作为 JSONL 行解析。
```

### 3.3 正文用途

- Agent 间转发（coco咪 text → cici咪 做决策）— **text 已经是干净的**
- 聊天室消息 — **text 直接渲染成气泡**
- Agent 活动面板 — **显示完整事件流（thinking + text + tool_use）**

---

## 4. UI 设计（修正：不再用 xterm.js）

### 4.1 布局

```
┌──────────────────────────────────────────────────────────────────┐
│  🤖 TeamChat                                         🟢 已连接   │
├────────┬──────────────────────────────────┬─────────────────────┤
│ Agent  │        📌 聊天室                  │  Agent 活动面板      │
│ 状态    │                                  │  (点击 agent 切换)   │
│        │  🧑: 开始 Phase 4b                │                     │
│ 🏗️cici │  🏗️: 拆成 #11 #12 #13             │ ┌─ coco咪 活动 ───┐ │
│ 🟢/🔴  │  💬 coco咪: #12 完成 ✅            │ │ 💭 思考...      │ │
│        │     [查看详情]                     │ │ 🔧 Bash(git)   │ │
│ ⚡coco │  [🔧 审批] git push origin?        │ │   [允许][拒绝]  │ │
│ 🟢/🔴  │     [允许] [拒绝]                  │ │ 💬 PR #20 done │ │
│        │  🏗️: 收到，派发 #13 给 soso咪      │ │ ✅ turn 完成    │ │
│ 🔍soso │  💬 soso咪: Review 通过 ✅          │ └────────────────┘ │
│ 🟢/🔴  │                                  │                     │
│        ├──────────────────────────────────┤ [cici][coco][soso] │
│        │ 💬 @cici咪 ...            [发送]  │                     │
└────────┴──────────────────────────────────┴─────────────────────┘
```

**左：Agent 状态栏**（谁在线/忙碌）
**中：聊天室**（人类 ↔ cici咪 对话 + 系统消息 + 审批卡片）
**右：Agent 活动面板**（选中 agent 的事件流：thinking 折叠、tool_use 卡片、text 气泡）

### 4.2 聊天室内容（所有 Agent 输出都进聊天室）

stream-json 已自动分离 text/thinking/tool_use。**text 进气泡，thinking 折叠，tool_use 渲染为审批卡片。**

| 谁 | 显示内容 | 样式 |
|---|---|---|
| Human | 用户消息 | 白色气泡，右对齐 |
| cici咪 | text 输出 | 蓝色左边框气泡 |
| coco咪 | text 输出 | 绿色左边框气泡 |
| soso咪 | text 输出 | 紫色左边框气泡 |
| 系统 | 状态通知 | 灰色居中 |

示例聊天室消息流：

```
Human: 开始 Phase 4b
cici咪: 分析 -> #11 #12 #13。#11 #12 并行，#13 等两者。
coco咪: [tool: Bash(git push)] -> [审批卡片]
coco咪: #12 完成。PR #20 已创建。
cici咪: #11 完成。检查任务表... 都 done。#13 派给 soso咪。
soso咪: Review 通过。16/16 tests passed。
cici咪: 全部完成。
```

### 4.3 附件/图片支持

CLI 支持传入文件路径和图片。前端聊天室支持：

- **文件附件**：拖拽/点击上传 -> 取本地绝对路径 -> Engine 传给 CLI
- **图片**：Claude CLI 支持 --images <path> 或 content block 的 type: "image"
- **实现参考**：Roundtable 的 buildClaudeContent() 处理 image/document/text 附件

### 4.4 UI 布局

```
+--------------------------------------------------------------+
|  TeamChat                                       + connected   |
+--------+-----------------------------------------------------+
| Agent  |               Chat Room (all agents)                |
|        |                                                     |
| cici咪 |  Human: Start Phase 4b                                |
|  idle  |  cici咪: Analyze -> #11 #12 #13                      |
|        |  coco咪: #12 done PR #20                             |
| coco咪 |  [Tool: git push origin]      [Allow] [Deny]        |
|  busy  |  soso咪: Review passed 16/16 tests                   |
|        |  cici咪: All done.                                    |
| soso咪 |                                                     |
|  idle  +-----------------------------------------------------+
|        |  @cici咪 ...                          [paperclip] [Send] |
+--------+-----------------------------------------------------+
```

参考风格：Roundtable（干净气泡 + 审批卡片 + Agent 侧边栏 + 附件按钮）。## 5. 授权（修正：审批卡片，不是 PTY y/n）

采用 Roundtable 同款方案：

```
CLI 输出: {"type":"control_request","request":{"subtype":"can_use_tool",...}}
     ↓
Engine: handleLine() → events.js 映射 → "approval.requested"
     ↓
前端: 聊天室 + 活动面板同时出现审批卡片
  ┌─────────────────────────────────┐
  │ 🔧 coco咪 请求使用工具           │
  │ Bash("git push origin feature") │
  │                                 │
  │ [允许] [拒绝]                    │
  └─────────────────────────────────┘
     ↓
人类点击 [允许]
     ↓
Engine → stdin:
  {"type":"control_response","response":{"subtype":"success","request_id":"...","response":{"behavior":"allow"}}}
     ↓
CLI 继续执行
```

---

## 6. 失败处理

```
同一任务失败:
  第 1 次 → Engine 自动重试（重新发送相同 prompt）
  第 2 次 → Engine 自动重试
  第 3 次 → Engine 不再重试，在聊天室通知人类:

  "⚠️ coco咪 执行 #12 失败 3 次。
   最后错误: <error excerpt>
   选项: [重试] [交给 cici咪 分析] [放弃]"

选项说明:
  [重试]       → 重新发送 prompt（第 4 次）
  [交给cici咪] → cici咪 看错误，决定修 prompt / 换 agent / 改方案
  [放弃]       → 标记 abandoned，从任务表移除。人类手动决策后续
```

---

## 7. 任务表 (Task Table)

cici咪 声明，Engine 存储和检查：

```json
{
  "tasks": [
    {
      "id": "11",
      "title": "CLI --continue 引擎改动",
      "agent": "cici咪",
      "status": "done",
      "depends_on": [],
      "output_summary": "实现了 --continue 模板..."
    },
    {
      "id": "12",
      "title": "ChatRoom 折叠区",
      "agent": "coco咪",
      "status": "done",
      "depends_on": [],
      "output_summary": "Task complete: Issue #12..."
    },
    {
      "id": "13",
      "title": "E2E 测试",
      "agent": "soso咪",
      "status": "blocked",
      "depends_on": ["11", "12"],
      "output_summary": null
    }
  ]
}
```

状态流转: `pending → running → done | failed | abandoned`

---

## 8. 与现有实现的差距

| 功能 | 现在 | ADR-003 v2 (Stream-JSON) |
|---|---|---|
| Agent 运行 | subprocess one-shot | spawn per message + --resume（不是长连接）✅ 已实测 |
| 正文提取 | JSON result 字段 only | **不需要提取** stream-json/JSONL 统一映射为 AgentEvent ✅ 已实测 |
| UI | 聊天室 only | 聊天室 + 审批卡片 + Agent 活动面板 |
| 任务编排 | 无 | Task Table + 依赖检查 |
| 授权 | 无 | 审批卡片 → Engine 写 control_response 到 stdin |
| 失败处理 | 无 | 3 次重试 → 3 选项 |
| 会话恢复 | --continue 模板 | `--resume <id>` / `--continue` |
| 结果排队 | 无 | 并行任务→排队→cici咪完成→一次性推送 |

---

## 9. 实施优先级

| Phase | 内容 | 依赖 |
|---|---|---|
| **C1** | Task Table 数据结构 + Engine API | 无 |
| **C2** | Runtime Manager（spawn CLI + JSONL parse + session resume）| C1 — ✅ 原型已写，待 review |
| **C3** | Event Mapper 完善（handle 会话重放、错误、超时）| C2 |
| **C4** | 前端 Agent 活动面板（结构化事件流）| C3 |
| **C5** | 审批卡片（仅 Claude）+ 聊天气泡混合显示 | C3 |
| **C6** | 结果排队 + 依赖检查 + 自动派发 | C1, C3 |
| **C7** | 失败处理（重试 + 三选项）| C1 |
| ~~C8~~ | ~~Codex/Cursor stream-json 实测~~ | ✅ 已完成 |

---

**状态:** ADR-003 v3 (confirmed CLI modes, session IDs, all-agent chat room)

---

## 10. 待讨论问题清单

以下问题来自人类对人肉路由流程的复盘，需要逐一确认后更新本文档。

### 10.1 Engine 边界

| # | 问题 | 状态 |
|---|---|---|
| Q1 | Engine 的定位是什么？ | ✅ Engine = 中间人（spawn CLI、解析事件、写 stdin、管理任务表）。决策在 cici咪 |
| Q2 | Engine 的边界？ | ✅ Engine 不做 AI 推理、不生成 prompt、不判断依赖。只做进程管理 + 事件映射 + 存储 |
| Q3 | cici咪 正文 → 任务表？ | ⏳ 方案：cici咪 用 `TASK:` 标签格式，Engine 解析。具体格式待实现阶段确认 |
| Q4 | Engine 如何把 prompt 喂给 agent？ | ✅ Claude: stdin JSON。Codex/Cursor: CLI args。已实测验证 |

### 10.2 Prompt 流转

| # | 问题 | 状态 |
|---|---|---|
| Q5 | Prompt 是 cici咪 写的吗？ | ✅ 是。就像你之前让我写 prompt 给 coco咪/soso咪，cici咪 生成 prompt → Engine 执行 |
| Q6 | Prompt 流转机制？ | ✅ Engine spawn CLI + stdin/CLI-args 传递。见 2.2 节 |
| Q7 | cici咪 的 `TASK:` 格式如何解析？| ⏳ 实现阶段确定。可参考 ADR-003 1.2 节格式 |

### 10.3 正文提取

| # | 问题 | 状态 |
|---|---|---|
| Q8-Q10 | 正文提取方案 | ✅ Runtime Manager 统一事件映射。不需要硬编码 |
| Q11 | `.teamchat/` 存储 | ✅ raw events 存 SQLite sessions 表。session ID 存 `.teamchat/session_{cli}.txt` |
| Q12 | prompt 写入 schema/JSON | ✅ Engine 直接构建 CLI 命令（args/stdin JSON），不需要中间文件 |

### 10.4 CLI 模式选择

| # | 问题 | 状态 |
|---|---|---|
| Q13-Q15 | PTY vs stream-json | ✅ 全部回答。选 stream-json。不需要 xterm.js |

### 10.5 审批/授权

| # | 问题 | 状态 |
|---|---|---|
| Q16-Q17 | 审批方案 | ✅ Claude: 审批卡片。Codex/Cursor: 接受自动执行。见 2.4 节 |

### 10.6 调度细节

| # | 问题 | 状态 |
|---|---|---|
| Q18-Q20 | 调度细节 | ⏳ 实现阶段处理。1.2 节流程为基础，边界情况边做边补 |

---

## 11. 参考资料: Roundtable

https://github.com/wenwen-0617/roundtable

### 架构摘要

Roundtable 是本地圆桌聊天应用，让 Codex 和 Claude Code 在聊天室中协作。

**核心实现（与我们设计相关的部分）：**

```
用户浏览器 ↔ HTTP/WebSocket ↔ Roundtable Server
                                    │
                        ┌───────────┼───────────┐
                        │           │           │
                   RuntimeHub   SQLite DB   Summary/Checkin
                        │
            ┌───────────┴───────────┐
            │                       │
    Codex Runtime Adapter    Claude Code Runtime Adapter
            │                       │
    child_process.spawn()    child_process.spawn()
    (pipe, NOT ptY)          (pipe, NOT pty)
```

**关键设计：**

1. **非 PTY，用 pipe** — `spawn("claude", args, { stdio: ["pipe","pipe","pipe"] })`，读取 stdout 每一行

2. **事件映射层** — `events.js` 将 CLI 行输出映射为结构化事件：
   - `runtime.approval.requested` → 前端审批卡片
   - `runtime.turn.completed` → 任务完成
   - `runtime.message` → 聊天气泡

3. **审批流程** — CLI 输出 "Run git push?" → events.js 映射为 approval 事件 → 存入 `pendingApprovals` → 前端渲染审批卡片 → 人类点击允许/拒绝 → `sendResponse(requestId, decision)` → Engine 向 CLI stdin 写入 y/n

4. **会话恢复** — `claude -c` 恢复上次会话，session 绑定存储在 SQLite

5. **UI 分离** — 聊天区显示干净的消息和审批卡片；完整 CLI 输出可通过其他方式查看

### 对 TeamChat 的启示

- **不需要 PTY** — 用 pipe + 事件映射可以达到同样效果，且正文提取天然结构化
- **审批卡片** — 不需要人类在终端按 y/n，可以做成前端交互
- **Runtime Adapter 模式** — 每种 CLI 一个 adapter，负责启动、通信、事件映射
- **SQLite 存储一切** — 消息、审批、session、摘要都存 SQLite



---

## 12. Current Session IDs (2026-07-09)

| Agent | CLI | Session ID | Resume Command |
|---|---|---|---|
| cici咪 | Claude | `5fbaf844-4cbc-48b2-9242-7902d098bd81` | `claude --resume <id>` |
| coco咪 | Codex | `019f40ef-e8cf-76f0-8b49-6691cc7275f3` | `codex resume <id>` |
| soso咪 | Cursor | `04e64d6d-de38-4861-a7ce-87c26d28d77f` | `cursor-agent --resume=<id>` |

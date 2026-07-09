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

### 1.1 会话管理

```bash
# 人类开三个终端，分别 cd 到 TeamChat 目录:
#   终端1: claude              ← cici咪 交互式会话
#   终端2: codex               ← coco咪 交互式会话
#   终端3: cursor-agent        ← soso咪 交互式会话

# 如果之前在该目录启动过，恢复上次会话:
#   终端1: claude -c           ← 继续 cici咪 上次会话
#   终端2: codex exec resume --last  ← 继续 coco咪 上次会话
#   终端3: cursor-agent --continue   ← 继续 soso咪 上次会话
```

**Engine 需要做的：** 维护目录级的会话标记（`.teamchat/sessions/` 下记录每个 agent 是否已有会话）。有则恢复，无则冷启动。

```
启动逻辑:
  if .teamchat/sessions/{agent}_session_exists:
      cmd = 恢复命令 (claude -c / codex exec resume --last / cursor-agent --continue)
  else:
      cmd = 冷启动 (claude / codex / cursor-agent)
      touch .teamchat/sessions/{agent}_session_exists
```

### 1.2 协作流程（完整版）

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

## 2. 会话：不是 One-Shot，是 PTY

### 2.1 冷启动 vs 恢复

```
Engine 启动时:
  for each agent in [cici, coco, soso]:
    session_file = .teamchat/sessions/{agent}_active
    if session_file exists:
      → 使用恢复命令启动 PTY
      → log: "{agent} 恢复上次会话"
    else:
      → 使用冷启动命令启动 PTY
      → touch session_file
      → log: "{agent} 冷启动新会话"
```

冷启动命令:
- cici咪: `claude`
- coco咪: `codex`
- soso咪: `cursor-agent`

恢复命令:
- cici咪: `claude -c`
- coco咪: `codex exec resume --last`
- soso咪: `cursor-agent --continue`

### 2.2 Stream-JSON 通信（参考 Roundtable）

**重大发现：Claude CLI 支持 `--output-format stream-json --input-format stream-json --permission-prompt-tool stdio`**
Cursor 也支持 `--output-format stream-json`。Codex 有 `--json` (JSONL) 标志。

这意味着**不需要 PTY**。CLI 作为 headless 子进程运行，stdin/stdout 全是结构化 JSON：

```
Engine 启动 CLI:
  spawn("claude", [
    "--print",
    "--output-format", "stream-json",   // stdout: 每行一个 JSON 事件
    "--input-format", "stream-json",     // stdin:  每行一个 JSON 指令
    "--permission-prompt-tool", "stdio", // 权限通过 stdio 流
    "--resume", sessionId,               // 恢复会话
  ])

Engine → CLI (stdin):
  {"type":"user","message":{"role":"user","content":"实现 XX"}}

CLI → Engine (stdout, 每行 JSON):
  {"type":"assistant","message":{"content":[
    {"type":"thinking","thinking":"需要先分析..."},   → 💭 思考（折叠）
    {"type":"text","text":"好的，我来实现..."},       → 💬 正文（气泡）
    {"type":"tool_use","name":"Bash","input":{...}}  → 🔧 工具（审批卡）
  ]}}

Engine → CLI (stdin, 审批回复):
  {"type":"control_response","response":{
    "subtype":"success","request_id":"xxx",
    "response":{"behavior":"allow"}
  }}
```

**Codex CLI: 有待验证 `--json` 输出格式。需要实测启动后 stdout 的 JSON 事件结构。**
**Cursor CLI: 支持 `--output-format stream-json` + `--continue`/`--resume`。**

### 2.3 冷启动 vs 恢复

```
Engine 启动时:
  for each agent:
    session_file = .teamchat/sessions/{agent}_active
    if session_file exists:
      → 使用 --resume / --continue 标志
    else:
      → 不带 session 标志冷启动
      → touch session_file
```

启动命令:
- cici咪: `claude --print --output-format stream-json --input-format stream-json --permission-prompt-tool stdio [--resume <id>]`
- coco咪: `codex exec --json [...]`（待验证）
- soso咪: `cursor-agent --print --output-format stream-json [--continue]`

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

### 4.2 聊天室显示

| 内容 | 显示为 |
|---|---|
| 人类消息 | 白色气泡，右对齐 |
| cici咪 text 回复 | 聊天气泡（蓝色边框），干净正文 |
| coco咪/soso咪 text 回复 | 聊天气泡（绿/紫边框），附带 [#XX] Issue 链接 |
| 系统通知 | 灰色居中（"#12 完成"、"#13 已派发"） |
| 审批请求 | 审批卡片，带 [允许] [拒绝] 按钮 |

### 4.3 Agent 活动面板（替代终端）

不是一个真实终端，而是**选定 agent 的结构化事件流**：

- 💭 thinking → 灰色折叠区，点击展开
- 🔧 tool_use → 审批卡片，实时更新 status
- 💬 text → 干净气泡
- ✅ turn complete → 耗时、token 用量
- ❌ error → 红色提示

**相比传统终端：更干净、更可读、不需要人眼自己区分正文。**

---

## 5. 授权（修正：审批卡片，不是 PTY y/n）

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
| Agent 运行 | subprocess one-shot | spawn + stream-json 持久会话 |
| 正文提取 | JSON result 字段 only | **不需要提取** stream-json 自带 text/thinking/tool_use |
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
| **C2** | Stream-JSON Runtime Manager（spawn + JSONL 解析）| C1 |
| **C3** | Event Mapper（类似 roundtable events.js）| C2 |
| **C4** | 前端 Agent 活动面板（结构化事件流）| C3 |
| **C5** | 审批卡片 + 聊天气泡混合显示 | C3 |
| **C6** | 结果排队 + 依赖检查 + 自动派发 | C1, C3 |
| **C7** | 失败处理（重试 + 三选项）| C1 |
| **C8** | Codex / Cursor stream-json 实测 + adapter | C2 |

---

**状态:** 等待审查

---

## 10. 待讨论问题清单

以下问题来自人类对人肉路由流程的复盘，需要逐一确认后更新本文档。

### 10.1 Engine 边界

| # | 问题 | 状态 |
|---|---|---|
| Q1 | Engine 的定位是什么？是否只是中间人（不决策）？ | 待讨论 |
| Q2 | Engine 的边界在哪里？哪些事归 Engine，哪些归 cici咪？ | 待讨论 |
| Q3 | cici咪 的正文如何被 Engine 解析为结构化任务表？是否有 TASK: 标签格式？ | 待讨论 |
| Q4 | Engine 如何从 cici咪 的回复中提取 prompt，再写入对应 agent 的 CLI？ | 待讨论 |

### 10.2 Prompt 流转

| # | 问题 | 状态 |
|---|---|---|
| Q5 | 派发任务时，prompt 是 cici咪 写的吗？还是 Engine 根据任务表自动生成？ | 待讨论 |
| Q6 | Prompt 如何在 Engine 和 PTY 之间流转？具体机制是什么？ | 待讨论 |
| Q7 | 如果 cici咪 在回复中写了 `TASK:#12:agent=coco咪:...`，Engine 怎么解析这个格式？ | 待讨论 |

### 10.3 正文提取

| # | 问题 | 状态 |
|---|---|---|
| Q8 | 如何统一提取正文？ | ✅ **已回答** — stream-json 自带 text/thinking/tool_use 分离，不需要提取 |
| Q9 | "找 Task complete:" 硬编码行不通 | ✅ **已回答** — 不需要硬编码，stream-json 事件已结构化 |
| Q10 | 先搭建平台再决定提取策略？ | ✅ **已回答** — 对 Claude 和 Cursor 已有 stream-json，对 Codex 需要实测 --json |
| Q11 | `.teamchat/` 存 transcript 还是 JSON？ | ⏳ 待确认 — stream-json 的 raw events 存 SQLite 或 JSONL 文件，供回放 |
| Q12 | prompt 写入 schema/JSON，Engine 读出来喂给咪？ | ⏳ 待确认 — cici咪 的 prompt 写入任务表，Engine 构建 JSON-RPC 写入 agent stdin |

### 10.4 CLI 模式选择

| # | 问题 | 状态 |
|---|---|---|
| Q13 | PTY vs Pipe + 事件映射？ | ✅ **已回答** — 选 stream-json pipe 方案（参考 roundtable）。Claude 和 Cursor 原生支持 |
| Q14 | 是否借鉴 roundtable？ | ✅ **已回答** — 借鉴。核心改动：用 `--output-format stream-json --input-format stream-json --permission-prompt-tool stdio` |
| Q15 | 不需要终端面板了？ | ✅ **已回答** — 不需要 xterm.js。改为 Agent 活动面板（结构化事件流）|

### 10.5 审批/授权

| # | 问题 | 状态 |
|---|---|---|
| Q16 | roundtable 审批方案是否采用？ | ✅ **已回答** — 采用。CLI 发 control_request → Engine 映射 → 前端审批卡片 → 人类点击 → Engine 写 control_response 到 stdin |
| Q17 | 不用 PTY 后，还能按 y/n 吗？ | ✅ **已回答** — 不能也不需要在终端按 y/n。改为前端点击 [允许][拒绝] 按钮 |

### 10.6 调度细节

| # | 问题 | 状态 |
|---|---|---|
| Q18 | 1.2 节的流程是否足够详细？人类实际操作中还有哪些边界情况？ | 待讨论 |
| Q19 | coco咪 先完成时，如果 cici咪 还在跑，coco咪 的输出排队。但如果 cici咪 跑了一个小时，人类能看到 coco咪 的输出吗？ | 待讨论 |
| Q20 | 三个 agent 同时在 chat 里说话时，消息顺序如何保证？ | 待讨论 |

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


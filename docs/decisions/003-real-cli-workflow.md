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

### 2.2 PTY 通信

Engine 通过 PTY (pseudo-terminal) 管理每个 agent 的 stdin/stdout：

```
Engine → PTY.stdin: prompt + \n   （模仿人类粘贴）
PTY.stdout → Engine: 实时输出     （完整 CLI 输出）
PTY.stdout → 前端: WebSocket 推送  （终端面板渲染）
```

Engine 同时监听 stdout，缓冲全部输出，在检测到 agent 完成时触发正文提取。

---

## 3. 正文提取 (Output Extractor)

### 3.1 问题

Agent CLI 输出包含：思考、工具调用、代码变更、文件列表... 几百行。人类只复制最后的"正文总结"（如 "Task complete: Issue #12 — ..."）给 cici咪。

### 3.2 策略

```
Claude CLI (--output-format json):
  → JSON 解析 → result 字段

Codex CLI (纯文本):
  → 找 "Task complete:" 标记 → 从该行开始取到末尾
  → fallback: 取倒数 30% 的内容

Cursor CLI (纯文本):
  → 同 Codex 逻辑
  → 找 "完成情况" / "Task complete" 标记

通用 fallback:
  → 取最后 500 行中非空行的最后一段连续文本
```

### 3.3 正文用途

- Agent 间转发（coco咪 的正文 → cici咪 做决策）
- 未来可选：聊天室消息（干净的气泡内容）
- Agent 自身终端面板：始终显示完整输出

---

## 4. UI 设计

### 4.1 布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 TeamChat                                              🟢 已连接  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────┐  ┌──────────────────────────────┐  │
│  │        📌 聊天室             │  │  cici咪 终端                   │  │
│  │                             │  │  $ claude -c                  │  │
│  │  🧑: 开始 Phase 4b          │  │  > 我来分析一下...            │  │
│  │  🏗️: 拆成 #11 #12 #13       │  │  ...                          │  │
│  │  🏗️: #11 #12 并行, #13 等待  │  │  ✅ Task complete             │  │
│  │  ⚡: #12 完成 ✅             │  │                                │  │
│  │  🏗️: 收到两个结果，派发 #13  │  └──────────────────────────────┘  │
│  │  🔍: #13 Review 通过 ✅      │  ┌──────────────────────────────┐  │
│  │                             │  │  coco咪 终端                   │  │
│  ├─────────────────────────────┤  │  $ codex                      │  │
│  │ 💬 @cici咪 ...      [发送]  │  │  > 开始实现前端...            │  │
│  └─────────────────────────────┘  │  ...                          │  │
│                                   │  ✅ Task complete: Issue #12  │  │
│  ┌──────────────────────────────┐ │                                │  │
│  │  soso咪 终端                   │ └──────────────────────────────┘  │
│  │  $ cursor-agent               │                                    │
│  │  > 开始写 E2E 测试...          │                                    │
│  │  ...                           │                                    │
│  │  ✅ 16/16 tests passed         │                                    │
│  └──────────────────────────────┘                                     │
└──────────────────────────────────────────────────────────────────────┘
```

**左：聊天室**（人类 ↔ cici咪 对话，简洁）  
**右三行：三个终端面板**（同时显示，各自可滚动）

### 4.2 聊天室的内容

聊天室显示：
- 人类消息
- cici咪 的回复（正文内容，干净的）
- 系统消息（"#12 完成"、"#13 已派发给 soso咪"）

**不显示** coco咪/soso咪 的回复到聊天室（MVP 先不做）。未来正文提取成熟后，可加入：
```
⚡ coco咪: ✅ #12 完成 — PR #20 已创建，等待 review
🔍 soso咪: ✅ #13 完成 — 16/16 tests passed
```

### 4.3 终端面板

用 **xterm.js** 渲染。每个 agent 一个面板。人类可以：
- 看到完整 CLI 输出（包括思考、工具、代码）
- 滚动翻页查看历史
- 在需要授权时按 `y` + Enter
- 直接在终端里执行脚本

---

## 5. 授权

**MVP 方案：终端面板直接授权。** 不在聊天室加按钮。

```
Agent PTY 输出: "Run git push? [y/n]"
     ↓
终端面板显示这一行
     ↓
人类在该面板输入 y + Enter
     ↓
Engine 转发 y 到 PTY.stdin
     ↓
Agent 继续执行
```

不做聊天按钮的原因：终端面板是 PTY 直连，人类按 y 就行，不需要额外的后端路由。

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

| 功能 | 现在 | ADR-003 |
|---|---|---|
| Agent 运行 | subprocess one-shot | PTY 持久会话 |
| 正文提取 | JSON result 字段 only | 多格式提取器 (Claude/Codex/Cursor) |
| UI | 聊天室 only | 聊天室 + 3 个终端面板同时显示 |
| 任务编排 | 无 | Task Table + 依赖检查 |
| 授权 | 无 | PTY 终端直连，人类按 y/n |
| 失败处理 | 无 | 3 次重试 → 3 选项 |
| 会话恢复 | --continue 模板 | 目录级 session 标记 + 冷/热启动 |
| 结果排队 | 无 | 并行任务→排队→cici咪完成→一次性推送 |

---

## 9. 实施优先级

| Phase | 内容 | 依赖 |
|---|---|---|
| **C1** | Task Table 数据结构 + Engine API | 无 |
| **C2** | PTY Session Manager（冷/热启动 + stdin/stdout）| C1 |
| **C3** | Output Extractor（多格式正文提取）| C1 |
| **C4** | 终端面板前端 (xterm.js × 3) | C2 |
| **C5** | 结果排队 + 依赖检查 + 自动派发 | C1, C3 |
| **C6** | 失败处理（重试 + 三选项）| C1 |
| **C7** | 完整集成测试 | C1-C6 |

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
| Q8 | 每个 CLI 的输出格式不同（Claude JSON、Codex 纯文本、Cursor 纯文本），如何统一提取正文？ | 待讨论 |
| Q9 | "找 Task complete: 标记" 这种硬编码行不通。有什么更好的方案？ | 待讨论 |
| Q10 | 是否先搭建平台，实际跑几次，看后台收到什么内容，再决定提取策略？ | 待讨论 |
| Q11 | `.teamchat/` 如何存放每个 agent 的回复？用 transcript？还是 schema/JSON？ | 待讨论 |
| Q12 | cici咪 要和其他咪协作时，是否把 prompt 写入 schema/JSON 文件，Engine 再读出来结构化喂给对应咪？ | 待讨论 |

### 10.4 CLI 模式选择

| # | 问题 | 状态 |
|---|---|---|
| Q13 | PTY 模式 vs Pipe + 事件映射（roundtable 方案），选哪个？ | 待讨论 |
| Q14 | roundtable 用 `spawn` + `pipe` + 事件映射做到了干净聊天 + 审批卡片。TeamChat 要不要借鉴？ | 待讨论 |
| Q15 | 如果借鉴 roundtable 的 pipe 方案，三个终端面板还需要吗？还是换成事件卡片？ | 待讨论 |

### 10.5 审批/授权

| # | 问题 | 状态 |
|---|---|---|
| Q16 | roundtable 的审批是 CLI 输出 → 事件映射 → 前端渲染审批卡片 → 人类点击 → Engine 回复 y 给 CLI。TeamChat 是否采用同样方案？ | 待讨论 |
| Q17 | 如果不用 PTY，人类还能在终端里按 y/n 吗？还是全部改成前端点击卡片？ | 待讨论 |

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


#!/usr/bin/env python3
"""Update ADR-003 with session IDs, all-agent chat room, attachment support."""
import re

adr_path = "docs/decisions/003-real-cli-workflow.md"

with open(adr_path, "r") as f:
    content = f.read()

# 1. Replace session section
old_session = re.search(r'### 1\.1 会话管理.*?(?=### 1\.2)', content, re.DOTALL)
if old_session:
    new_session = """### 1.1 会话管理（/exit 方式）

**核心：每次人类消息 spawn 一个新的 CLI 进程，带 --resume <sessionId> 恢复上下文。不是长连接，是"spawn per message"。**

**会话 ID 获取（/exit 命令，不用目录扫描）：**

```
首次启动:
  1. Engine spawn CLI（冷启动，不带 --resume）
  2. Engine 往 stdin 写 "/exit\\n"
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

**存储路径:** `.teamchat/session_{claude,codex,cursor}.txt`

"""
    content = old_session.re.sub(new_session.strip(), content, count=1)

# 2. Replace chat room sections (4.2 + 4.3)
old_chat = re.search(r'### 4\.2 聊天室.*?(?=## 5\. )', content, re.DOTALL)
if old_chat:
    new_chat = """### 4.2 聊天室内容（所有 Agent 输出都进聊天室）

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

参考风格：Roundtable（干净气泡 + 审批卡片 + Agent 侧边栏 + 附件按钮）。

"""
    content = old_chat.re.sub(new_chat.strip(), content, count=1)

# 3. Update status
content = content.replace("**状态:** 等待审查", "**状态:** ADR-003 v3 (confirmed CLI modes, session IDs, all-agent chat room)")

# 4. Add session ID reference at bottom
content += """

---

## 12. Current Session IDs (2026-07-09)

| Agent | CLI | Session ID | Resume Command |
|---|---|---|---|
| cici咪 | Claude | `5fbaf844-4cbc-48b2-9242-7902d098bd81` | `claude --resume <id>` |
| coco咪 | Codex | `019f40ef-e8cf-76f0-8b49-6691cc7275f3` | `codex resume <id>` |
| soso咪 | Cursor | `04e64d6d-de38-4861-a7ce-87c26d28d77f` | `cursor-agent --resume=<id>` |
"""

with open(adr_path, "w") as f:
    f.write(content)

print("ADR-003 updated successfully!")
print(f"Length: {len(content)} chars")

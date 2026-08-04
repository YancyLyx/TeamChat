# 03. 核心技术点（完整证据链）

> 每个点独立成篇：问题 → 方案 → 取舍 → 数据 → 失败/改进。面试官只问一个点，读这一段就能答。

---

## 3.1 CLI 进程驱动（stream-json）

**一句话** — 用结构化 JSON 流驱动三个 AI CLI，替代交互式伪终端。

**问题** — 要让三个 CLI 自动化，需要：① 程序化发送 prompt ② 解析输出 ③ 处理审批。交互式 PTY 的输出是混杂文本，无法可靠解析。

**方案** — 三个 CLI 全部用非交互 JSON 模式：
```
claude --print --output-format stream-json --verbose
codex exec --json
agent --print --output-format stream-json   (注意: 不是 cursor-agent)
```
每行 stdout 是一个 JSON 事件，`text`/`thinking`/`tool_use`/`result` 天然分离。用 `asyncio.subprocess` spawn，逐行读。

**取舍** — 备选是 PTY（伪终端模拟真人）。PTY 能"假装真人"但输出解析全靠正则，审批只能模拟按键。stream-json 是 CLI 官方支持的结构化接口，解析可靠、审批是结构化事件。代价：需要为三个 CLI 写三个解析 adapter。

**数据** — 三个 CLI 全部实测：Claude 第一行 system 事件含 session_id；Codex 是 `thread.started`；Cursor 是 `system` 事件。每条回复解析为 text（干净气泡）+ thinking（折叠）+ tool_use（审批卡）。

**失败/改进** — ① Cursor 命令名写错成 `cursor-agent`，报 "No Cursor IDE installation found"，实测发现真实命令是 `agent`。② Cursor 输出 `assistant` 和 `result` 事件含相同文本，导致回复重复，加内容去重。③ `--output-format stream-json` 必须配 `--verbose`，否则报错，实测确认。

---

## 3.2 会话管理（session ID 绑定）

**一句话** — 每次 spawn 带 `--resume <id>` 延续 agent 上下文，实现多会话隔离。

**问题** — CLI 的上下文绑定在 session ID 上。要让 agent 记住之前的对话（比如 cici咪 记得我们讨论过什么），必须拿到并复用 session ID。

**方案** — 冷启动时第一次 spawn 不发 prompt 也能从第一行 JSON 拿到 session_id，存到数据库；后续 spawn 带 `--resume <id>`。每个前端会话（TeamChat session）绑定三只咪各自的 CLI session ID。

**取舍** — 备选方案是"长连接常驻进程"（进程一直开着）。放弃原因：① CLI 进程可能僵死 ② 资源占用 ③ 崩溃恢复难。spawn-per-message + `--resume` 让每次调用是独立的，失败不影响下次。

**数据** — 实测三个 CLI 第一行 JSON 都包含 ID（Claude `session_id`、Codex `thread_id`、Cursor `session_id`）。多会话测试：Test 会话的三只咪 ID 与默认会话不同，隔离有效。

**失败/改进** — ① 目录扫描发现 session 不可靠（会扫到别的项目的），改为冷启动捕获。② Cursor 冷启动捕获不到 ID，排查发现是命令没带 `--print` 导致输出非 JSON，修复后捕获成功。

---

## 3.3 MCP Server 任务编排

**一句话** — 给 cici咪 提供 MCP 工具（create_task 等），让她通过工具调用管理任务表，而不是让 Engine 解析自然语言。

**问题** — 人类提需求后，需要 cici咪 拆任务、写 prompt、指派。方案 A：让 cici咪 输出 `TASK:...` 文本让 Engine 解析——不可靠，表述稍变就解析失败。方案 B：给 cici咪 提供结构化工具。

**方案** — 实现 MCP Server（JSON-RPC over stdio），Claude CLI 通过 `.mcp.json` 自动发现并启动。提供 4 个工具：`create_task`（含 prompt 字段）、`update_task`、`list_tasks`、`get_task`。cici咪 在对话中直接调用 `mcp__teamchat__create_task(agent, title, prompt, depends_on)`。

**取舍** — 备选是 Skill（prompt 注入）——Skill 只能注入文本不能执行 CRUD。MCP 工具是真正的函数调用，100% 可靠，且 Claude CLI 原生支持。代价：MCP 是进程外协议，调试稍复杂。

**数据** — MCP Server 9 个单元测试 + stdio 子进程测试通过。实测 cici咪 成功创建 6 个任务（重复是 MCP 断连重试导致）。

**失败/改进** — ① `--mcp-config` 参数位置错误导致 prompt 被当作路径，改用 `.mcp.json` 自动发现。② MCP Server 缺 `cwd` 导致模块找不到，加 `cwd` 修复。

---

## 3.4 审批流（control_request）

**一句话** — Claude 请求工具权限时，前端弹审批卡，人类点允许/拒绝，Engine 写回 Claude stdin。

**问题** — Claude 用 `--permission-prompt-tool stdio` 时，需要工具权限会输出 `control_request` 事件并等待 stdin 响应。`process.communicate()` 一次性读完 stdout，无法中途暂停等人类。

**方案** — Claude 路径改为逐行读 stdout：遇到 `control_request` → `register_approval()` 存 (stdin, asyncio.Event) → 广播审批卡到前端 → `await event.wait()` 暂停 → 人类点按钮 → `POST /api/approval` 写 control_response 到 stdin + `event.set()` → 继续读。

**取舍** — 备选 `--permission-mode acceptEdits`（自动批准）。放弃：安全工具自动放行没问题，但 MCP 工具也被自动批准，失去了人类审核环节。保留人工审批更符合"AI 是协作者，人负责"的原则。

**数据** — 12 个测试覆盖：allow/deny/404（找不到请求）/422（非法 decision）/重复提交。

**失败/改进** — 严重 bug：runner 和 API 各建了一个 Event，API set 的是注册表里的，runner 等的是自己的 → 死锁卡 120s。soso咪 review 发现，改用 `register_approval()` 的返回值统一等待。

---

## 3.5 数据库设计

**一句话** — 单文件 SQLite 三表，FK 隔离会话数据。

**问题** — 早期设计三个独立 db 文件（sessions.db/tasks.db/teamchat.db），无法 JOIN、三个连接、WAL 文件混乱。

**方案** — 合并为一个 `teamchat.db`：`teamchat_sessions`（前端会话）+ `agent_calls`（CLI 调用日志）+ `task_table`（任务编排）。所有动态表带 `teamchat_session_id` FK。

**取舍** — JSON 文件存储（备选）：不支持并发写、查询要全量加载。SQLite 单文件零依赖、支持 SQL 聚合（Stats L1/L2/L3 全靠它）。

**数据** — 三表结构 + 索引设计写入 ADR-003 §10。stats 通过 SQL 聚合：成功率、平均耗时、token 总量、tool calls 次数。

**失败/改进** — ① 数据库文件误提交进 git（.gitignore 缺失），`git rm --cached` + 加 `.gitignore`。② 合并冲突时 DB 被删重建，会话丢失——教训：DB 不进 git，重建时自动种子默认会话。

---

## 3.6 多 agent 并行调度

**一句话** — 打招呼等场景用 `asyncio.gather` 并行调用三只咪，各自完成后独立推送。

**问题** — 最初串行 for 循环调三只咪，一只等一只，总耗时 = 三倍单次耗时。

**方案** — `asyncio.gather(greet_one(cici), greet_one(coco), greet_one(soso))`，每只咪独立 spawn + 独立广播。

**取舍** — 备选线程池：GIL 下无意义，asyncio 是 IO-bound 的正确选择。

**数据** — 串行 ~30s（每只咪 6-10s）→ 并行 ~10s（取最慢）。

**失败/改进** — 并行后三条消息同一毫秒到达，前端 `Date.now()` 去重把其中一条当重复丢弃。改用"内容 + agent + 3s 窗口"去重。

---

## 3.7 AI 输出验证（QA 流程）

**一句话** — 三只咪协作 + 强制 review，AI 产出的每一行代码都经过独立审查。

**问题** — AI 写代码快但会犯错，且错误隐蔽（死锁、XSS、逻辑错位）。如何保证质量？

**方案** — 铁律：**没有 soso咪 review 的 PR 不能合并**。soso咪 独立审查每个 PR，发现问题直接修 + 补测试。

**数据** — soso咪 累计审查 90+ PR，发现的关键 bug：
- MCP 审批双 Event 死锁
- Markdown XSS（未转义 HTML、可绕过的 sanitize）
- Stats L3 硬编码占位数据
- SQL 列索引错位（status 当 depends_on）
- 并行消息去重丢失

**取舍** — 备选"自己 review 自己"：不可靠，AI 会重复同样错误。独立 agent 审查 + 测试 + E2E 三层验证。

**失败/改进** — 早期我跳过 review 直接合并过多次 PR，被用户纠正。从此铁律写入 CLAUDE.md + START-HERE.md，且**我不再执行 `gh pr merge`，合并由人类执行**。

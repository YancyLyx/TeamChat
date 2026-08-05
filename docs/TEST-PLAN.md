# TeamChat 测试计划

> 来源：任务 #7 输出的测试点清单（A. 引擎配置与 CLI 封装 / B. 消息解析与 `/api/chat` 路由 / C. Runner 与事件解析 / D. 会话与数据持久化 / E. 任务表、DAG、MCP / F. Task Scheduler、Result Relay、失败重试 / G. REST API、WebSocket、审批、GitHub / H. Dashboard 前端）。

## 1. 测试范围

### 范围内

| 模块 | 测试对象 |
|---|---|
| 引擎层 | `engine/config.py`、`runner.py`、`runtime.py`、`message_parser.py`、`router.py`、`bus.py`、`store.py`、`session_store.py`、`task_table.py`、`task_planner.py`、`mcp_server.py`、`task_scheduler.py`、`result_relay.py`、`orchestrator.py`、`github_adapter.py`、`github_client.py` |
| API 层 | `/api/chat`、`/api/tasks`、`/api/sessions`、`/api/session-manager`、`/api/agents`、`/api/stats`、`/api/engine`、`/api/approval`、`/api/upload`、`/api/github/webhook`、WebSocket `/ws` |
| 前端 | Dashboard 壳、ChatRoom、ChatInput、ChatMessage、ApprovalCard、AgentCard、SessionManager、StatsPanel、LivePanel、`useWebSocket`、markdown/unicode/metrics 工具 |

### 范围外

- 真实 GitHub push / PR / merge / webhook 联调（当前 GitHub 账号暂停，使用 mock 或单元级验证）。
- Tasks 看板 Tab 已接入（2026-08-03，设计见 ADR-004）。
- 真实 CLI 长任务或高成本 AI 调用，仅作为可选的 smoke 测试。

## 2. 测试策略

1. **单元测试**：使用临时 `project_root` 和 mock 依赖，验证 parser、task table、DAG、Router、MCP、Scheduler、Result Relay、store 的确定性行为。
2. **API 测试**：使用 FastAPI TestClient 或本地 uvicorn 验证 REST 响应、状态码、错误处理、session 隔离与 WebSocket 消息。
3. **前端 E2E**：使用 Playwright + mock AgentRunner，覆盖聊天、历史、刷新、断线重连、审批卡片、Session Manager、Stats/Live 面板。
4. **真实 CLI Smoke**：仅在 CLI 可用且环境变量就绪时执行，不默认跑完整 AI 流程，避免成本和不可控性。
5. **数据隔离**：每个测试使用独立临时数据库或独立 `teamchat_session_id`；测试日志使用 `tag=test`，确认不会污染 `tag=prod` 历史。
6. **回归原则**：每个修复先复现问题，再补充对应测试；P0/P1 测试全绿后进入后续任务。

## 3. 测试点清单

### A. 引擎配置与 CLI 封装

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-A1 | 加载 Agent 身份、角色、CLI、Git 身份、token 环境变量 | 三个 agent 配置完整且名称/CLI 映射正确 |
| TC-A2 | 冷启动、continue、resume 三种 CLI 命令构建 | Claude/Codex/Cursor 参数格式正确，session id 按需注入 |
| TC-A3 | 子进程环境变量 | 只注入当前 agent 的 GitHub token 和 Git 身份，兄弟 agent token 被剥离 |
| TC-A4 | CLI 缺失与超时 | CLI 缺失报错；超时后返回 `exit_code=-1` 和 `TIMEOUT` 信息 |

### B. 消息解析与 `/api/chat` 路由

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-B1 | 空消息 | 返回 400，不产生聊天记录或 agent 调用 |
| TC-B2 | 单个 `@mention` | 只派发目标 agent，@名字被清理，人类消息按 session 持久化 |
| TC-B3 | 多个 `@mention` | 返回广播/多目标响应，不直接 spawn 单个 agent |
| TC-B4 | 无 `@mention` | cici咪 分析，聊天室广播分析结果，新建任务由 Scheduler 自动派发 |
| TC-B5 | 问候语广播 | 空闲的三个 agent 并行回复；busy agent 跳过，不发生并发 spawn |
| TC-B6 | busy 排队 | 目标 agent 或 cici咪 忙时转为 task 排队并广播提示，不重复 spawn |

### C. Runner 与事件解析

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-C1 | Claude stream-json | 正确提取 text、MCP tool_use、token usage；control_request 进入审批 |
| TC-C2 | Codex JSONL | 只展示 agent_message，过滤 reasoning/command_execution，token usage 正确 |
| TC-C3 | Cursor stream-json | assistant text 与 result 正确提取 |
| TC-C4 | 非 JSON 输出 | 作为纯文本保留 |
| TC-C5 | 冷启动与续会话 | 首次捕获并保存 CLI session id；后续使用 resume 或 continue |

### D. 会话与数据持久化

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-D1 | 数据库初始化 | `teamchat.db` 创建三张表并 seed 默认会话 |
| TC-D2 | 会话管理 CRUD | 创建、列表、查询、改名、删除正确；创建校验目录存在 |
| TC-D3 | agent_calls 日志 | prompt/output/exit_code/耗时/token/tool_calls/tag/session/起止时间完整 |
| TC-D4 | 查询隔离 | `/api/sessions`、`/api/stats` 按 agent、tag、session 过滤，prod/test 不串数据 |

### E. 任务表、DAG、MCP

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-E1 | 任务 CRUD 与状态流转 | pending/running/done/failed 正确，起止时间自动写入 |
| TC-E2 | 依赖调度 | 无依赖或依赖 done 可执行；缺失/失败/废弃依赖保持阻塞 |
| TC-E3 | DAG 校验 | 能识别循环依赖、孤儿依赖、失败阻塞 |
| TC-E4 | 任务树 | `task_tree` 返回根任务及后代，深度安全截断 |
| TC-E5 | MCP 协议 | initialize、tools/list、6 个工具、错误码、stdio 输出正常 |
| TC-E6 | MCP 任务 session 修正 | chat/scheduler/result relay 新任务修正到实际 session，不留在默认 session 1 |

### F. Task Scheduler、Result Relay、失败重试

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-F1 | 自动派发 | 轮询 unblocked tasks，仅派发空闲 agent，不双 spawn |
| TC-F2 | Engine 边界 | 派发后标记 running 并移交审核，Engine 不自行标记 done/failed |
| TC-F3 | 异常任务 | 未知 agent 标记 failed；spawn 异常构造失败结果并回流 |
| TC-F4 | 自动重试 | 最多 1 次原执行 + 3 次重试，指数退避，重试写审计 |
| TC-F5 | 结果回流 | cici咪 忙时排队，空闲时批量审核；cici咪 自身结果不回流 |
| TC-F6 | 审核可靠性 | 审核失败重新入队；prompt 包含输出、exit_code、重试次数和 MCP 指令 |

### G. REST API、WebSocket、审批、GitHub

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-G1 | 基础 API | health/agents/engine/tasks/stats 返回结构与状态正确 |
| TC-G2 | 文件上传 | 10MB 内保存并返回路径；超限返回 413 |
| TC-G3 | WebSocket | connected、ping/pong、广播事件、断连清理正常 |
| TC-G4 | 审批 | allow/deny 写入 control_response；未知 request 返回 404；进程关闭返回 410 |
| TC-G5 | GitHub Webhook | 配置 secret 时验签；issues.opened 创建任务；其他事件忽略 |
| TC-G6 | GitHub Client | Issue/PR 创建、列表、评论、关闭、合并、reviewer 请求使用 agent 身份 |

### H. Dashboard 前端

| ID | 测试内容 | 预期结果 |
|---|---|---|
| TC-H1 | 页面加载 | 显示 TeamChat 标题、三个 Agent 卡片；失败显示错误 banner 和 Retry |
| TC-H2 | WebSocket 状态 | connected/connecting/offline 文案正确；断线禁用输入并自动重连 |
| TC-H3 | 聊天历史 | 只加载 prod 历史，刷新按钮可拉新消息，显示加载/失败状态 |
| TC-H4 | 聊天输入 | @mention、IME、Enter/Shift+Enter、附件、剪贴板图片、发送中禁用正常 |
| TC-H5 | 消息渲染 | 人类/agent/系统/任务事件/thinking/tool_calls/审批/Markdown/Unicode 正确 |
| TC-H6 | 审批交互 | Allow/Deny 调用 API，成功后隐藏卡片，失败显示系统错误 |
| TC-H7 | Agent 侧栏 | busy/idle、执行耗时、展开角色卡和最近会话正确 |
| TC-H8 | 右侧面板 | Tasks 看板默认展示；Stats L1/L2/L3 与 Live Engine Mode、queue、Recent Events 正常，侧栏可折叠 |
| TC-H9 | Tasks 看板 | Running/Waiting/Pending/Done/Failed 分组、依赖标签、失败重试/转派/放弃、按 agent 筛选、WS 实时更新 |

## 4. 执行优先级

| 优先级 | 说明 | 测试点 |
|---|---|---|
| P0 | 核心协作链路，阻塞发布必须通过 | TC-A1/A2/A3/A4、TC-B1/B2/B4/B5/B6、TC-C1/C2/C3/C5、TC-D1/D3、TC-E1/E2/E5/E6、TC-F1/F2/F3/F4/F5/F6、TC-G1/G3/G4、TC-H1/H2/H3/H4/H5 |
| P1 | 常规功能与回归，应在交付前通过 | TC-B3、TC-C4、TC-D2/D4、TC-E3/E4、TC-G2/G5/G6、TC-H6/H7/H8 |
| P2 | 边界和外部依赖，按环境可用性执行 | 真实 CLI smoke、真实 GitHub webhook/client 联调、长文本/大数据量边界 |

## 5. 执行约束

- 只写本地文档与测试，不执行 `git push`，不创建 PR。
- GitHub 相关用例在 GitHub 账号恢复前使用 mock，不要求真实网络。
- 执行结果记录到 PROGRESS.md，发现 Bug 按项目流程登记。

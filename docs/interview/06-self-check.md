# 06. 自查清单

> 面试前最后过一遍。每个问题都能脱稿讲清楚（不看文档），才算准备好。

## 项目概览

- [ ] 30 秒电梯陈述（项目是什么、解决什么问题）
- [ ] 1 分钟版本（+ 技术栈、核心功能）
- [ ] 3 分钟版本（+ 架构、分工、数据）
- [ ] 能说出项目规模数字（Issues/PRs/Tests）

## 核心技术点（每个都要能讲 2 分钟）

- [ ] stream-json 驱动：为什么不用 PTY，三个 CLI 格式差异
- [ ] Session 管理：session ID 怎么捕获、怎么复用、多会话隔离
- [ ] MCP Server：为什么用工具不用文本解析，4 个工具是什么
- [ ] 审批流：control_request 流程、Event 同步、死锁怎么修的
- [ ] 数据库：三表结构、FK 隔离、为什么单文件
- [ ] 并行调度：asyncio.gather、消息去重坑
- [ ] AI 验证：三层验证、抓到过哪些 bug

## 取舍题（每个都能说"为什么选这个不选那个"）

- [ ] stream-json vs PTY
- [ ] CLI vs API
- [ ] 自己写 vs LangChain
- [ ] SQLite vs Postgres
- [ ] 人工审批 vs acceptEdits
- [ ] 三 agent 分工依据

## 失败案例（每个都有完整故事）

- [ ] 审批双 Event 死锁（问题→发现→修复→测试）
- [ ] MCP `--mcp-config` 参数吞 prompt（→ .mcp.json）
- [ ] 并行消息去重丢回复（→ 内容+时间窗口）
- [ ] Cursor 命令名写错（→ agent 而非 cursor-agent）
- [ ] 数据库误提交 git（→ gitignore + 种子）
- [ ] 跳过 review 直接合并（→ 铁律 + 人类执行合并）

## 数据点（背下来）

- Issues: 90+ closed
- PRs: 90+，全部 review 后合并
- Tests: 60+ passing
- 三只咪分工：cici 架构 / coco 开发 / soso QA
- 我的职责：引擎层 + 架构 + 数据库

## 表达检查

- [ ] 结论先行（先说是什么，再说过程）
- [ ] 用数字（不说"很多"，说"90+ Issues"）
- [ ] 主动讲失败（体现验证能力，面试官最看这个）
- [ ] 不贬低 AI 也不神话 AI（"AI 是能力强的协作者，我为结果负责"）

# BACKLOG — 待办事项 & 已知问题

> Last updated: 2026-07-10

## 🐛 Known Bugs

| # | Bug | 状态 | 谁负责 |
|---|---|---|---|
| 1 | 前端显示 Unicode escape (`\U0001F3D7` 等) | 🔴 待修复 | coco咪/soso咪 联合排查 |
| 2 | 无 @mention 消息 cici咪 不回复 | 🔴 等 Worker 实现 | cici咪 |
| 3 | Codex/Cursor 审批不可用 | 🟡 已知限制，接受 | — |

## 📋 TODO (未排期)

| # | 任务 | ADR 引用 | 优先级 |
|---|---|---|---|
| 1 | MCP Server（teamchat: create_task 等 tools）| ADR-003 §7 | 高 |
| 2 | Claude 审批端点 (`POST /api/approval`) | ADR-003 §2.4 | 高 |
| 3 | Worker Pool 持久进程（减少冷启动延迟）| ADR-003 | 中 |
| 4 | Git Worktree 隔离 | ADR-003 §5 | 低 |
| 5 | Conflict Resolver（辩论→投票→裁决）| 设计 doc §4 | 低 |
| 6 | Codex MCP Server 模式（实现审批）| — | 低 |

## 🔄 流程改进

| # | 建议 | 来源 |
|---|---|---|
| 1 | PR 不能跳过 review | cici咪 多次违规的教训 |
| 2 | 每个 session 先读 START-HERE.md | 本次添加 |
| 3 | Bug 修复必须走 Issue → PR 流程 | 本次添加 |

## ✅ 最近完成

| # | 任务 | 日期 |
|---|---|---|
| 1 | ADR-003 完整实施 (C1-C6) | 2026-07-10 |
| 2 | soso咪 回顾审查 (26 tests) | 2026-07-10 |
| 3 | Roundtable 风格前端重写 | 2026-07-10 |

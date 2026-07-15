# PROGRESS

> Last updated: 2026-07-15

## 当前

Phase: ADR-003 实施打磨。冷启动绑定已实现，Session 管理基本就绪。

## 🔴 Open Issues

| # | 内容 | 谁 | PR |
|---|---|---|---|
| 69 | PR #68 回顾审查 | soso咪 | #70 |

## ✅ 本轮已完成

| 日期 | # | 内容 | PR |
|---|---|---|---|
| 07-15 | 67 | 历史顺序+人类对齐 | #68 |
| 07-15 | 61 | Cursor 冷启动修复 | #64 |
| 07-15 | 62 | 刷新丢历史 | #65 |
| 07-15 | 63 | Live Panel 重复 | #66 |
| 07-15 | 59 | 新会话冷启动绑定 | #60 |
| 07-15 | 57 | Session bugs 修复 | #57 #58 |
| 07-15 | 50-52 | 消息重复+粘贴截图+Stats | #54 #55 #56 |
| 07-15 | 39 | 统一数据库 | #49 |
| 07-15 | 42-44 | 回归修复 | #45 #46 |
| 07-15 | 36-38 | Session 持久化+Stats+Live | #40 #41 |
| 07-15 | 25 | Unicode emoji | #26 #27 |

## 数据库

- 1 个文件: `.teamchat/teamchat.db`
- 3 个表: `teamchat_sessions` / `agent_calls` / `tasks`
- ADR-003 §10

## 待办

| 内容 | 谁 | 优先级 |
|---|---|---|
| MCP Server | cici咪 | 高 |
| /api/approval | cici咪 | 高 |
| 无 @mention 回复 | cici咪 | 中 |
| Stats/Live 面板完善 | coco咪 | 中 |

## 铁律更新

- **cici咪 不再执行 `gh pr merge`** — 合并由人类执行

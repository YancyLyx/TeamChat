# PROGRESS

> Last updated: 2026-07-31

## 当前

Phase: ADR-004 设计阶段。任务调度器让 agent 之间能主动通信。

## 🔴 Open Issues

| # | 内容 | 谁 |
|---|---|---|
| - | Task Scheduler 实现 | cici咪 |

## ✅ 本轮已完成

| 日期 | # | 内容 | PR |
|---|---|---|---|
| 07-31 | - | PR #92: mdRender 重复声明修复 | #92 |
| 07-31 | - | PR #80: 关闭（已过时，main 已有更完整实现） | - |
| 07-31 | - | 更新 cici咪 session ID | - |
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
- 3 个表: `teamchat_sessions` / `agent_calls` / `task_table`
- ADR-003 §10, ADR-004 §4.2

## 待办

| 内容 | 谁 | 优先级 |
|---|---|---|
| Task Scheduler 实现（ADR-004） | cici咪 | 高 |
| bus 消息集成 | cici咪 | 高 |
| Dashboard 显示 bus 消息 | coco咪 | 中 |
| 端到端测试 | soso咪 | 中 |
| Stats/Live 面板完善 | coco咪 | 低 |

## 铁律更新

- **cici咪 不再执行 `gh pr merge`** — 合并由人类执行

# PROGRESS — 唯一动态文档（每次 session 必读 + 必更新）

> 这个文件 = 进度表 + 待办清单。没有 BACKLOG，没有单独的 TODO 文件。
> 每次 session 开头读，结束时更新。

## 🔴 当前进行中

| # | 任务 | 谁 | 状态 | 备注 |
|---|---|---|---|---|
| 36 | Session 刷新后消失 | cici咪 | 🔴 | 待开 Issue |
| 37 | Stats 面板指标修复 | coco咪 | 🔴 | 待开 Issue |
| 38 | Engine 可观测面板 | coco咪 | 🔴 | 待开 Issue |

## 🟡 待办（未排期）

| # | 内容 | 谁 | 优先级 |
|---|---|---|---|
| — | MCP Server (create_task 等 tools) | cici咪 | 高 |
| — | Claude 审批端点 /api/approval | cici咪 | 高 |
| — | 无 @mention 消息 cici咪 回复 | cici咪 | 中 |
| — | Worker Pool 持久进程 | cici咪 | 中 |

## ✅ 本轮已完成

| 日期 | # | 内容 | PR |
|---|---|---|---|
| 07-15 | 31 | Codex 干净回复 | #35 |
| 07-15 | 32 | 并行 greeting | #34 |
| 07-15 | 33 | Stats 持久化 | #34 |
| 07-15 | 28 | Session Manager + Stats Panel | #28 |
| 07-15 | 25 | Unicode emoji | #26 #27 |
| 07-14 | 16-19 | ADR-003 C1-C6 | #20 #21 #22 |

## 🐛 已知 Bug

| # | Bug | 状态 |
|---|---|---|
| 25 | Unicode 转义 `\U0001F3D7` | ✅ Fixed |
| 31 | coco咪 回复 raw thinking | ✅ Fixed |
| 32 | 打招呼串行 | ✅ Fixed |
| 33 | Stats 无数据 | ✅ Fixed |
| — | 新建 Session 刷新消失 | 🔴 |
| — | Stats 指标错误 (task 数 vs token) | 🔴 |
| — | 左侧/右侧面板数据不一致 | 🔴 |
| — | Codex/Cursor 审批不可用 | 🟡 已知限制 |

## 📊 统计

- Issues: 20 closed
- Tests: 63/66 passing
- Phase: ADR-003 实施打磨期

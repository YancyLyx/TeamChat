# 01. 项目概览

## 一句话

TeamChat 是一个多 AI Agent 协作平台：把 Claude Code、Codex CLI、Cursor 三个 AI coding agent 变成自治协作的开发团队，人类从"人肉路由器"变成"观察者"。

## 30 秒电梯陈述

> 现在用多个 AI coding agent 的最大痛点是：人类在终端之间复制粘贴上下文、手动追踪谁说了什么、帮 AI 传话。TeamChat 解决了这个问题——我把三个 CLI agent（Claude 做架构、Codex 做开发、Cursor 做 QA）接到一个平台层上，它们通过 GitHub Issues/PRs 和聊天室自主协作。人类只需要在 Dashboard 上提需求、看进度、点审批。

## 解决的问题

**痛点：人肉路由器**

```
传统方式:
  人类 ←→ 终端1 (Claude)  复制粘贴上下文
 人类 ←→ 终端2 (Codex)
 人类 ←→ 终端3 (Cursor)
 人类自己判断：谁做什么、顺序、汇总结果

TeamChat:
  人类 → 聊天室 → cici咪 分析拆任务 → MCP 创建任务
  → Engine 派发 → coco咪 执行 → soso咪 review → 完成
  人类只在需要审批时点按钮
```

## 核心功能

| 功能 | 说明 |
|---|---|
| 多 agent 聊天室 | 人类 + 三只咪在同一聊天室，气泡分色 |
| 任务编排 | cici咪 通过 MCP 工具创建任务，Engine 自动派发 |
| CLI 会话管理 | 每只咪的上下文通过 session ID 绑定，跨消息延续 |
| 审批卡片 | Claude 请求工具权限时弹卡片，人类点允许/拒绝 |
| 实时观测 | Agent 状态、Stats L1/L2/L3、Live 事件流 |
| 数据隔离 | 多会话各自独立数据（FK 隔离）|

## 团队分工（我负责什么）

| 角色 | 负责 | 本项目中的体现 |
|---|---|---|
| 架构师（我） | 系统设计、核心引擎、文档 | engine/ 全部、ADR、数据库设计 |
| 开发（coco咪） | 前端、API 层 | Dashboard、FastAPI 路由 |
| QA（soso咪） | 测试、代码审查 | 70+ 次 review，发现 XSS/死锁等 |

## 规模数据

- Issues: 90+（全部走 PR 流程）
- PRs: 90+（全部经 soso咪 review 后合并）
- Tests: 60+ passing（单元 + 集成 + E2E）
- 技术栈: Python/FastAPI/SQLite + React/Vite/Tailwind

## 面试可能追问（对应文档）

| 追问 | 去读 |
|---|---|
| 为什么用 CLI 而不是 API？ | `03` §stream-json |
| 三只咪怎么协作的？ | `04-ai-workflow.md` |
| 你怎么验证 AI 的输出？ | `03` 每个点的"失败/改进" |
| 哪个部分是你独立完成的？ | 本文档"团队分工" |

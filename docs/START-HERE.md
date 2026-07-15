# START HERE — TeamChat 项目导航

> 每次 session 开始前先读这个文件。5 分钟了解全貌。

## 这是什么项目

TeamChat — 把 Claude Code、Codex CLI、Cursor 三个 AI coding agent 变成自治协作团队的平台层。

**目标：人类从"人肉路由器"变成"观察者"。**

## 团队成员

| 成员 | CLI | 角色 | 负责 |
|---|---|---|---|
| 🧑‍💻 你 | — | 产品经理 | 提需求、审设计、按审批 |
| 🏗️ cici咪 | Claude `5fbaf844-...` | 架构师 | 引擎层、任务拆分、文档 |
| ⚡ coco咪 | Codex `019f40ef-...` | 开发 | 前端、API 层 |
| 🔍 soso咪 | Cursor `04e64d6d-...` | QA | 测试、代码审查 |

## 文档地图

### 新成员？先看这些（按顺序）
1. **`docs/specs/2026-07-08-teamchat-design.md`** — 11 章完整设计
2. **`docs/architecture.md`** — 运行时架构（图示）
3. **`docs/process.md`** — 协作流程 + 铁律

### 想了解技术决策？
4. **`docs/decisions/001-tech-stack.md`** — 为什么选 Python/FastAPI/React
5. **`docs/decisions/002-persistent-agent-architecture.md`** — Worker Pool 设计（已过时，被 003 替代）
6. **`docs/decisions/003-real-cli-workflow.md`** — **当前技术方案**：stream-json、MCP、聊天室设计

### 想了解 Phase 进度？
7. **`PROGRESS.md`**（根目录）— 每个 Phase 的完成状态
8. **`docs/phases/`** — 各阶段详细文档

### 想了解 Agent 角色？
9. **`docs/agents/cici-claude.md`** — cici咪 的性格和能力
10. **`docs/agents/coco-codex.md`** — coco咪 的性格和能力
11. **`docs/agents/soso-cursor.md`** — soso咪 的性格和能力

### 有 Bug 或待办？
12. **`docs/BACKLOG.md`** — 已知问题 + 待办列表

---

## 当前状态

- **Phase:** ADR-003 实施完成 ✅
- **Issues:** 15/15 关闭
- **Tests:** 26/26 通过
- **下一步:** MCP Server、审批端点、生产加固

见 `PROGRESS.md` 获取最新状态。

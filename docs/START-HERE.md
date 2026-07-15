# START HERE — TeamChat 项目导航

## 每次 session 先读这两个

1. **`PROGRESS.md`**（根目录）— 当前进度 + 待办 + Bug
2. **本文档** — 导航 + 铁律

## 铁律

1. 不能直接 push main。必须：分支 → PR → review → merge
2. 不能跳过 review。cici咪 的代码也要 soso咪 审查
3. 不能跳过测试。改动前跑测试，改动后写测试
4. Bug 修复也走 Issue → 分支 → PR → review → merge 流程
5. 各自负责自己的模块。cici咪→引擎，coco咪→前端，soso咪→测试
6. 新 Bug/想法 → 写进 PROGRESS.md
7. Session 结束时更新 PROGRESS.md

## 团队成员

| 成员 | CLI | 角色 | 负责 |
|---|---|---|---|
| 🧑‍💻 你 | — | 产品经理 | 提需求、审设计、按审批 |
| 🏗️ cici咪 | Claude `5fbaf844-...` | 架构师 | 引擎层、ADRs、任务拆分 |
| ⚡ coco咪 | Codex `019f40ef-...` | 开发 | 前端 Dashboard、API 层 |
| 🔍 soso咪 | Cursor `04e64d6d-...` | QA | 测试、代码审查 |

## 文档地图（5 个不动的 + 1 个会变的）

### 会变的（每次 session 更新）
- **`PROGRESS.md`** — 进度 + 待办 + Bug。唯一动态文档

### 不动的（改了才更新）
- **`CLAUDE.md`** — cici咪 手册（铁律 + 角色）
- **`AGENTS.md`** — 三猫协议
- **`docs/process.md`** — 协作流程说明
- **`docs/architecture.md`** — 运行时架构
- **`docs/decisions/003-real-cli-workflow.md`** — 当前技术方案

### 参考（基本不动）
- **`docs/specs/2026-07-08-teamchat-design.md`** — 初始设计（锁定）
- **`docs/decisions/001-002.md`** — 早期 ADR
- **`docs/phases/`** — 各阶段回顾
- **`docs/agents/`** — 角色卡（静态性格）

## 当前状态

- Phase: ADR-003 实施打磨
- Issues: 20 closed
- Tests: 63/66
- 见 `PROGRESS.md`

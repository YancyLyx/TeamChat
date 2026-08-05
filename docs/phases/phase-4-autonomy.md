# Phase 4: Autonomy (自治)

**Status:** 🟢 进行中（核心闭环已完成，剩余项见下）
**Date:** 2026-07-08（初稿）/ 2026-08-05（状态跟踪更新）
**说明:** 本文件是 Phase 4 的**完成状态跟踪**（对照 `docs/decisions/` 的 ADR 逐项核对）；详细设计见 decisions 文档。

---

## 📁 对应 decisions 文档

| ADR | 主题 | 状态 |
|---|---|---|
| `001-tech-stack.md` | Python/FastAPI/React/SQLite 技术栈 | ✅ 落地 |
| `002-persistent-agent-architecture.md` | 常驻 workers 架构 | ❌ **已 revert**（218fa56）——被 ADR-003 取代 |
| `003-real-cli-workflow.md` | 真实 CLI 一次性进程 + stream-json | ✅ 落地（当前架构） |
| `004-phase4-complete.md` | Phase 4 完整规划（含 #96 并行派发、#97 审查闭环设计） | 🔄 实施中 |

---

## ✅ 已完成（对应 decisions 章节）

| 功能 | 对应 ADR-004 章节 / 追踪编号 | 验收 |
|---|---|---|
| 协作闭环（发消息 → 拆任务 → 派发 → 执行 → 回流 → 审核 → done） | 分段实施计划 Phase 4.0 | 端到端验证通过（2026-08-01） |
| Result Relay 结果回传 + 排队审核 | 断点 1 | ✅ |
| 依赖检查 + 自动派发（DAG） | 断点 2 | ✅（含 feature_id 需求树） |
| 失败自动重试（3 次指数退避） | 断点 3 | ✅（Phase 4.5 自愈） |
| 忙时排队（@mention/分析/greeting） | 完善点⑥ | ✅ |
| 看板手动干预（重试/转派/放弃） | Phase 4.5 | ✅ |
| Stats L1/L2/L3 观测面板 | ADR-004 规划 | ✅（L3 为 2026-08 新增） |
| 审批卡（control_request） | ADR-003 §3.4 | ✅ |
| 段落级流式输出 | 2026-08-03 新增 | ✅ |
| **任务编排并行派发** | #96（ADR-004 附章节） | ✅ 审查 + 真实 e2e 通过（2026-08-04） |
| **cici咪 任务审查闭环**（审查节点动态创建、task_type 驱动双模式、修复/复审循环、需求树 agent 着色） | #97（ADR-004 设计章节） | ✅ 实现 + soso咪 审查 + 五轮真实 e2e PASS（2026-08-05） |

---

## 🔴 未完成（待办）

| 功能 | 编号/文档 | 阻塞/优先级 |
|---|---|---|
| 终止正在执行的 agent（kill 进程） | PROGRESS 待办 | 高（用户紧急/跑偏场景） |
| Phase 4.1 GitHub Adapter（Issue 双向同步/Webhook） | ADR-004 规划 | ⏸ 阻塞于 GitHub 账号恢复 |
| 数据库优化（agent_calls 大文本外置 + 10 万行归档） | PROGRESS 待办 | 低 |
| Git Worktree 隔离（多 agent 共享工作区问题） | PROGRESS 教训记录 | 低（并发需求时实施） |
| 冲突解决（辩论→投票→裁决） | 早期 roadmap | 未启动 |
| MCP 对外接入 | 早期 roadmap | 未启动（MCP 已对内用，对外未做） |

---

## 📌 历史备注

- **ADR-002 常驻 workers 曾实现一半被整体 revert**（commit 218fa56）——早期试错，现架构为 ADR-003 一次性进程 + resume（详细取舍见 `interview/03 §3.2`）
- 早期 Bug 清单（消息重复/IME/裸 JSON/无 @mention）均已修复，见 git 历史

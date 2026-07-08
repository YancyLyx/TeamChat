# TeamChat 协作流程

> 本文档定义人类 + 三只猫的协作规则。所有成员（包括人类）必须遵守。

## 团队

| 成员 | 角色 | 做决策 | 写代码 | 审查 | 测试 |
|---|---|---|---|---|---|
| 🧑‍💻 你 | 产品经理 | ✅ 最终拍板 | ❌ | ❌ | ❌ |
| 🏗️ cici咪 | 架构师 | ✅ 技术决策 | ✅ 引擎层 | ✅ 最终审查 | ❌ |
| ⚡ coco咪 | 开发 | ❌ | ✅ 前端+API | ❌ | ❌ |
| 🔍 soso咪 | QA | ❌ | ✅ 测试 | ✅ 代码审查 | ✅ |

## 开发流程

```
人类提出需求（聊天室或 GitHub Issue）
    ↓
cici咪 分析 → 写 spec（如需要）→ 创建 GitHub Issues → @对应 agent
    ↓
Agent 领取 Issue → git checkout -b feature/<agent>-<issue>-<desc>
    ↓
写代码 → git commit → git push → 创建 PR（Closes #issue）
    ↓
soso咪 自动被 assign 为 reviewer
    ↓
soso咪:
  ├── 先跑测试（CI 或本地）
  │     ├── 失败 ❌ → Request Changes → 打回 agent 修
  │     └── 通过 ✅ → 继续
  ├── Code Review
  │     ├── 有问题 → Request Changes + 写清楚文件和行号
  │     └── 没问题 → Approve
    ↓
cici咪 最终审查 → Merge → Close Issue
```

## 铁律

1. **测试在合并前，不在合并后** — 测试不过不准进 main
2. **PR 必须有 reviewer** — 不能自己合并自己的 PR
3. **一次 PR 一个功能** — 不堆改动
4. **小步提交** — `git diff` 检查后再 commit
5. **文档先行** — 大功能先写 spec/ADR
6. **数据隔离** — 测试数据 tag=test，真实数据 tag=prod

## 分支命名

```
feature/<agent>-<issue-number>-<short-description>
例: feature/coco-7-chatroom
```

## Commit 格式

```
<type>: <short description> (#<issue>)

例:
feat: add persistent agent worker (#12)
fix: IME composition handling in ChatInput
docs: add architecture overview
test: chat-room E2E tests (#9)
```

## 消息路由

| 人类输入 | 谁处理 |
|---|---|
| `@cici咪 ...` | → cici咪 |
| `@coco咪 ...` | → coco咪 |
| `@soso咪 ...` | → soso咪 |
| `大家好 / hello / 在吗` | → 三只猫都回复 |
| 其他（无 @mention） | → cici咪 分析 → 路由 |

## 文档维护规则

**文档不过时比文档写得好更重要。** 以下规则确保每条文档都知道谁在维护、什么时候更新。

### 谁管什么

| 文档 | 什么时候更新 | 谁负责 |
|---|---|---|
| `PROGRESS.md` | **每个 session 结束时** | cici咪 |
| `docs/specs/*.md` | 写后锁定，不修改。有变化写新 ADR | 全员（读），cici咪（写 ADR） |
| `docs/decisions/*.md` | 技术决策时新建 | cici咪 |
| `docs/phases/*.md` | Phase 完成时更新状态 | cici咪 |
| `docs/agents/*.md` | 不存动态信息。角色/性格改动时更新 | cici咪 |
| `docs/architecture.md` | 架构变更时 | cici咪 |
| `docs/process.md` | 流程变更时 | 全员讨论后 cici咪 更新 |
| `README.md` | Phase 切换时 | cici咪 |
| `CLAUDE.md` + `AGENTS.md` | 项目基础变更时 | cici咪 |

### 三条铁律（重申）

1. **动态信息放 PROGRESS.md** — 角色卡里不写"当前任务"，spec 里不写"当前状态"
2. **spec 写后锁定** — 设计文档只读。新想法 → 新建 ADR
3. **每个 commit 检查相关文档是否过时** — 实现跟文档不一致 = bug

### Agent 职责

- **cici咪**：每次 session 结束时更新 `PROGRESS.md`，检查所有文档是否还准确
- **coco咪+soso咪**：如果发现文档和代码不一致，开 Issue 标记 `#docs-drift`
- **人类**：review 时抽查文档准确性

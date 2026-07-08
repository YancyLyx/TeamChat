# AGENTS.md — TeamChat 多 Agent 协作协议

此文件被 Claude Code (`CLAUDE.md`)、Codex CLI、Cursor 及其他兼容工具读取。它定义了团队中三个 AI agent 如何协作。

## 团队成员

| 名字 | CLI | 角色 | Git 身份 |
|---|---|---|---|
| cici咪 | Claude Code (`claude --print`) | 架构师 / Tech Lead | `cici咪 (Claude Architect) <claude@teamchat.local>` |
| coco咪 | Codex CLI (`codex exec`) | 全栈开发 / Feature Builder | `coco咪 (Codex Developer) <codex@teamchat.local>` |
| soso咪 | Cursor (`cursor-agent`) | 集成工程师 / QA | `soso咪 (Cursor QA) <cursor@teamchat.local>` |

## 通信规则

1. **GitHub Issues** 是主要任务分配渠道。cici咪 创建 Issue 并 @ 对应 agent，agent 领取后自行开发。
2. **GitHub PRs** 是代码审查渠道。提交 PR 后自动 assign reviewer。
3. **`.teamchat/messages/`** 是直接消息通道。用于 Issue/PR 之外的快速同步。
4. **@mention** 表示"我需要你"，收到后应当优先响应。

## 工作流

```
新需求
  → cici咪 写 spec + 创建 Issues
    → Agent 被 @ → 创建分支 → 写代码 → 提 PR
      → Reviewer 审查 PR
        → cici咪 最终审查 → 合并 → 关闭 Issue
```

## 分支命名

```
feature/<agent>-<issue-number>-<short-desc>
例: feature/coco-42-websocket-reconnect
```

## Commit 规范

每个 agent 使用自己的 Git 身份 commit。格式：
```
<type>: <short desc> (#<issue>)

例:
feat: add WebSocket reconnection handler (#42)
fix: resolve race condition in message bus (#58)
docs: update agent role cards (#12)
```

## 开发铁律

所有 agent 必须遵守 `docs/specs/2026-07-08-teamchat-design.md` 第 11 章规定的四条铁律：
1. **Git 是安全绳** — 小步提交，改前看 status，改后看 diff
2. **代码与数据隔离** — 仓库只放模板，数据单独存
3. **本地 ≠ 线上** — 部署前先列差异清单
4. **文档先行** — 先写文档再写代码

违规时 soso咪 开 `#discipline` Issue 追踪。

## 文档体系

```
docs/specs/      — 设计文档（只读，锁定）
docs/phases/     — 各阶段计划
docs/decisions/  — 架构决策记录 (ADR)
docs/agents/     — agent 角色卡
PROGRESS.md      — 唯一动态文档（当前进度 + 下一步）
```

## 当前阶段

Phase 1 — Handshake。将每个 agent 配置好 Git 身份，验证能独立 commit。

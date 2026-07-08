# Phase 4: Autonomy (自治)

**Status:** 🔴 In Progress
**Date:** 2026-07-08

## Goal

实现完整自治协作闭环 — 人类在聊天室里发消息，agent 自动执行、协作、交付。

## Current State

### ✅ Done

| # | Task | Who |
|---|---|---|
| 1 | 聊天室架构设计 | cici咪 |
| 2 | 消息路由规则 (ADR-002) | cici咪 |
| 3 | Chat-room Dashboard (MVP) | coco咪 |
| 4 | `engine/message_parser.py` | cici咪 |
| 5 | `api/routes/chat.py` (basic) | cici咪 |
| 6 | Chat-room E2E tests (4 tests) | soso咪 |

### 🔴 Remaining (ADR-002 implementation)

| # | Task | Who |
|---|---|---|
| 1 | Persistent Agent Workers | cici咪 |
| 2 | WorkerPool + 生命周期管理 | cici咪 |
| 3 | 打招呼广播路由 | cici咪 |
| 4 | CLI 输出解析 (THINKING/TOOL_CALLS/RESULT) | cici咪 |
| 5 | 会话 Tag 隔离 (test vs prod) | cici咪 |
| 6 | ChatRoom 折叠区 + 历史过滤 | coco咪 |
| 7 | E2E 测试更新 | soso咪 |

### ⏳ Future

| # | Task | Who |
|---|---|---|
| - | Conflict Resolver (辩论→投票→裁决) | cici咪 |
| - | Git Worktree 隔离 | soso咪 |
| - | MCP 接口（对外接入） | coco咪 |
| - | 自愈机制（失败重试/转派） | soso咪 |

## Current Bugs

| Bug | Status |
|---|---|
| 消息显示两次 | ✅ Fixed (dedup by ID) |
| 中文输入 Enter 误触发送 | ✅ Fixed (IME composition) |
| cici咪 输出裸 JSON | ✅ Fixed (result field parsing) |
| 无 @mention 没回复 | 🔴 等 ADR-002 Worker 实现后修复 |
| 测试数据混入历史 | 🔴 等 session tagging |

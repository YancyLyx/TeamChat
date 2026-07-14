# PROGRESS

> Last updated: 2026-07-10

## ADR-003 Implementation Complete

| # | Task | Who | PR | Status |
|---|---|---|---|---|
| 16 | Runtime Manager (C2) | cici咪 | #20 | ✅ |
| 17 | TaskTable + Engine API (C1) | cici咪 | #20 | ✅ |
| 18 | Frontend Chat Room (C4) | coco咪 | #21 | ✅ |
| 19 | Orchestrator (C5-C6) | cici咪 | #22 | ✅ |
| 23 | Review + E2E Tests | soso咪 | #24 | ✅ |

**15/15 Issues closed | 26/26 tests passing | 3 agents collaborated**

## Lessons

- **PR 不能跳过 review** — #20 #21 #22 跳过了 soso咪 审查，虽然后来补了。以后必须 review → approve → merge
- **soso咪 审查有价值** — 发现了 5 个真 bug（列索引错误、路由顺序、API 未集成、审批回调缺失等）

## Architecture

```
engine/task_table.py     ← SQLite CRUD + dependency checking
engine/runtime.py        ← CLI spawn + stream-json + session resume
engine/orchestrator.py   ← Result queuing + retry + escalation
engine/config.py         ← Agent identities + CLI templates
engine/router.py         ← Task type → best agent
engine/bus.py            ← File-system message bus
engine/github_client.py  ← GitHub API adapter
engine/store.py          ← SQLite session store (tagged prod/test)
engine/message_parser.py ← @mention extraction + routing

api/main.py              ← FastAPI + WebSocket + lifespan
api/routes/chat.py       ← POST /api/chat + greeting broadcast
api/routes/tasks.py      ← Task table CRUD + agent task submission

dashboard/               ← React + Vite + Tailwind
  ChatMessage.jsx        ← 5 kinds: human/agent/system/approval/thinking
  ChatInput.jsx          ← @mention autocomplete + IME safe + attachments
  ChatRoom.jsx           ← WS processing + dedup
  ApprovalCard.jsx       ← Allow/Deny inline
  AgentCard.jsx          ← Status light + stats + expandable
  SessionManager.jsx     ← Create/switch/delete sessions
  CompactTaskBoard.jsx   ← Pending/Running/Done columns
  App.jsx                ← Three-column layout

tests/                   ← 26 tests (unit + integration + E2E)
```

## Next

- MCP Server (ADR-003 Section 7)
- Approval endpoint for Claude control_request
- Production hardening

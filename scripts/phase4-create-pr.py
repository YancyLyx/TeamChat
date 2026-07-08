#!/usr/bin/env python3
"""Create PR for Phase 4 chat-room + routing engine."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)
    pr = await cici.create_pr(
        title="feat: Chat-room Dashboard + message routing engine (#7, #8)",
        head="feature/coco-7-chatroom",
        base="main",
        body="""## Overview
Chat-room Dashboard redesign + message routing engine.

## What's Included

### Dashboard (coco咪)
- ChatRoom.jsx: Main chat message flow with auto-scroll
- ChatMessage.jsx: Per-message component with agent styling
- ChatInput.jsx: @mention input with send
- AgentPanel.jsx: Compact left sidebar agent status
- CompactTaskBoard.jsx: Collapsible right sidebar

### Engine (cici咪)
- engine/message_parser.py: @mention extraction + routing logic
- api/routes/chat.py: POST /api/chat endpoint
- api/main.py: Registered chat router

## How It Works
1. Human types "@coco咪 do X" in chat input
2. POST /api/chat -> parses @mention -> routes to agent
3. AgentRunner executes -> result pushed via WebSocket
4. ChatRoom displays agent response as chat message

Closes #7, closes #8

Review requested: @soso咪""")
    print(f"PR #{pr.number}: {pr.title}\n   {pr.url}")
    await cici.close()

if __name__ == "__main__":
    asyncio.run(main())

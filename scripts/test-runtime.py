#!/usr/bin/env python3
"""Test Runtime Manager with real CLI sessions. Run: python scripts/test-runtime.py"""

import asyncio, json, sys
sys.path.insert(0, ".")

from engine.config import load_config, AGENT_CICI, AGENT_COCO, AGENT_SOSO
from engine.runtime import RuntimeManager, find_claude_session, find_codex_session, find_cursor_session

async def main():
    config = load_config()

    # 1. Discover existing sessions
    print("=" * 60)
    print("Session Discovery")
    print("=" * 60)

    cid = find_claude_session(config.project_root)
    print(f"Claude session: {cid}")

    xid = find_codex_session()
    print(f"Codex session: {xid}")

    sid = find_cursor_session()
    print(f"Cursor session: {sid}")

    # 2. Create Runtime Manager
    rt = RuntimeManager(config)
    discovered = rt.discover_sessions()
    print(f"\nDiscovered: {discovered}")

    # 3. Test sending a message to cici咪 using existing session
    print("\n" + "=" * 60)
    print("Test: cici咪 with --resume")
    print("=" * 60)

    events = await rt.send(AGENT_CICI,
        "Please reply with ONE short sentence: what is your current session ID? "
        "Just say 'My session ID is <the id>'.")
    for e in events:
        if e.type in ("text", "done"):
            print(f"[{e.type}] {e.agent_name}: {e.content[:200]}")
        elif e.type == "session_init":
            print(f"[session_init] {e.session_id}")

    print(f"\nStored session: {rt.get_session_id(AGENT_CICI)}")
    print(f"Events: {len(events)} total")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Test Codex CLI approval — try a dangerous command. Run: python scripts/test-codex-approval.py"""

import asyncio, json

async def main():
    cmd = [
        "codex", "exec",
        "--json",
        "List all files in /tmp/ starting with 'teamchat'. If no such files exist, create one called /tmp/teamchat-approval-test.txt with content 'approval test'. Also try to delete /tmp/teamchat-approval-test.txt if it exists.",
    ]

    print(f"Running codex exec --json ...")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    count = 0
    async for line in process.stdout:
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str: continue
        count += 1
        try:
            event = json.loads(line_str)
        except json.JSONDecodeError:
            print(f"[TEXT #{count}] {line_str[:300]}")
            continue

        etype = event.get("type", "?")
        item = event.get("item", {})

        if etype == "item.started":
            itype = item.get("type", "?")
            if itype == "command_execution":
                print(f"\n🔧 COMMAND START: {item.get('command', '')[:200]}")
                print(f"   Keys: {list(event.keys())}")
                print(f"   Item keys: {list(item.keys())}")
            elif itype == "reasoning":
                print(f"💭 Reasoning started")
            else:
                print(f"[item.started] type={itype}")

        elif etype == "item.completed":
            itype = item.get("type", "?")
            if itype == "command_execution":
                exit_code = item.get("exit_code")
                status = item.get("status")
                output = item.get("aggregated_output", "")[:200]
                print(f"🔧 COMMAND DONE: exit={exit_code} status={status}")
                print(f"   Output: {output}")
            elif itype == "reasoning":
                text = item.get("text", "")[:300]
                print(f"💭 Reasoning: {text}")
            elif itype == "agent_message":
                text = item.get("text", "")[:300]
                print(f"💬 Agent: {text}")
            else:
                print(f"[item.completed] type={itype} text={str(item.get('text',''))[:200]}")
                print(f"   All item keys: {list(item.keys())}")

        elif etype == "turn.completed":
            usage = event.get("usage", {})
            print(f"\n✅ Turn completed. Usage: {json.dumps(usage)}")

        elif etype == "thread.started":
            print(f"🧵 Thread: {event.get('thread_id', '')}")

        elif etype == "turn.started":
            print(f"🔄 Turn started")

        else:
            print(f"[{etype}] keys={list(event.keys())}")

    # Also read stderr for any approval prompts
    await process.wait()
    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    if stderr.strip():
        print(f"\n📢 STDERR ({len(stderr)} chars):")
        print(stderr[:2000])

    print(f"\nTotal events: {count}")

if __name__ == "__main__":
    asyncio.run(main())

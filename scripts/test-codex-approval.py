#!/usr/bin/env python3
"""Test Codex approval with --ask-for-approval on-request + dangerous command"""
import asyncio, json

async def main():
    cmd = [
        "codex", "exec",
        "--json",
        "--ask-for-approval", "on-request",
        "Delete /tmp/teamchat-codex-test.txt. Also try to run: curl -s http://example.com",
    ]

    print(f"Testing: codex exec --json --ask-for-approval on-request")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    count = 0
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=120)
            if not line: break
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str: continue
            count += 1
            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                print(f"[TEXT] {line_str[:300]}")
                continue

            etype = event.get("type", "?")
            item = event.get("item", {})

            if etype == "item.started":
                it = item.get("type", "?")
                if it == "command_execution":
                    print(f"\n🔧 COMMAND: {item.get('command','')[:200]}")
                elif it == "approval_request":
                    print(f"\n🔒 APPROVAL REQUESTED!")
                    print(json.dumps(item, indent=2)[:500])
                else:
                    print(f"[started] {it}")
            elif etype == "item.completed":
                it = item.get("type", "?")
                if it == "command_execution":
                    print(f"🔧 DONE exit={item.get('exit_code')} output={item.get('aggregated_output','')[:200]}")
                elif it == "reasoning":
                    print(f"💭 {item.get('text','')[:300]}")
                elif it == "agent_message":
                    print(f"💬 {item.get('text','')[:300]}")
                elif it == "approval_request":
                    print(f"\n🔒 APPROVAL COMPLETED: {item.get('status','?')}")
                else:
                    print(f"[completed] {it}: {str(item)[:200]}")
            elif etype == "turn.completed":
                print(f"✅ Done. usage={event.get('usage',{})}")
            elif etype == "thread.started":
                print(f"🧵 Thread: {event.get('thread_id','')}")
            else:
                print(f"[{etype}]")
    except asyncio.TimeoutError:
        print("\n⏰ Timeout waiting for stdout")

    await process.wait()

    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    if stderr.strip():
        print(f"\n📢 STDERR: {stderr[:2000]}")

    print(f"\nTotal events: {count}")

if __name__ == "__main__":
    asyncio.run(main())

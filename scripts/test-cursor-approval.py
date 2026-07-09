#!/usr/bin/env python3
"""Test Cursor approval with --auto-review + dangerous command"""
import asyncio, json

async def main():
    cmd = [
        "cursor-agent",
        "--print",
        "--output-format", "stream-json",
        "--auto-review",
        "Delete /tmp/teamchat-cursor-test.txt. Also try to run: curl -s http://example.com",
    ]

    print(f"Testing: cursor-agent --print --output-format stream-json --auto-review")
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
            subtype = event.get("subtype", "")

            if etype == "system":
                print(f"⚙️  init session={event.get('session_id','')[:20]}... model={event.get('model','?')}")
            elif etype == "thinking":
                t = event.get("text", "")
                if t.strip(): print(f"💭 {t[:200]}")
            elif etype == "assistant":
                for c in event.get("message", {}).get("content", []):
                    ct = c.get("type", "?")
                    if ct == "text": print(f"💬 {c.get('text','')[:300]}")
                    elif ct == "tool_use":
                        print(f"\n🔧 TOOL: {c.get('name','?')}")
                        print(f"   input: {json.dumps(c.get('input',{}))[:300]}")
                    else: print(f"   [{ct}]")
            elif etype == "tool_call":
                tc = event.get("tool_call", {})
                print(f"🔧 TOOL_CALL: {tc.get('name','?')} id={event.get('call_id','')[:20]}...")

                # Check if this is an approval request
                tc_subtype = event.get("subtype", "")
                if tc_subtype == "approval_requested":
                    print(f"\n🔒 APPROVAL REQUESTED!")
                    print(f"   tool: {tc.get('name','?')}")
                    print(f"   args: {json.dumps(tc.get('arguments',{}))[:300]}")
                    print(f"   call_id: {event.get('call_id','')}")
            elif etype == "user":
                print(f"👤 User echo")
            elif etype == "result":
                print(f"\n✅ RESULT (error={event.get('is_error',False)}, {event.get('duration_ms',0)}ms):")
                print(f"   {str(event.get('result',''))[:500]}")
            else:
                print(f"[{etype}/{subtype}] keys={list(event.keys())[:6]}")

    except asyncio.TimeoutError:
        print("\n⏰ Timeout waiting for stdout")

    await process.wait()

    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    if stderr.strip():
        print(f"\n📢 STDERR: {stderr[:2000]}")

    print(f"\nTotal events: {count}")

if __name__ == "__main__":
    asyncio.run(main())

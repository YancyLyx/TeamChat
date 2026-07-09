#!/usr/bin/env python3
"""Test Cursor CLI approval — try a dangerous command WITHOUT --force. Run: python scripts/test-cursor-approval.py"""

import asyncio, json

async def main():
    # NO --force / --yolo flag — should trigger approval
    cmd = [
        "cursor-agent",
        "--print",
        "--output-format", "stream-json",
        "List /tmp/ files starting with 'teamchat'. If none exist, create /tmp/teamchat-cursor-approval.txt with 'test'. Then delete it.",
    ]

    print(f"Running cursor-agent --print --output-format stream-json (NO --force)...")
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
        subtype = event.get("subtype", "")

        if etype == "system":
            print(f"🔧 System: subtype={subtype} session={event.get('session_id','')[:20]}...")

        elif etype == "thinking":
            text = event.get("text", "")
            if text.strip():
                print(f"💭 {text[:200]}")

        elif etype == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", [])
            for c in content:
                ct = c.get("type", "?")
                if ct == "text":
                    print(f"💬 {c.get('text','')[:300]}")
                elif ct == "tool_use":
                    print(f"🔧 TOOL: {c.get('name','?')} input={json.dumps(c.get('input',{}))[:200]}")
                else:
                    print(f"   [{ct}] {str(c)[:200]}")

        elif etype == "tool_call":
            tc = event.get("tool_call", {})
            print(f"🔧 TOOL_CALL: {tc.get('name','?')} call_id={event.get('call_id','')[:20]}...")

        elif etype == "user":
            print(f"👤 User event")

        elif etype == "result":
            result_text = event.get("result", "")
            is_error = event.get("is_error", False)
            dur = event.get("duration_ms", 0)
            print(f"\n✅ RESULT (error={is_error}, {dur}ms): {str(result_text)[:500]}")

        elif etype == "control_request":
            req = event.get("request", {})
            print(f"\n🔒 APPROVAL REQUESTED!")
            print(f"   subtype={req.get('subtype')}")
            print(f"   tool={req.get('tool_name')}")
            print(f"   input={json.dumps(req.get('input',{}))[:300]}")
            print(f"   request_id={event.get('request_id','')}")

        else:
            print(f"[{etype}] keys={list(event.keys())[:8]}")

    await process.wait()
    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    if stderr.strip():
        print(f"\n📢 STDERR ({len(stderr)} chars):")
        print(stderr[:2000])

    print(f"\nTotal events: {count}")

if __name__ == "__main__":
    asyncio.run(main())

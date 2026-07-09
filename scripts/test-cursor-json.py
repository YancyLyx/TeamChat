#!/usr/bin/env python3
"""Test Cursor CLI --output-format stream-json. Run: python scripts/test-cursor-json.py"""

import asyncio
import json

async def main():
    # Test 1: stream-json format
    cmd = [
        "cursor-agent",
        "--print",
        "--output-format", "stream-json",
        "Say hello in one short sentence.",
    ]

    print(f"Running: {' '.join(cmd[:5])} ...")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    count = 0
    text_parts = []
    async for line in process.stdout:
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str:
            continue
        count += 1
        try:
            event = json.loads(line_str)
        except json.JSONDecodeError:
            print(f"[TEXT #{count}] {line_str[:200]}")
            text_parts.append(line_str)
            continue

        event_type = event.get("type", "unknown")
        print(f"\n[JSON #{count}] type={event_type}")
        print(f"  keys: {list(event.keys())}")
        if "text" in event:
            t = str(event["text"])[:200]
            text_parts.append(t)
            print(f"  text: {t}")
        if "result" in event:
            print(f"  result: {str(event['result'])[:200]}")
        if count <= 5:
            print(f"  full: {json.dumps(event, ensure_ascii=False)[:500]}")

    await process.wait()

    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    print(f"\nTotal events: {count}")
    print(f"Text gathered: {''.join(text_parts[:3])}")
    if stderr.strip():
        print(f"Stderr: {stderr[:500]}")

if __name__ == "__main__":
    asyncio.run(main())

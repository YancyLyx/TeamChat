#!/usr/bin/env python3
"""Test Codex CLI --json JSONL output. Run: python scripts/test-codex-json.py"""

import asyncio
import json

async def main():
    cmd = [
        "codex", "exec",
        "--json",
        "Say hello in one short sentence. Then respond with just the greeting.",
    ]

    print(f"Running: {' '.join(cmd[:4])} ...")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    count = 0
    async for line in process.stdout:
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str:
            continue
        count += 1
        try:
            event = json.loads(line_str)
        except json.JSONDecodeError:
            print(f"[TEXT #{count}] {line_str[:200]}")
            continue

        event_type = event.get("type", "unknown")
        print(f"\n[JSON #{count}] type={event_type}")
        print(f"  keys: {list(event.keys())}")
        # Show text if present
        if "text" in event:
            print(f"  text: {str(event['text'])[:200]}")
        if "content" in event:
            print(f"  content: {str(event['content'])[:200]}")
        if "result" in event:
            print(f"  result: {str(event['result'])[:200]}")
        # Show full event for first few
        if count <= 5:
            print(f"  full: {json.dumps(event, ensure_ascii=False)[:500]}")

    await process.wait()

    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    print(f"\nTotal events: {count}")
    if stderr.strip():
        print(f"Stderr: {stderr[:500]}")

if __name__ == "__main__":
    asyncio.run(main())

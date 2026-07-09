#!/usr/bin/env python3
"""Test Claude CLI stream-json mode. Run: python scripts/test-stream-json.py"""

import asyncio
import json

async def main():
    cmd = [
        "claude", "--print",
        "--verbose",
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--permission-prompt-tool", "stdio",
        "-p", "Say hello in one short sentence. Then say 'DONE'.",
    ]

    print(f"Running: {' '.join(cmd[:6])} ...")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Read stdout line by line as JSON
    count = 0
    text_parts = []
    thinking_parts = []
    tool_uses = []

    async for line in process.stdout:
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str:
            continue

        count += 1
        try:
            event = json.loads(line_str)
        except json.JSONDecodeError:
            print(f"[NON-JSON] {line_str[:120]}...")
            continue

        event_type = event.get("type", "unknown")
        print(f"\n[Event #{count}] type={event_type}")

        # Show relevant fields
        if event_type == "system":
            print(f"  session_id: {event.get('session_id', 'N/A')}")
        elif event_type == "assistant":
            content = event.get("message", {}).get("content", [])
            for item in content:
                item_type = item.get("type")
                if item_type == "text":
                    text = item.get("text", "")
                    text_parts.append(text)
                    print(f"  💬 text: {text[:200]}")
                elif item_type == "thinking":
                    thinking = item.get("thinking", "")
                    thinking_parts.append(thinking)
                    print(f"  💭 thinking: {thinking[:120]}...")
                elif item_type == "tool_use":
                    tool_name = item.get("name", "?")
                    tool_uses.append(tool_name)
                    print(f"  🔧 tool_use: {tool_name}")
        elif event_type == "result":
            result_text = event.get("result", "")
            print(f"  ✅ result: {result_text[:200]}")
            print(f"  duration_ms: {event.get('duration_ms')}")
            print(f"  usage: {json.dumps(event.get('usage', {}))}")
        elif event_type == "control_request":
            req = event.get("request", {})
            print(f"  🔒 control_request: {req.get('subtype')} tool={req.get('tool_name')}")
        else:
            # Print keys for unknown event types
            print(f"  keys: {list(event.keys())}")

    # Wait for process
    await process.wait()

    print("\n" + "=" * 60)
    print(f"Total events: {count}")
    print(f"Text parts: {len(text_parts)}")
    print(f"Thinking parts: {len(thinking_parts)}")
    print(f"Tool uses: {len(tool_uses)}")
    print(f"\nFull text: {''.join(text_parts)}")

    # Show stderr
    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
    if stderr.strip():
        print(f"\nStderr: {stderr[:500]}")

if __name__ == "__main__":
    asyncio.run(main())

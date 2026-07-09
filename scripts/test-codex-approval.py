#!/usr/bin/env python3
"""Test Codex CLI approval with concurrent stdout+stderr monitoring. Run: python scripts/test-codex-approval.py"""

import asyncio, json, sys

async def read_stream(stream, name, timeout=120):
    """Read stream line by line, print immediately."""
    count = 0
    try:
        while True:
            line = await asyncio.wait_for(stream.readline(), timeout=timeout)
            if not line:
                break
            line_str = line.decode("utf-8", errors="replace").strip()
            if line_str:
                count += 1
                try:
                    event = json.loads(line_str)
                    etype = event.get("type", "?")
                    item = event.get("item", {})

                    if etype == "item.started":
                        itype = item.get("type", "?")
                        if itype == "command_execution":
                            print(f"\n🔧 [stdout] COMMAND: {item.get('command', '')[:150]}")
                        else:
                            print(f"[stdout] item.started type={itype}")
                    elif etype == "item.completed":
                        itype = item.get("type", "?")
                        if itype == "command_execution":
                            print(f"🔧 [stdout] DONE exit={item.get('exit_code')} output={item.get('aggregated_output','')[:200]}")
                        elif itype == "reasoning":
                            print(f"💭 [stdout] {item.get('text','')[:300]}")
                        elif itype == "agent_message":
                            print(f"💬 [stdout] {item.get('text','')[:300]}")
                        elif itype == "approval_request":
                            print(f"\n🔒 [stdout] APPROVAL REQUESTED!")
                            print(f"   Item: {json.dumps(item, indent=2)[:500]}")
                        else:
                            print(f"[stdout] item.completed type={itype}")
                    elif etype == "turn.completed":
                        print(f"✅ [stdout] Turn done. usage={event.get('usage',{})}")
                    elif etype == "thread.started":
                        print(f"🧵 [stdout] Thread: {event.get('thread_id','')}")
                    elif etype == "turn.started":
                        print(f"🔄 [stdout] Turn started")
                    else:
                        print(f"[stdout] type={etype} keys={list(event.keys())}")
                except json.JSONDecodeError:
                    print(f"[stdout TEXT] {line_str[:300]}")

            # Reset timeout — we got data
            timeout = 120
    except asyncio.TimeoutError:
        print(f"\n⏰ [{name}] No output for 120s — stream may be waiting for stdin")

    return count


async def main():
    cmd = [
        "codex", "exec",
        "--json",
        "Delete the file /tmp/teamchat-test.txt if it exists. If it doesn't exist, create /tmp/teamchat-test.txt with content 'hello' then delete it.",
    ]

    print(f"Running codex exec --json ...")
    print(f"(Reading stdout + stderr concurrently. Look for approval in stderr!)")
    print("=" * 60)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Read stdout and stderr concurrently
    stdout_task = asyncio.create_task(read_stream(process.stdout, "stdout"))
    stderr_task = asyncio.create_task(read_stream(process.stderr, "stderr"))

    # Wait for both streams to finish or timeout
    try:
        done, pending = await asyncio.wait(
            [stdout_task, stderr_task],
            timeout=180,
            return_when=asyncio.FIRST_COMPLETED,
        )
        # If one stream finishes (stdout), check stderr
        for task in pending:
            task.cancel()
    except asyncio.TimeoutError:
        print("\n⏰ Overall timeout — process still running")
        try:
            process.kill()
            await process.wait()
        except:
            pass

    # Final stdout/stderr dump
    try:
        remaining_stdout = (await asyncio.wait_for(process.stdout.read(), timeout=5)).decode("utf-8", errors="replace")
        if remaining_stdout.strip():
            print(f"\n📤 Remaining stdout: {remaining_stdout[:1000]}")
    except:
        pass

    try:
        remaining_stderr = (await asyncio.wait_for(process.stderr.read(), timeout=5)).decode("utf-8", errors="replace")
        if remaining_stderr.strip():
            print(f"\n📢 Remaining stderr: {remaining_stderr[:2000]}")
    except:
        pass

    print(f"\nDone. stdout_count={stdout_task.result() if stdout_task.done() else '?'}")

if __name__ == "__main__":
    asyncio.run(main())

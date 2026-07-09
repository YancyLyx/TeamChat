#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, ".")
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient
async def main():
    cici = GitHubClient(load_config(), AGENT_CICI)
    pr = await cici.create_pr(
        title="feat: ADR-002 chat + engine --continue + greeting + tagging",
        head="feature/coco-12-collapse-dedup",
        base="main",
        body="Closes #11, closes #12\nReview: @soso咪")
    print(f"PR #{pr.number}: {pr.url}")
    await cici.close()
asyncio.run(main())

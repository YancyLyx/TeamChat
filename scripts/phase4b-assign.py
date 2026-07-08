#!/usr/bin/env python3
"""Create Phase 4b Issues for ADR-002."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    issues = [
        ("[Phase 4b] 引擎层: --continue 上下文 + 打招呼广播 + session tag",
         """## 任务
实现 ADR-002 引擎层改动，开 feature 分支 → PR → soso咪 review → merge。

### 1. AgentRunner 支持 --continue
- engine/config.py: CLI_TEMPLATES 加 continue 模式
- engine/runner.py: 首次调用普通 run()，后续调用 run_continue()

### 2. 打招呼广播
- api/routes/chat.py: 检测 "大家好/hello/hi/在吗"
- 广播给三条猫各回复一句

### 3. Session Tagging
- engine/store.py: 加 tag 字段 (prod/test)

### 4. CLI 输出解析
- engine/runner.py: 解析 Claude JSON 的 result 字段

## 实现者: cici咪""",
         ["phase-4", "engine"]),

        ("[Phase 4b] ChatRoom 前端: 折叠区 + 历史过滤",
         """## 任务

### 1. 折叠区展示
THINKING/TOOL_CALLS 标签内容默认折叠，点击展开

### 2. 历史消息过滤
只加载 tag=prod 的消息

### 3. 去重
seenMsgIds Set 防重复

## 实现者: coco咪""",
         ["phase-4", "frontend"]),

        ("[Phase 4b] E2E 测试: greeting, routing, tag filtering",
         """## 任务

### 测试场景
1. "大家好" -> 三条回复
2. "@coco咪 hello" -> 只有 coco咪
3. 无 @mention -> cici咪 分析路由
4. tag=prod 过滤

等待 cici咪 + coco咪 PR 合并后开始

## 实现者: soso咪""",
         ["phase-4", "testing"]),
    ]

    for title, body, labels in issues:
        issue = await cici.create_issue(title=title, body=body, labels=labels, assignee="YancyLyx")
        print(f"Issue #{issue.number}: {issue.title}\n   {issue.url}")

    await cici.close()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())

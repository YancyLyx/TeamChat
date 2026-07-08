#!/usr/bin/env python3
"""Create Phase 4b Issues for ADR-002 — proper workflow this time."""
import asyncio, sys
sys.path.insert(0, ".")
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient

ISSUE_ENGINE = """## 任务
实现 ADR-002 引擎层改动。每个改动独立 commit，一个分支一个 PR。

### 1. AgentRunner 支持 --continue
- `engine/config.py`: CLI_TEMPLATES 加 continue 模式
  - Claude: `["claude", "-p", "--output-format", "json", "-c", "{prompt}"]`
  - Codex: `["codex", "exec", "resume", "--last", "{prompt}"]`
- `engine/runner.py`: 新增 `run_continue()` 方法，首次用普通 run()，后续用 run_continue()
- 注意: 如果 resume 失败，回退到普通 run()

### 2. 打招呼广播
- `api/routes/chat.py`: 检测 "大家好/hello/hi/在吗"
- 广播模式: 依次调用三个 agent 各回复一句
- WebSocket 推送三条 chat_message

### 3. Session Tagging
- `engine/store.py`: 加 tag 字段 (prod/test)
- log() 方法加 tag 参数
- get_recent() 支持 tag 过滤

### 4. CLI 输出解析
- `engine/runner.py`: 解析 Claude CLI JSON 输出中的 result 字段
- 提取 thinking/tool_calls 用于 ChatRoom 折叠显示

## 工作流
1. git checkout -b feature/cici-10-engine-continue
2. git config user.name "cici咪 (Claude Architect)" && git config user.email "claude@teamchat.local"
3. 每个改动独立 commit
4. push + 创建 PR，请求 soso咪 review
5. 所有测试通过后才 merge

## 实现者
cici咪 — 引擎层改动"""

ISSUE_FRONTEND = """## 任务
基于 ADR-002，改造聊天室前端。

### 1. 折叠区展示
当 agent 回复包含 <THINKING> 或 <TOOL_CALLS> 标签时:
- 默认折叠，显示为灰色小字
- 点击展开查看详情
- <RESULT> 内容正常显示在聊天气泡中

### 2. 历史消息过滤
- 聊天室启动时加载历史，但只加载 tag=prod 的消息
- 调用 GET /api/sessions?tag=prod 而非无条件加载

### 3. 去重修复
- 用 seenMsgIds Set 防止同一 WS 消息被重复添加到聊天区
- 已在 ChatRoom.jsx 中实现，确认生效

## 工作流
1. git checkout -b feature/coco-11-chat-improvements
2. git config user.name "coco咪 (Codex Developer)" && git config user.email "codex@teamchat.local"
3. 开发 -> commit -> push -> 创建 PR
4. 请求 soso咪 review

## 实现者
coco咪 — 前端"""

ISSUE_TESTS = """## 任务
更新 E2E 测试覆盖 ADR-002 新功能。

### 测试场景
1. "大家好" -> 三条 chat_message 回复
2. "@coco咪 hello" -> 只有 coco咪 回复
3. 无 @mention "加个按钮" -> cici咪 分析 -> 系统路由消息
4. 折叠区 -> <THINKING> 内容默认不可见，点击后展开
5. tag=prod 过滤 -> 历史加载不包含测试数据

### 更新文件
- tests/test_chat.py: 新增 greeting + routing 测试
- tests/e2e_support.py: MockRunner 支持 tag 参数

## 注意
- 等待 cici咪 和 coco咪 的 PR 合并后再开始
- 或者基于他们的分支写测试，PR 指向他们的分支

## 实现者
soso咪 — QA"""

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    for title, body, labels in [
        ("[Phase 4b] 引擎层: --continue 上下文 + 打招呼广播 + session tag",
         ISSUE_ENGINE, ["phase-4", "engine"]),
        ("[Phase 4b] ChatRoom 前端: 折叠区 + 历史过滤",
         ISSUE_FRONTEND, ["phase-4", "frontend"]),
        ("[Phase 4b] E2E 测试: greeting, routing, tag filtering",
         ISSUE_TESTS, ["phase-4", "testing"]),
    ]:
        issue = await cici.create_issue(title=title, body=body, labels=labels, assignee="YancyLyx")
        print(f"Issue #{issue.number}: {issue.title}\n   {issue.url}")

    await cici.close()

if __name__ == "__main__":
    asyncio.run(main())

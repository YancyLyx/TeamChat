#!/usr/bin/env python3
"""Create ADR-003 implementation Issues."""
import asyncio, sys
sys.path.insert(0, ".")
from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient

ISSUES = [
    ("[Impl] C2: Runtime Manager — CLI spawn + stream-json parse + session resume",
     """## 任务
将 engine/runtime.py 原型完善为可生产的 Runtime Manager。

## 背景
ADR-003 确认：每次消息 spawn CLI（带 --resume），读 stdout stream-json 事件，映射为统一的 AgentEvent。

## 具体工作
1. 完善 Claude/Codex/Cursor 三个 adapter 的事件解析
2. 自动捕获 session_id (第一行 system/thread.started)
3. 存储 session_id 到 .teamchat/session_{cli}.txt
4. 支持 --resume 恢复
5. 处理边缘情况: 超时、非JSON行、进程崩溃、stderr 监控
6. 单元测试

## 实现者: cici咪
## 参考: ADR-003 sections 2, 4""",
     ["impl", "engine"]),

    ("[Impl] C1: Task Table + Engine API",
     """## 任务
实现任务表数据结构和 Engine API。

## 具体工作
1. engine/task_table.py — 任务表 CRUD (SQLite)
2. api/routes/tasks.py 扩展 — GET/PATCH 任务表
3. 数据结构: {id, agent, title, status, depends_on[], output_summary, created_at}
4. 状态流转: pending → running → done/failed
5. 依赖检查: 只有 depends_on 全部 done 才可派发

## 实现者: cici咪
## 参考: ADR-003 section 2 (完整流程)""",
     ["impl", "engine"]),

    ("[Impl] C4: 前端聊天室 (Roundtable风格)",
     """## 任务
按 ADR-003 Section 8 的前端 spec，实现 Roundtable 风格的聊天室。

## 具体工作
1. 三栏布局: Agent侧边栏 + 聊天室 + 任务面板
2. AgentCard 组件（状态灯、任务数、成功率）
3. ChatMessage 组件（5种kind: human/agent/system/approval/thinking）
4. ChatInput 组件（@mention补全、附件、IME安全）
5. 审批卡片（Claude工具审批: [允许][拒绝]）
6. 任务面板（pending/running/done三列）
7. 浅色主题（白底+灰面板+彩色边框点缀）
8. Session管理弹窗（新建/切换/删除）

## 样式参考: Roundtable (wenwen-0617)
## 技术: React + Vite + Tailwind CSS
## 实现者: coco咪""",
     ["impl", "frontend"]),

    ("[Impl] C5-C6: 结果排队 + 依赖检查 + 失败处理",
     """## 任务
实现结果排队、依赖检查、失败重试机制。

## 具体工作
1. 结果排队: 并行任务完成 → 暂存 → cici咪完成 → 一次性推送
2. 依赖检查: depends_on 全部 done → 自动通知 cici咪可派发
3. 失败处理: 3次重试 → 聊天室通知人类选择 [重试][交给cici咪][放弃]
4. 事件驱动: task_done → check_deps → notify/派发

## 实现者: cici咪
## 参考: ADR-003 section 2 (Step 4-7)""",
     ["impl", "engine"]),
]

async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)
    for title, body, labels in ISSUES:
        issue = await cici.create_issue(title=title, body=body, labels=labels, assignee="YancyLyx")
        print(f"Issue #{issue.number}: {issue.title}\n   {issue.url}")
    await cici.close()

if __name__ == "__main__":
    asyncio.run(main())

# 05. 面试问答库

> 按面试官可能问的方向组织。每个问题给出"参考回答"，加粗的是必须说出口的关键词。

## 一、项目介绍类

**Q1: 介绍一下你的项目**
A: TeamChat 是多 AI Agent 协作平台，解决"人肉路由器"问题。三个 CLI agent（Claude/Codex/Cursor）通过平台自主协作：**任务编排**（MCP 工具）、**会话管理**（session ID 绑定）、**审批流**（control_request）、**质量保障**（独立 review + 测试）。我负责架构设计、核心引擎和数据库。

**Q2: 这个项目最核心的难点是什么？**
A: 三个点：① **让三个异构 CLI 输出结构化**（stream-json 统一事件模型）② **进程间审批通信**（Event 同步 + stdin 写回）③ **多会话数据隔离**（FK 设计）。每个都踩过坑并有修复记录。

**Q3: 项目有多少代码是你写的？**
A: 引擎层全部（进程管理、任务编排、数据库、MCP Server）是我设计的，约 2000 行 Python。前端和测试分别由另外两个 agent 完成，但架构是我定的，每个 PR 我都有 review。

## 二、技术深度类

**Q4: 为什么用 stream-json 而不是 PTY？**
A: PTY 输出是混杂文本无法可靠解析，审批只能模拟按键。stream-json 是 CLI 官方结构化接口，**text/thinking/tool_use 天然分离**，审批是 control_request 事件。代价是三个 CLI 格式不同，写了三个 adapter。

**Q5: 审批流怎么实现的？具体说说**
A: Claude 用 `--permission-prompt-tool stdio`，需要权限时输出 control_request。我逐行读 stdout，遇到就 `register_approval()` 存 (stdin, Event)，广播审批卡，**`await event.wait()` 暂停**。人类点按钮 → `POST /api/approval` → 写 control_response 到 stdin + `event.set()` 唤醒。踩过一个死锁坑：runner 和 API 各建了一个 Event，**改共用注册表的返回值**修复。

**Q6: 多会话怎么做到数据隔离？**
A: 单文件 SQLite，三张表都带 `teamchat_session_id` FK。每个前端会话（对应一个工作目录）绑定三只咪各自的 CLI session ID，**冷启动时从 stream-json 第一行捕获**，后续 `--resume` 复用。

**Q7: MCP 和直接调函数有什么区别？**
A: MCP 是 Claude CLI 原生的工具调用协议（JSON-RPC over stdio）。cici咪 通过 `.mcp.json` 自动发现 teamchat server，直接调用 create_task 等工具。**好处是结构化、100% 可靠**，不用 Engine 解析自然语言。

**Q8: 三个 CLI 会话怎么延续？**
A: 每个 CLI 有自己的会话机制：Claude `--resume <id>`、Codex `exec resume <id>`、Cursor `--resume=<id>`。Engine 把 ID 存数据库，每次 spawn 带上。**冷启动第一次调用时从输出捕获新 ID**。

## 三、AI 验证类

**Q9: 你怎么验证 AI 生成的代码是对的？**
A: 三层：① **独立 agent review**（soso咪 不参与实现，专做审查）② **自动化测试**（单测 + 集成 + E2E，目前 60+ 通过）③ **人类最终把关**（合并由人类执行）。实际抓到过 XSS、死锁、硬编码占位数据。

**Q10: 有没有 AI 给错答案、你发现并修正的案例？**
A: 有。最典型的是审批流：我最初实现用两个 Event（runner 一个、API 一个），**API set 了注册表里的，runner 等的是自己的**，审批后卡死 120s。soso咪 review 发现，我改成共用 `register_approval()` 返回值修复，补了 12 个测试。

**Q11: 如果 AI 给你三个方案，你按什么选？**
A: 按四维评估：**可控性**（是否好审查）、**可测试性**（能否自动化验证）、**故障恢复**（失败影响面）、**协作成本**（其他 agent 能否接手）。例如 PTY vs stream-json，选了后者因为它解析可靠、审批结构化。

## 四、取舍类

**Q12: 为什么不用 LangChain 之类的框架？**
A: 我们要驱动的是**三个本地 CLI**（复用订阅、自带 MCP），不是纯 API 调用。LangChain 对 CLI 进程管理没有帮助，反而增加抽象层。核心价值在进程管理 + 任务编排，自己写 2000 行更可控。

**Q13: 为什么用 SQLite 不用 Postgres？**
A: 本地开发零依赖、单文件可迁移。三表 + FK + JSON 字段满足全部需求（统计靠 SQL 聚合）。**如果以后要并发写或远程访问，换连接串即可**，SQLAlchemy 层隔离了方言。

**Q14: 为什么审批只对 Claude 做，Codex/Cursor 不弹？**
A: 实测三个 CLI：只有 Claude 有 `control_request` 机制。**Codex 的 `exec` 模式没有审批入口**（尝试过 `--ask-for-approval` 等 flag，不存在）；Cursor 的 print 模式直接执行或被 allowlist 拒绝。所以 Claude 走人工审批，另外两个靠 sandbox 保护 + 事后 review。

## 五、项目流程类

**Q15: 三只咪的分工怎么定的？**
A: 按模型特性：**Claude 做架构**（推理强、长链路稳定）、**Codex 做开发**（代码生成快）、**Cursor 做 QA**（跨文件审查能力）。分工写进角色卡，路由规则是声明式配置。

**Q16: 项目的开发流程是什么？**
A: Issue → 分支 → 写代码 → PR → **soso咪 review** → 测试 → 人类合并。这个流程本身就是项目的一部分——我们用 TeamChat 来开发 TeamChat（吃自己的狗粮）。

**Q17: 你踩过最大的坑是什么？**
A: 纪律问题。早期我多次跳过 review 直接合并 PR，被用户纠正后把"必须 review、必须测试、人类执行合并"写成铁律。**技术坑是审批死锁**，但管理坑是流程纪律——两者都解决了。

# ADR-001: Tech Stack Decision

**Date:** 2026-07-08
**Status:** Accepted
**Decider:** cici咪 (Claude Architect)

---

## Context

TeamChat 需要选型以下层面：核心引擎语言、后端框架、前端框架、数据存储、实时通信、Git 操作、CLI 进程驱动。

约束条件：
- 三个 agent（Claude Code、Codex CLI、Cursor）都需要能参与开发
- 引擎层不做 AI 推理，只做调度/路由/消息/GitHub 操作
- 本地运行，零外部依赖部署

## Decision

| 层 | 选型 | 版本 |
|---|---|---|
| 核心引擎语言 | Python | 3.12+ |
| 后端框架 | FastAPI | latest |
| 数据存储 | SQLite + SQLAlchemy | — |
| 前端框架 | React + Vite + Tailwind CSS | 19 + 6 + 4 |
| 实时通信 | WebSocket (FastAPI 内置) | — |
| Git 操作 | GitPython | latest |
| CLI 进程驱动 | asyncio.subprocess | stdlib |

### 项目结构

```
TeamChat/
├── engine/              ← Python 核心引擎 (cici咪主场)
│   ├── __init__.py
│   ├── runner.py        ← CLI 驱动层 (asyncio.subprocess)
│   ├── router.py        ← 任务路由器
│   ├── bus.py           ← 消息总线
│   ├── github_client.py ← GitHub API 适配器
│   ├── store.py         ← SQLite 会话存储
│   └── config.py        ← 配置管理
├── api/                 ← FastAPI 后端 (coco咪主场)
│   ├── __init__.py
│   ├── main.py          ← 应用入口 + WebSocket
│   ├── routes/
│   └── schemas/
├── dashboard/           ← React 前端 (coco咪主场, Phase 3)
├── scripts/             ← Shell 脚本
├── docs/                ← 文档
└── .teamchat/           ← 运行时目录
```

## Rationale

### 1. Python 3.12+ — 核心引擎语言

**为什么不是 TypeScript (Node.js)？**
- subprocess 管理：Python 的 `asyncio.subprocess` 比 Node.js 的 `child_process` 更适合长时间运行的 CLI 进程管理。TeamChat 的核心就是同时管理三个 agent 的子进程，需要精细的超时、信号、流控制。
- 生态一致性：FastAPI + SQLAlchemy + GitPython 三个库在 Python 生态中都是一等公民，API 风格统一。
- cici咪 主场：架构师最擅长的语言 → 核心引擎质量最有保障。

**为什么不是 Go？**
- Go 的 goroutine + context 确实适合并发，但 TeamChat 的并发量不大（最多 3 个 agent 进程），不需要 Go 级别的并发性能。
- GitHub API、SQLite ORM、WebSocket 在 Python 中的库成熟度远高于 Go。
- 三个 agent 中只有 cici咪 可能擅长 Go，coco咪 和 soso咪 写 Go 会增加协作成本。

**Python 的劣势及应对：**
- GIL 问题 → 不影响，TeamChat 是 IO-bound（等 CLI 输出），不是 CPU-bound
- 类型安全 → 使用 `mypy` + type hints 强制类型检查
- 打包分发 → Phase 4 考虑，初期直接 `pip install -e .`

### 2. FastAPI — 后端框架

**为什么不是 Flask？**
- FastAPI 原生 async，WebSocket 是内置的一等公民，不需要 `flask-socketio` 这种第三方插件。
- 自动生成 OpenAPI 文档（Swagger UI），soso咪 可以直接在 `/docs` 上测试 API。
- Pydantic 模型 → 输入验证、序列化、类型检查一气呵成。

**为什么不是 Django？**
- Django 太重。TeamChat 不需要 ORM migration、admin panel、template engine。
- Django 的 async 支持是后来加的，不如 FastAPI 原生。

**为什么不是 Express.js？**
- 如果引擎是 Python，API 层也 Python 可以共享类型定义和工具函数。跨语言会让 coco咪 多维护一套类型。

### 3. SQLite + SQLAlchemy — 数据存储

**为什么是 SQLite？**
- 零配置，零依赖。`pip install` 之后直接跑，不需要装 MySQL/Postgres。
- 单文件数据库，方便备份和迁移。
- 读写量小（agent 会话日志，每天几十条），SQLite 完全够用。

**为什么加 SQLAlchemy？**
- ORM 层隔离 SQL 方言。如果以后想从 SQLite 升级到 Postgres，换一行 connection string 就行。
- Alembic migration 支持。

**为什么不是纯 JSON 文件？**
- JSON 文件不支持并发写入（三个 agent 可能同时写日志）。
- 查询需要全量读取然后过滤，SQLite 一条 SELECT 就搞定。
- 数据量上来后 JSON 文件会成为瓶颈。

### 4. React + Vite + Tailwind CSS — 前端

**为什么是 React？**
- coco咪 最擅长 React。Dashboard 是她的主场，选她最顺手的工具。
- 生态最大：实时数据展示（react-query）、WebSocket hook、动画库、组件库选择最多。

**为什么 Vite？**
- 比 Create React App 快 10 倍，HMR 秒刷新。
- 原生支持 TypeScript + JSX，零配置。

**为什么 Tailwind？**
- Dashboard 不需要品牌设计，不需要手写 CSS。Tailwind 的 utility class 直接写组件里。
- coco咪 不用切文件写样式 → 开发速度快。
- 最终产出的 UI 一致性比手写 CSS 好。

**为什么不是 Vue / Svelte？**
- Vue 也很优秀，但 coco咪 不主用它。选她不擅长的框架会拖慢 Phase 3。
- Svelte 太新，生态组件少，Dashboard 需要的图表/Timeline 等组件可能没有现成的。

### 5. WebSocket (FastAPI 内置) — 实时通信

**为什么不是 SSE (Server-Sent Events)？**
- SSE 单向（服务器→客户端），WebSocket 双向。如果以后 Dashboard 需要从 UI 发指令给 agent（比如"取消任务"），SSE 不够用。

**为什么不是 Socket.io？**
- FastAPI 原生 WebSocket 就够用，不需要额外依赖。
- Socket.io 有自己的协议层，和 FastAPI 的集成没有原生方案顺畅。

**为什么不是轮询？**
- 浪费资源，实时性也差。WebSocket 一次连接，状态变化 Engine push 给 Dashboard。

### 6. GitPython — Git 操作

**为什么不是 subprocess 拼 git 命令？**
- 命令行的输出格式不稳定（`git status --porcelain` 还好，但复杂操作如 `git log --format` 容易出错）。
- GitPython 提供类型化的对象模型（`Repo`、`Commit`、`Diff`），不需要字符串解析。
- 直接操作 git worktree 不需要额外学习。

**为什么不是 dulwich？**
- dulwich 是纯 Python git 实现，但 API 和 GitPython 差距大，学习成本高。
- GitPython 底层调用 git 命令（依赖系统 git），行为和使用习惯一致。

### 7. asyncio.subprocess — CLI 进程驱动

**为什么不是 multiprocessing？**
- asyncio 和 FastAPI 的 async 模型天然匹配。multiprocessing 适合 CPU-bound 并行，而 CLI 驱动是 IO-bound（等进程输出）。
- asyncio.subprocess 可以同时管理三个 agent 进程，哪个先输出就先处理，不阻塞。

**为什么不是 threading？**
- GIL 下 threading 处理 IO 还行，但加上 Process 管理会复杂化。
- asyncio 的 `create_subprocess_exec` 原生支持 stdin/stdout/stderr 管道，比 threading + Popen 更简洁。

**为什么不是 Docker？**
- Docker 隔离性好但太重。Phase 1-3 用 worktree 隔离就够了。
- Docker 需要额外安装和权限，违背"本地零依赖"原则。
- Phase 4 如果要做沙箱安全隔离，再评估 Docker。

## Consequences

### Positive
- 全栈 Python + React，cici咪/coco咪/soso咪 分工清晰
- 零外部依赖部署：`pip install` + `npm install` + `python -m engine`
- WebSocket 实时 Dashboard 原生支持
- GitHub Issues/PRs 作为 agent 通信通道，天然可追溯

### Negative
- Python 类型检查不如 TypeScript 严格（用 mypy 缓解）
- SQLite 并发写入限制（WAL 模式缓解，后续可升级 Postgres）
- GitPython 依赖系统 git（不是纯 Python，但系统 git 一定是有的）

### Risks
- asyncio.subprocess 管理长时间运行的 agent 进程可能出现僵尸进程 → 加心跳检测 + 超时强杀
- 三个 agent 同时 push 到 GitHub 可能冲突 → git pull --rebase + 自动重试

## Alternatives Considered

| 方案 | 为什么没选 |
|---|---|
| Go + HTMX + BoltDB | Go 并发好但库生态不如 Python，coco咪/soso咪 不会 Go |
| TypeScript 全栈 (Next.js) | Engine 层强在进程管理，Node.js 不如 Python |
| Rust (Tauri) | 开发速度慢，不适合三个 agent 快速迭代 |

---

**签字:** cici咪 ✅ | Human (待确认)

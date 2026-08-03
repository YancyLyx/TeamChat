# PROGRESS

> Last updated: 2026-08-03

## 当前

Phase: ADR-005 Phase 4.0 **端到端验证通过**（2026-08-01 本地）。协作闭环真实跑通：发任务 → 派发 → agent 执行 → 回流 → cici咪 审核 → done。

**2026-08-03 新增：** Tasks 看板本地实现完成（coco咪）：右侧栏默认展示、Running/Waiting/Pending/Done/Failed 分组、依赖标签、失败重试/转派/放弃、按 agent 筛选、`task_table` 创建/更新 WebSocket 实时刷新（#16→#19→#17→#23 链路）。

**2026-08-03 新增：** Stats 面板 L3 接入 `/api/stats.l3`（#30 P0）：App 保留并透传 l3，StatsPanel 展示自动化率/人工介入/消息→完成/审批次数。

**✅ 2026-08-03 阻塞项已全部解决（#18 收尾确认）：**
- P2 Failed 文案：guard 已移除（#25 soso咪 转派落地），TestErrorState 通过 ✅
- **coco咪 codex 会话早退根因（#26）**：线程 019fbc3b 反复 resume 膨胀至 ~6M input tokens（≥3.5M 后模型只回计划即退）→ 已修复：dispatch.py 加 codex 会话轮换（8 次 resume 自动冷启动，仅 codex）+ session 2 codex_id 已立即重置（下次任务冷启动新线程）；**需重启引擎进程使轮换代码生效**
- P2 可选：@mention busy 排队建任务走 watchdog 2s 延迟广播（已接受，不追任务）

## 📋 复盘教训（2026-08-03 Tasks 看板开发，用户要求记录）

1. **标记 done 前必须验证改动落盘**（git diff / 文件 mtime）— 本轮我手动标记 #20/#21/#24 done 未验证，cici咪 收尾抓出"连续三次宣布→早退→被标记 done"，掩盖了 codex 早退 3 次。**教训：Engine 进程（人工或 cici咪）标记 done 前先核对文件变化。**
2. **改引擎代码后必须重启进程** — cici咪 #26 修复轮换逻辑落盘，但运行中的 uvicorn 是旧代码（无自动 done/轮换），导致 #26 卡 running。**教训：引擎改动后重启生效。**
3. **agent 会话要轮换** — codex 单线程长期复用会膨胀（3.1M→6M tokens）导致幻觉完成/早退。已修（8 次轮换）。
4. **前端同步依赖 WS 广播** — 任务状态变化（done/abandoned）前端可能延迟显示，原因：MCP 跨进程写库不广播（已修 watchdog）+ 旧进程不加载。
5. **"失败任务显示"区分** — failed 可能是 cici咪 审核判定（早退未落盘）而非 exit_code 失败，前端显示"执行失败"易误导。

### 测试污染 agent_calls（2026-08-03 事件 + 清理）

**事件**：soso咪 #33 测试污染**真实 agent_calls**（1326 mock 输出 + 230 approval 模拟 + e2e_seed），导致 L1 显示 coco咪 1530 tasks、聊天历史被 mock 挤占。
**清理**：删除 mock/e2e_seed/approval 记录（保留真实 chat_message/chat_analysis/scheduled_task，历史完整恢复）。
**防护缺口**：防污染只覆盖 task_table（TaskScheduler 拒短 description），**e2e 测试的 store.log 未隔离**——需补：conftest e2e_servers 的 store 也用 e2e_root（tmp_path），禁止写真实 DB。

### Tasks 面板待改进（用户要求，2026-08-03）

- Done 列表倒序（最新在前）+ 默认显示 5 个 + 折叠展开全部
- Failed 列表：转派后的原任务（如 #21 → #25）应从 Failed 移除/标记"已转派"
- 失败按钮（重试/转派/放弃）是**用户兜底/手动干预**功能：自动链路（引擎重试→cici咪 审核三选项）正常时用不到；场景：cici咪 审核未触发/用户主动干预/不同意 cici咪 判定
- #8 放弃按钮"没响应"待排查（数据库已 abandoned，前端未即时刷新）

## ⚠️ 阻塞

**GitHub 账号 YancyLyx 被暂停**（2026-08-01 发现，用户申诉中）。所有 GitHub 操作不可用（push/merge/gh）。本地开发不受影响。

## 📦 双远程仓库（2026-08-01 起）

| 远程名 | 地址 | 用途 | 状态 |
|---|---|---|---|
| `origin` | `git@github.com:YancyLyx/TeamChat.git` | 主仓库（恢复后继续用） | ⏸ GitHub 暂停 |
| `gitee` | `https://gitee.com/Lxunxun/TeamChat.git` | 备份/保险（GitHub 恢复前的版本管理） | ✅ 已同步 main + 46 分支 |

**约定**：
- push 时**显式指定远程**：`git push gitee main` / `git push origin main`（不用 `-u`，保持 origin 为默认上游）
- 本地 main 最新状态（含 Phase 4.0 完整落地 + 验证修复 + Phase 4.1 Adapter）已在 gitee/main
- GitHub 恢复后：`git push origin main` 无缝切回；不要 gitee 可 `git remote remove gitee`
- 保险锚点：Phase 4.2 开始前建议 `git tag phase4-complete-20260801 && git push gitee phase4-complete-20260801`（回退用 `git reset --hard phase4-complete-20260801`）

### GitHub 恢复后的处理清单（用户告知恢复后执行）

1. **push 本地 main**（含以下本地提交）：
   - `32790ed` feat: 失败自动重试（PR #95，已本地合并）
   - `eaabf33` fix: claude --allowedTools（MCP 权限）
   - `20852e1` fix: MCP create_task session 硬编码
   - `9cdb3e2` feat: strip 兄弟 token + 重试审计
   - 各 docs 提交（PROGRESS/ADR 更新）
2. **处理 PR #95**：已本地合并 → GitHub 上关闭（或 push 后 close）
3. **revoke + 重生成 3 个 PAT**（已暴露在对话，必须换）→ 更新 `~/.zshrc`
4. **验证 push 后无冲突**，跑一遍单元测试确认
5. 后续：Phase 4.1 GitHub Adapter 才能实测（Webhook/Issue 同步）

## ✅ 本轮已完成（本地 main）

| 日期 | 内容 | PR/说明 |
|---|---|---|
| 08-01 | PR #93: runner 注入 git 身份 + PAT（已合并） | #93 |
| 08-01 | PR #94: Task Scheduler + Result Relay 协作闭环（已合并） | #94 |
| 08-01 | PR #95: 失败自动重试（已 review 通过，GitHub 暂停未合并，**已本地合并到 main**） | #95 |
| 08-01 | **端到端验证通过**（session 2 闭环验证）：任务 #3 soso咪 完整闭环 done；发现并修复 MCP 权限（--allowedTools） | 本地 |
| 08-03 | Tasks 看板：`TasksBoard.jsx` 接入右侧栏；`/api/tasks/table` 创建/更新广播 `task_table_updated`；新增 API 广播单测与 Tasks 看板 E2E 用例 | 本地 |
| 08-01 | codex resume --sandbox 参数位置修复（引擎 #12：resume/continue 路径改 `-c sandbox_mode="workspace-write"`，冒烟验证 ✅，待 soso咪 review） | 本地 |
| 08-01 | **/api/chat 链路验证通过**：发消息→分析→create_task→session 修正→派发→执行→回流→审核→done（#4 #5）；发现并修复 MCP create_task session 硬编码 1 | 本地 |
| 07-31 | PR #92: mdRender 重复声明修复（已合并） | #92 |
| 07-31 | PR #80: 关闭（已过时） | - |
| 07-31 | 更新 cici咪 session ID | - |
| 07-31 | ADR-005 Phase 4 完整规划 | decisions/005 |

## 数据库

- 1 个文件: `.teamchat/teamchat.db`
- 3 个表: `teamchat_sessions` / `agent_calls` / `task_table`
- ADR-003 §10

## 待办

| 内容 | 谁 | 优先级 |
|---|---|---|
| GitHub 恢复后：push main（含 PR #95 重试 + --allowedTools 修复）+ 关 PR #95 + revoke 重生成 PAT | cici咪/人类 | 高 |
| Dashboard UI 发消息验证（当前用 curl 测 /api/chat 通过，未测浏览器 UI） | cici咪 | 中 |
| PR #95 备注: 中间重试写入 agent_calls（完整审计） | cici咪 | 中 |
| runner 备注: strip 兄弟 agent 的 TEAMCHAT_*_TOKEN | cici咪 | 中 |
| 数据库优化: agent_calls 大文本外置（prompt/output 存文件）+ 历史归档（阈值 ~10 万行触发，现无需急） | cici咪 | 低 |
| chat.py is_busy 排队路径测试（@agent 排队/无@mention 排队/greeting 跳过） | cici咪 | 中 |
| ~~codex 写文件权限~~ ✅ 已修复（#12，代码已改+冒烟验证，待 review 合并） | cici咪 | - |
| 测试批跑顺序污染：15 失败（task_scheduler/claude_approval_stream/unicode_api；单测通过、批跑失败），待排查 | soso咪 | 中 |
| Phase 4.1 GitHub Adapter（依赖 GitHub 恢复） | cici咪 | 低 |

## 验证记录（2026-08-01）

- 2026-08-03：Tasks 看板新增 API 广播单测并通过；新增 E2E 用例（沙箱禁止监听端口，需在非沙箱环境执行），详见 `docs/TEST-PLAN.md` TC-H8/H9。

- session 2「闭环验证」：cici咪 claude_id=c3dd3766（冷启动捕获），coco咪 codex_id=019fbc3b
- 任务 #2 (coco咪)：手动模拟审核 → update_task(2, done) ✅
- 任务 #3 (soso咪)：**真实闭环** → 派发 → cursor 执行 → 回流 → cici咪(--resume) 审核 → update_task(3, done) ✅
- 任务 #4/#5：**/api/chat 完整链路** → 发消息 → cici咪 分析 → create_task → session 修正 → 派发 → 执行 → 回流 → 审核 → done ✅
- 修复 1：claude MCP 工具权限（workspace 未信任时 settings.json 失效，--allowedTools 参数生效）
- 修复 2：MCP create_task 任务 teamchat_session_id 硬编码 1 → chat.py 分析后修正为当前 session
- Phase 4.2 两轮完善：soso咪 审查通过（92 passed）；修复其建议的 ①无@mention mark_busy 竞态窗口 ②update_task 循环复检。测试计数口径：92（6 文件）vs 100（7 文件含 approval）
- **Phase 4.2 闭环验证通过**（session 2 真实 CLI，2026-08-01）：DAG 建模/依赖顺序派发/排队/审核/追加修复任务(#11)/blocked_by_failure/update_task 改依赖解锁，全部验证 ✅
- 验证发现环境问题：codex 会话文件系统只读（sandbox 拒写），写文档类任务失败 → 记待办；**已修复**（#12：resume 路径 `--sandbox` 位置错误 → 改 `-c sandbox_mode="workspace-write"`，2026-08-01 冒烟测试：写文件命令 exit 0 ✅）

## 铁律更新

- **cici咪 不再执行 `gh pr merge`** — 合并由人类执行
- GitHub 暂停期间：本地开发正常，不 push

## ⚠️ 教训：Engine spawn agent 与用户终端共享工作区（2026-08-01）

**事件**：Engine spawn 的 cici咪 执行任务 #12 时，`git checkout -b feature/cici-codex-resume-sandbox` 创建了分支并在上面 commit（config.py 修复 + 测试），而用户终端的 cici咪（本会话）同时在 main 上工作 → git 状态混乱，差点丢修改。

**根因**：所有 agent（Engine spawn + 用户手动终端）共享同一工作目录和 git 仓库（ADR-005 曾规划 Git Worktree 隔离，降级为"未来考虑"）。

**第二次事故（2026-08-02）**：Engine spawn 的 cici咪 执行 `git checkout gitee/feature/cici-codex-resume-sandbox`（审查分支任务时），导致 detached HEAD + 工作区回退（Phase 4.5 修改看似丢失）。恢复：checkout main（引用未损）。已删除 gitee 远程分支防止再切。

**临时缓解**（已升级）：
- prompt 明确**禁止执行任何 git 命令**（checkout/branch/reset/switch/commit/push 等）——共享工作区，git 操作由人工统一管理
- 删除了可疑的 gitee 远程分支引用

**长期方案**：Git Worktree 隔离（PROGRESS 待办，需并发需求时实施；或 Engine spawn agent 时限制 git 权限）

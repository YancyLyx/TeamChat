# PROGRESS

> Last updated: 2026-08-01

## 当前

Phase: ADR-005 Phase 4.0 **端到端验证通过**（2026-08-01 本地）。协作闭环真实跑通：发任务 → 派发 → agent 执行 → 回流 → cici咪 审核 → done。

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
| Tasks 看板（前端，ADR-003 §8.2 [📋 Tasks] tab 待实现；数据已加载未渲染） | coco咪 | 中 |
| Phase 4.1 GitHub Adapter（依赖 GitHub 恢复） | cici咪 | 低 |

## 验证记录（2026-08-01）

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

**临时缓解**（已实施）：
- Engine spawn 的 cici咪 任务 prompt 增加提示："不要创建 git 分支、不要 git commit/push（代码修改请直接改文件，由人工统一提交）"

**长期方案**：Git Worktree 隔离（PROGRESS 待办，需并发需求时实施）

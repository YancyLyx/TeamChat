# ADR-006: TaskScheduler 并行派发（#96）

**状态**: Draft → 实施中（2026-08-04）
**日期**: 2026-08-04
**作者**: cici咪
**关联**: ADR-005（Phase 4.2 任务编排）、03 文档 §3.6

---

## 背景与动机

用户场景：DAG 中多个**无依赖关系**的任务分派给**不同 agent**（如 A → coco咪、B → soso咪，C 依赖 A+B），期望 A、B 并行执行，总耗时 = max(A, B) 而非 A+B。

现状：`TaskScheduler.run()` 主循环**顺序派发**：

```python
unblocked = self.task_table.unblocked_tasks()   # 依赖全部完成的 pending 任务
for task in unblocked:
    if agent 空闲 and not _should_defer(task):
        await self._dispatch(task)              # ⚠️ 等 agent 跑完才轮到下一个
```

`_dispatch` 内部 `await self._spawn_with_retry(...)`（单任务最长 300s 超时）。因此即使两个任务分属不同 agent、互不依赖，也会被顺序执行——第二个任务白白等待第一个任务的整个执行时间。实测场景：多分支需求（前端 + 测试两个分支）总耗时 = 各分支之和，而非最慢分支。

## 目标

- 不同 agent 的独立任务可**并行**执行（同时 running）
- 保持既有语义不变：同一 agent 串行（CLI session 并发写保护）、忙时排队、_should_defer 延迟派发、结果回流审核、重试逻辑

## 现状分析（相关代码）

| 位置 | 现状 |
|---|---|
| `task_scheduler.py::run()` | `for task in unblocked: await self._dispatch(task)` 顺序 await |
| `task_scheduler.py::_dispatch()` | 内部 `mark_busy` → `await _spawn_with_retry` → `mark_free`；同 agent 并发由 busy 检查防住 |
| `_should_defer()` | cici咪 busy 期间创建的任务延迟到 cici咪 空闲（避免 task_started 早于 cici咪 回复） |
| `unblocked_tasks()` | 依赖全部完成的 pending 任务列表 |

## 方案设计

### 并发派发

`run()` 主循环改造：每个轮询周期，收集"agent 空闲 + 不 defer"的 unblocked 任务，**并发派发**：

```python
unblocked = self.task_table.unblocked_tasks()
dispatchable = []
for task in unblocked:
    agent = self._find_agent(task.agent)
    if agent and not self.router.is_busy(agent) and not self._should_defer(task):
        dispatchable.append(task)
# 并发派发：每个任务独立 coroutine，单个失败不拖垮整轮
results = await asyncio.gather(
    *(self._dispatch(t) for t in dispatchable),
    return_exceptions=True,
)
for r in results:
    if isinstance(r, Exception):
        logger.error(f"Scheduler parallel dispatch error: {r}")
```

### 关键设计点

1. **同 agent 串行天然保持**：筛选阶段排除 busy agent；`_dispatch` 内 `mark_busy` 后同 agent 不再进入下一轮（同一轮内同 agent 的任务只会被选一次——`is_busy` 在筛选循环中逐个检查，第一个选中的任务 mark_busy 前，后续同 agent 任务仍可能被选中！）

   ⚠️ **竞态（必须在实现中处理）**：`for task in unblocked` 筛选循环里，如果 unblocked 里有**两个同 agent 的任务**（如 coco咪 任务 A1、A2 都 unblocked），第一个 `is_busy` 检查通过后**尚未 mark_busy**，第二个同样通过检查 → 同 agent 双派发，破坏"同 agent 串行"。
   
   **解法**：筛选循环内选中一个任务后**立即 `mark_busy(agent)`**（把 busy 标记提前到筛选阶段，与聊天室路径的"检查与标记之间不允许 await"同一原则）；`_dispatch` 内部不再重复 mark_busy（或幂等处理）。若后续 `_dispatch` 因异常提前返回，`finally` 里必须 `mark_free`——注意筛选阶段标记的 busy 要在**所有**并发 coroutine 结束后统一释放，而不是各自 finally 释放（否则一个任务结束就把同 agent 另一个任务的 busy 标记清掉）。
   
   **更简单的方案**：筛选时按 agent 去重——每个 agent 每轮只取**一个** unblocked 任务。同 agent 的第二个任务自然留到下一轮（等第一个完成、busy 释放后）。这样 busy 管理完全不动，`_dispatch` 无需改动。
   
   **决策：按 agent 去重**（每轮每 agent 最多派发 1 个任务）——最小改动、无竞态、行为可预期。代价：同 agent 的 N 个无依赖任务仍逐轮串行（每轮 2s 轮询间隔 + 执行时间）——符合"同 agent 串行"的既有约束。

2. **并发上限**：每轮最多 3 个（3 个 agent 各一个），天然受限，无需额外并发控制。

3. **广播顺序**：task_started 广播在 `_dispatch` 内各自进行，并发下到达顺序可能交错——前端按任务 id 渲染，无影响；Stats 计数按 DB 聚合，无影响。

4. **异常隔离**：`return_exceptions=True`——单个任务 spawn 异常（如 CLI 缺失）只记录日志，不打断其他任务的派发和本轮循环。

5. **ResultRelay 回流**：每个任务独立 `relay()`，并发下审核队列按完成顺序排队——cici咪 审核仍是串行的（决策者单线程），不受影响。

### 不做的事

- 不做"跨 agent 并行上限调节"（每 agent 多任务并发）——超出本需求，且 CLI session 并发写风险
- 不改 chat.py 的打招呼 gather（已是并行）
- 不做任务级优先级调度

## 测试计划

| 测试 | 内容 | 位置 |
|---|---|---|
| 单元：不同 agent 并行 | mock runner，建 coco咪 + soso咪 各 1 个 unblocked 任务，断言两个 spawn **同时开始**（两个 coroutine 都在对方完成前启动） | `tests/test_task_scheduler.py` |
| 单元：同 agent 不并行 | coco咪 2 个 unblocked 任务，断言第二个等第一个完成后才 spawn | 同上 |
| 单元：单任务异常不拖垮整轮 | 一个任务 spawn 抛异常，断言另一个任务正常完成、循环继续 | 同上 |
| 回归 | 全量套件 `pytest tests/ -q`（172+ passed） | - |
| 端到端验收 | 建 A(coco)、B(soso)、C(depends_on A+B) → 观测 A、B 同时 running，C 等两者 done 后派发 | 人工（用户同意后） |

## 验收标准

1. 两个不同 agent 的独立任务并行启动（单测断言）
2. 同 agent 任务仍串行（单测断言）
3. 单个任务失败不影响并行同伴和后续轮询（单测断言）
4. 全量套件通过，无回归
5. 端到端：多分支需求总耗时 ≈ 最慢分支（而非各分支之和）

## 影响面

- `engine/task_scheduler.py`：run() 循环 + 筛选逻辑（按 agent 去重）
- 测试：`tests/test_task_scheduler.py`（新增）
- 文档：通过验收后更新 `docs/interview/03-core-techniques.md` §3.6 详细版（现状 → 并行已实现）

## 追踪

- 编号：#96（commit message 统一带 `#96`）
- 阶段 commit：`docs(adr): #96 设计` → `feat(scheduler): #96 并行派发` → `test(scheduler): #96` → `docs(interview): #96 3.6 更新`（验收后）
- push：攒批，用户同意后统一执行

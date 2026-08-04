"""#96 真实 e2e 验收 — 连真实引擎（uvicorn 运行中），建 A/B/C 任务，观测并行派发。

- 任务通过 TaskTable 直接写入真实 DB（scheduler 的 watchdog 会广播，前端看板实时可见）
- A(coco咪)、B(soso咪) 独立并行；C(coco咪) depends_on [A, B]
- 全程轮询打印状态流转；由真实 TaskScheduler 派发、真实 CLI 执行、真实 cici咪 审核
- 验收后任务标记 abandoned（保留记录，不再派发）
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import Config
from engine.task_table import TaskTable

ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = 2  # 当前活动 session（与历史任务一致）

A_PROMPT = "请用一句中文回复：并行验收任务A完成（只回复这一句，不要做其他事）"
B_PROMPT = "请用一句中文回复：并行验收任务B完成（只回复这一句，不要做其他事）"
C_PROMPT = "请用一句中文回复：并行验收任务C完成（只回复这一句，不要做其他事）"


def main() -> int:
    config = Config(repo_owner="YancyLyx", repo_name="TeamChat",
                    repo_url="https://github.com/YancyLyx/TeamChat", project_root=ROOT)
    tt = TaskTable(config)
    tt.init()

    # 检查是否已有残留验收任务（上次中断）
    existing = [t for t in tt.list_tasks()
                if t.title in ("E2E-A", "E2E-B", "E2E-C")]
    if existing:
        print("⚠️ 发现残留验收任务，先标记 abandoned 清理")
        for t in existing:
            tt.update(t.id, status="abandoned",
                      output_summary="e2e cleanup (rerun)")

    a = tt.create(agent="coco咪", title="E2E-A", description=A_PROMPT,
                  teamchat_session_id=SESSION_ID)
    b = tt.create(agent="soso咪", title="E2E-B", description=B_PROMPT,
                  teamchat_session_id=SESSION_ID)
    c = tt.create(agent="coco咪", title="E2E-C", description=C_PROMPT,
                  depends_on=[a.id, b.id], teamchat_session_id=SESSION_ID)
    print(f"已创建: #{a.id} A(coco咪) / #{b.id} B(soso咪) / #{c.id} C(依赖A,B)")

    started_at = time.monotonic()
    last_line = ""
    t0 = tt.get(a.id).created_at
    while time.monotonic() - started_at < 420:  # 最多 7 分钟
        ta, tb, tc = tt.get(a.id), tt.get(b.id), tt.get(c.id)
        line = (f"[{int(time.monotonic()-started_at):>3}s] "
                f"A:{ta.status}  B:{tb.status}  C:{tc.status}")
        if line != last_line:
            print(line, flush=True)
            last_line = line
        if tc.status == "done":
            print("🎉 C done — 验收链路完整走通")
            break
        time.sleep(2)

    ta, tb, tc = tt.get(a.id), tt.get(b.id), tt.get(c.id)
    print("=" * 56)
    print(f"真实 e2e 验收结果（session {SESSION_ID}）")
    print("=" * 56)
    print(f"  A #{a.id} (coco咪): {ta.status}")
    print(f"  B #{b.id} (soso咪): {tb.status}")
    print(f"  C #{c.id} (coco咪, 依赖A+B): {tc.status}")
    ok = tc.status == "done" and ta.status == "done" and tb.status == "done"
    print("验收结论:", "PASS ✅（真实 CLI 全链路）" if ok else "INCOMPLETE ⚠️ 见上方状态流转")

    # 清理：验收任务标 abandoned（保留记录，不再派发，不污染统计）
    for t in (tt.get(a.id), tt.get(b.id), tt.get(c.id)):
        if t.status not in ("abandoned", "failed"):
            tt.update(t.id, status="abandoned",
                      output_summary="e2e verification complete")
    print("已清理：E2E-A/B/C → abandoned（看板 Abandoned 分组可见）")
    tt.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

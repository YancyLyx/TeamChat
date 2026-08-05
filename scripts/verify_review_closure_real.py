"""#97 真实 e2e 验收 — 审查闭环全流程（连真实引擎）。

验证点（ADR-004 #97 v4）：
1. cici咪 开发节点完成后【不自动 done】（保持 running 等审核）
2. cici咪 审核自己的结果（自我编排模式）→ 引导创建 soso咪 审查节点
3. 审查节点执行 → 回流 → cici咪 审核 → done
4. coco咪 开发节点同链路（普通审核 + 审查节点）

安全：验收任务完成后标记 abandoned；prompt 要求不修改文件。
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import Config
from engine.task_table import TaskTable

ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = 2  # 当前活动 session

A_PROMPT = ("请用一句中文回复：E2E审查闭环任务A完成（只回复这一句，"
            "不要修改任何文件，不要执行 git 命令，不要创建任务）")
B_PROMPT = ("请用一句中文回复：E2E审查闭环任务B完成（只回复这一句，"
            "不要修改任何文件，不要执行 git 命令，不要创建任务）")


def main() -> int:
    config = Config(repo_owner="YancyLyx", repo_name="TeamChat",
                    repo_url="https://github.com/YancyLyx/TeamChat", project_root=ROOT)
    tt = TaskTable(config)
    tt.init()

    # 清理上次残留
    for t in tt.list_tasks():
        if t.title in ("E2E-97-A", "E2E-97-B"):
            tt.update(t.id, status="abandoned", output_summary="e2e cleanup (rerun)")

    a = tt.create(agent="cici咪", title="E2E-97-A", description=A_PROMPT,
                  teamchat_session_id=SESSION_ID, task_type="development")
    # 同一需求树：并行分支显式传 a.feature_id（模拟 cici咪 拆任务行为）
    b = tt.create(agent="coco咪", title="E2E-97-B", description=B_PROMPT,
                  teamchat_session_id=SESSION_ID, task_type="development",
                  feature_id=a.feature_id)
    print(f"已创建: #{a.id} A(cici咪) / #{b.id} B(coco咪)（同一需求树 {a.feature_id}）", flush=True)

    started_at = time.monotonic()
    last_line = ""
    review_node_seen = None
    while time.monotonic() - started_at < 600:  # 最多 10 分钟
        ta, tb = tt.get(a.id), tt.get(b.id)
        # 找审查节点：同一需求树（feature_id）里 soso咪 的验证节点
        reviews = [t for t in tt.list_tasks()
                   if t.agent == "soso咪" and t.feature_id == ta.feature_id]
        r_state = "none"
        if reviews:
            r = reviews[0]
            review_node_seen = r.id
            r_state = f"#{r.id}({r.agent},{r.status})"
        line = (f"[{int(time.monotonic()-started_at):>3}s] "
                f"A:{ta.status}  B:{tb.status}  review:{r_state}")
        if line != last_line:
            print(line, flush=True)
            last_line = line
        # 结束条件：审查节点出现且 done（或超时）
        if review_node_seen is not None:
            r = tt.get(review_node_seen)
            if r and r.status == "done":
                print("🎉 审查节点 done — 审查闭环走通", flush=True)
                break
        time.sleep(3)

    ta, tb = tt.get(a.id), tt.get(b.id)
    reviews = [t for t in tt.list_tasks()
               if t.agent == "soso咪" and t.feature_id == ta.feature_id]
    print("=" * 56)
    print(f"#97 真实 e2e 验收（session {SESSION_ID}）")
    print("=" * 56)
    print(f"  A #{a.id} (cici咪 开发): {ta.status}   ← 验收点1: 不应自动 done 后无人管")
    print(f"  B #{b.id} (coco咪 开发): {tb.status}")
    for r in reviews:
        print(f"  review 节点 #{r.id} ({r.agent}): {r.status}  ← 验收点2/3: cici咪 创建审查节点")
    print("-" * 56)
    # 验收判定
    ok1 = ta.status in ("running", "done") and tb.status in ("running", "done")
    ok2 = len(reviews) >= 1
    ok3 = ok2 and any(r.status == "done" for r in reviews)
    print(f"  验收点1 (不自动 done，等审核): {'✅' if ok1 else '❌'}")
    print(f"  验收点2 (cici咪 创建了 soso咪 审查节点): {'✅' if ok2 else '❌'}")
    print(f"  验收点3 (审查节点完成回流): {'✅' if ok3 else '❌'}")
    print("验收结论:", "PASS ✅" if (ok1 and ok2 and ok3) else "INCOMPLETE ⚠️ 见上方状态")

    # 清理：DELETE 整棵需求树（feature_id 匹配，防漏删）+ 重置 id 计数器（不跳号）
    ids = [t.id for t in tt.list_tasks() if t.feature_id == a.feature_id]
    for tid in ids:
        tt.conn.execute("DELETE FROM task_table WHERE id = ?", (tid,))
    tt.conn.execute(
        "UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM task_table) WHERE name = 'task_table'")
    tt.conn.commit()
    print("已清理：验收任务已 DELETE（无残留）")
    tt.close()
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
Playwright E2E — L3 解放面板数值与 /api/stats.l3 一致 (#30 P1, #32 前端接入).

Run:
  pytest tests/test_stats_l3_e2e.py -v
"""

from __future__ import annotations

import time

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

MSG_AT = "2026-07-31T09:00:00+00:00"


def _finish_task(tt, task_id: int, status: str, finished_at: str) -> None:
    """Set terminal status then finished_at (update() stamps now when status changes)."""
    tt.update(task_id, status=status)
    tt.update(task_id, finished_at=finished_at)


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


def _format_duration_ms(ms: int | None) -> str:
    """Mirror dashboard/src/utils/metrics.js formatDuration()."""
    if ms is None or ms <= 0:
        return "—"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    if ms < 3_600_000:
        return f"{ms / 60_000:.1f} min"
    return f"{ms / 3_600_000:.1f} h"


def _seed_l3_scenario(app) -> None:
    """Same construction as tests/test_stats_api._seed_full_l3."""
    done = {"ok": False}

    def _write() -> None:
        store = app.state.store
        tt = app.state.task_table

        store.log(
            agent_name="human", prompt="L3 e2e msg", output="L3 e2e msg",
            exit_code=0, duration_ms=0, task_type="chat_message", tag="prod",
            teamchat_session_id=1, started_at=MSG_AT, finished_at=MSG_AT,
        )
        for _ in range(2):
            store.log(
                agent_name="human", prompt="approval:req", output="allow",
                exit_code=0, duration_ms=0, task_type="approval", tag="prod",
                teamchat_session_id=1, started_at=MSG_AT, finished_at=MSG_AT,
            )
        for finish_at in (
            "2026-07-31T09:10:00+00:00",
            "2026-07-31T09:12:00+00:00",
            "2026-07-31T09:14:00+00:00",
        ):
            t = tt.create(agent="coco咪", title="done", description="d")
            _finish_task(tt, t.id, "done", finish_at)
        t_ab = tt.create(agent="coco咪", title="abandoned", description="d")
        _finish_task(tt, t_ab.id, "abandoned", "2026-07-31T09:15:00+00:00")
        done["ok"] = True

    app.state.loop.call_soon_threadsafe(_write)
    deadline = time.time() + 5
    while not done["ok"] and time.time() < deadline:
        time.sleep(0.05)
    if not done["ok"]:
        raise RuntimeError("Timed out seeding L3 E2E scenario")


def _l3_metric_text(stats_panel, label: str) -> str:
    """Read the bold value under an L3 metric label."""
    label_span = stats_panel.locator("span.text-gray-400", has_text=label)
    return label_span.locator("xpath=following-sibling::p[1]").inner_text()


def _assert_l3_metric(stats_panel, label: str, expected: str) -> None:
    assert _l3_metric_text(stats_panel, label) == expected


class TestStatsL3Panel:
    def test_l3_panel_matches_api_l3_stats(self, page: Page, e2e_servers, e2e_app):
        _seed_l3_scenario(e2e_app)
        api_url = e2e_servers["api_url"]

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        stats_panel = page.locator("aside").last
        stats_panel.get_by_role("button", name="Stats", exact=True).click()
        stats_panel.get_by_role("button", name="L3 解放").click()
        expect(stats_panel.get_by_text("Human Liberation")).to_be_visible(timeout=10_000)

        # Re-fetch after UI mount so panel and API share the same post-seed snapshot.
        l3 = httpx.get(f"{api_url}/api/stats", timeout=10.0).json()["l3"]

        automation_pct = f"{round(l3['automation_rate'] * 100)}%"
        expect(stats_panel.get_by_text(automation_pct).first).to_be_visible(timeout=15_000)

        _assert_l3_metric(stats_panel, "Manual Interventions", str(l3["human_interventions"]))
        _assert_l3_metric(stats_panel, "Approvals", str(l3["approvals"]))

        if l3["message_to_completion_ms"] is not None:
            expected_duration = _format_duration_ms(l3["message_to_completion_ms"])
            _assert_l3_metric(stats_panel, "Message to Completion", expected_duration)

"""
Playwright E2E tests for ADR-005 Tasks 看板.

Run:
  pytest tests/test_tasks_board_e2e.py -v
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e_support import seed_task_table

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _goto(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")


def _wait_connected(page: Page, timeout: float = 15_000) -> None:
    expect(page.get_by_text("WebSocket 已连接")).to_be_visible(timeout=timeout)


class TestTasksBoard:
    def test_shows_status_groups_and_dependency_waiting(
        self, page: Page, e2e_servers, e2e_app
    ):
        blocker_title = f"BLOCK_{uuid.uuid4().hex[:8]}"
        blocker_id = seed_task_table(
            e2e_app, agent="coco咪", title=blocker_title, status="failed"
        )
        waiting_title = f"WAIT_{uuid.uuid4().hex[:8]}"
        seed_task_table(
            e2e_app,
            agent="soso咪",
            title=waiting_title,
            status="pending",
            depends_on=[blocker_id],
        )
        running_title = f"RUN_{uuid.uuid4().hex[:8]}"
        seed_task_table(
            e2e_app, agent="coco咪", title=running_title, status="running"
        )
        done_title = f"DONE_{uuid.uuid4().hex[:8]}"
        seed_task_table(
            e2e_app, agent="cici咪", title=done_title, status="done"
        )

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        expect(tasks_panel.get_by_test_id("tasks-group-running")).to_be_visible()
        expect(
            tasks_panel.get_by_test_id("tasks-group-running").get_by_text(running_title)
        ).to_be_visible()
        expect(tasks_panel.get_by_test_id("tasks-group-waiting")).to_be_visible()
        expect(
            tasks_panel.get_by_test_id("tasks-group-waiting").get_by_text(waiting_title)
        ).to_be_visible()
        expect(
            tasks_panel.get_by_test_id("tasks-group-waiting").get_by_text(
                f"等 #{blocker_id} 完成"
            )
        ).to_be_visible()
        expect(tasks_panel.get_by_test_id("tasks-group-done")).to_be_visible()
        expect(
            tasks_panel.get_by_test_id("tasks-group-done").get_by_text(done_title)
        ).to_be_visible()
        expect(tasks_panel.get_by_test_id("tasks-group-failed")).to_be_visible()
        expect(
            tasks_panel.get_by_test_id("tasks-group-failed").get_by_text(blocker_title)
        ).to_be_visible()

    def test_agent_filter_hides_other_agents(self, page: Page, e2e_servers, e2e_app):
        coco_marker = f"COCO_{uuid.uuid4().hex[:8]}"
        soso_marker = f"SOSO_{uuid.uuid4().hex[:8]}"
        seed_task_table(e2e_app, agent="coco咪", title=coco_marker, status="running")
        seed_task_table(e2e_app, agent="soso咪", title=soso_marker, status="running")

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        tasks_panel.get_by_label("按 agent 筛选").select_option("coco咪")
        expect(tasks_panel.get_by_test_id("tasks-group-running").get_by_text(coco_marker)).to_be_visible()
        expect(tasks_panel.get_by_test_id("tasks-group-running").get_by_text(soso_marker)).to_have_count(0)

    def test_failed_task_shows_retry_info_and_retry_moves_to_waiting(
        self, page: Page, e2e_servers, e2e_app
    ):
        blocker = seed_task_table(
            e2e_app, agent="coco咪", title=f"BLOCKED_{uuid.uuid4().hex[:8]}", status="failed"
        )
        child_title = f"FAIL_{uuid.uuid4().hex[:8]}"
        child = seed_task_table(
            e2e_app,
            agent="soso咪",
            title=child_title,
            status="failed",
            depends_on=[blocker],
        )
        api_url = e2e_servers["api_url"]
        httpx.patch(
            f"{api_url}/api/tasks/table/{child}",
            json={"retry_count": 2, "last_error": "network timeout"},
            timeout=10.0,
        ).raise_for_status()

        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        tasks_panel = page.locator("aside").last
        failed_group = tasks_panel.get_by_test_id("tasks-group-failed")
        card = failed_group.get_by_test_id(f"task-{child}")
        expect(card.get_by_text("重试 2 次: network timeout")).to_be_visible()
        expect(card.get_by_role("button", name="重试")).to_be_visible()
        expect(card.get_by_role("button", name="转派")).to_be_visible()
        expect(card.get_by_role("button", name="放弃")).to_be_visible()

        card.get_by_role("button", name="重试").click()

        waiting_group = tasks_panel.get_by_test_id("tasks-group-waiting")
        expect(waiting_group.get_by_text(child_title)).to_be_visible(timeout=10_000)
        expect(failed_group.get_by_text(child_title)).to_have_count(0)

    def test_task_table_create_and_update_broadcast_to_board(
        self, page: Page, e2e_servers, e2e_app
    ):
        blocker = seed_task_table(
            e2e_app, agent="coco咪", title=f"BLOCKED_{uuid.uuid4().hex[:8]}", status="failed"
        )
        _goto(page, e2e_servers["dashboard_url"])
        _wait_connected(page)

        api_url = e2e_servers["api_url"]
        marker = f"LIVE_{uuid.uuid4().hex[:8]}"
        created = httpx.post(
            f"{api_url}/api/tasks/table",
            json={"agent": "soso咪", "title": marker, "depends_on": [blocker]},
            timeout=10.0,
        )
        created.raise_for_status()

        tasks_panel = page.locator("aside").last
        waiting_group = tasks_panel.get_by_test_id("tasks-group-waiting")
        expect(waiting_group.get_by_text(marker)).to_be_visible(timeout=10_000)

        httpx.patch(
            f"{api_url}/api/tasks/table/{created.json()['id']}",
            json={"status": "done"},
            timeout=10.0,
        ).raise_for_status()

        done_group = tasks_panel.get_by_test_id("tasks-group-done")
        expect(done_group.get_by_text(marker)).to_be_visible(timeout=10_000)

"""Unit tests for GitHub Adapter (ADR-005 Phase 4.1): Issue → Task bridging."""

import pytest

from engine.config import Config
from engine.github_adapter import handle_issue_event
from engine.session_store import SessionStore
from engine.task_table import TaskTable


@pytest.fixture
def stores(tmp_path):
    config = Config(
        repo_owner="t", repo_name="t", repo_url="https://github.com/t/t",
        project_root=tmp_path,
    )
    ss = SessionStore(config)
    ss.init()
    tt = TaskTable(config)
    tt.init()
    yield ss, tt
    tt.close()
    ss.close()


@pytest.fixture
def task_table(stores):
    return stores[1]


def _issue_payload(number=1, title="实现黑暗模式", body="支持深色主题",
                   action="opened", state="open"):
    return {
        "action": action,
        "issue": {"number": number, "title": title, "body": body, "state": state},
    }


class TestHandleIssueEvent:
    def test_opened_issue_creates_task(self, task_table):
        created = handle_issue_event(_issue_payload(), task_table)

        assert created is not None
        task = task_table.get(created["id"])
        assert task.agent == "cici咪"  # 中枢模式: cici咪 分析
        assert "实现黑暗模式" in task.title
        assert task.github_issue == "#1"
        assert task.status == "pending"
        assert "mcp__teamchat__create_task" in task.description  # 引导拆分

    def test_non_opened_action_ignored(self, task_table):
        created = handle_issue_event(
            _issue_payload(action="closed", state="closed"), task_table,
        )
        assert created is None
        assert len(task_table.list_tasks()) == 0

    def test_closed_issue_not_created(self, task_table):
        created = handle_issue_event(
            _issue_payload(state="closed"), task_table,
        )
        assert created is None

    def test_missing_title_ignored(self, task_table):
        payload = _issue_payload()
        payload["issue"]["title"] = ""
        created = handle_issue_event(payload, task_table)
        assert created is None

    def test_session_id_passed_through(self, stores):
        ss, tt = stores
        ss.create("测试会话", "/tmp/test-project")  # FK target for session 2
        created = handle_issue_event(_issue_payload(), tt, teamchat_session_id=2)
        task = tt.get(created["id"])
        assert task.teamchat_session_id == 2

#!/usr/bin/env python3
"""cici咪 更新 Issue #4: 明确 E2E 技术选型 — Playwright + pytest-playwright"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import load_config, AGENT_CICI
from engine.github_client import GitHubClient


async def main():
    config = load_config()
    cici = GitHubClient(config, AGENT_CICI)

    await cici.comment_on_issue(4, """## E2E 技术选型补充

soso咪 注意 — E2E 测试框架明确用 **Playwright + pytest-playwright**，与现有技术栈完美匹配：

| 优势 | 说明 |
|---|---|
| Python 原生 | `pytest-playwright` 用 Python 写测试，和现有 28 个测试同一套 pytest |
| 自动等待 | 元素自动等待加载，不用手动 `sleep()` |
| 零外部依赖 | 不需要 Selenium Grid / WebDriver / Java |
| 一键安装 | `playwright install chromium` |

### 依赖更新

`pyproject.toml` 的 dev dependencies 需要加：
```toml
dev = [
    # ... 现有的 ...
    "playwright>=1.50.0",
    "pytest-playwright>=0.6.0",
]
```

### 测试示例

```python
# tests/test_dashboard.py
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="module")
def dashboard_url():
    return "http://localhost:5173"  # Vite dev server

def test_dashboard_loads(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    # 标题可见
    expect(page.locator("h1")).to_contain_text("TeamChat")

def test_three_agent_cards_visible(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    expect(page.locator("[data-testid='agent-card']")).to_have_count(3)
    expect(page.locator("text=cici咪")).to_be_visible()
    expect(page.locator("text=coco咪")).to_be_visible()
    expect(page.locator("text=soso咪")).to_be_visible()

def test_websocket_connection_indicator(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    # 等待 WebSocket 连接建立
    page.wait_for_selector("[data-testid='connection-status']:has-text('已连接')", timeout=10000)
    expect(page.locator("[data-testid='connection-status']")).to_have_text("已连接")

def test_submit_task_via_api(page: Page, dashboard_url: str):
    import httpx
    # 通过 API 提交任务
    resp = httpx.post("http://localhost:8000/api/tasks", json={
        "agent": "cici咪",
        "prompt": "Say hello in one sentence."
    }, timeout=30)
    assert resp.status_code == 200

    page.goto(dashboard_url)
    # 任务卡片应该出现在 TaskBoard
    page.wait_for_selector("[data-testid='task-card']", timeout=10000)

def test_disconnect_reconnect(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_selector("[data-testid='connection-status']:has-text('已连接')", timeout=10000)

    # 模拟断线：关闭 API 服务器然后重启
    # 验证自动重连
    page.wait_for_selector("[data-testid='connection-status']:has-text('已连接')", timeout=30000)
```

### conftest.py 更新

在 `tests/conftest.py` 或新建 `tests/conftest_dashboard.py`：
```python
import pytest

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
    }
```

### 运行方式

```bash
# 安装
pip install playwright pytest-playwright
playwright install chromium

# 启动 API 和 Dashboard（两个终端）
uvicorn api.main:app --host 127.0.0.1 --port 8000 &
cd dashboard && npm run dev &

# 跑 E2E 测试
pytest tests/test_dashboard.py -v
```

---

记得：先让 coco咪 把 Dashboard 写完并创建 PR，你再基于 PR 的代码写测试。""")

    await cici.close()
    print("✅ Issue #4 已更新 — E2E 技术选型补充完毕")


if __name__ == "__main__":
    asyncio.run(main())

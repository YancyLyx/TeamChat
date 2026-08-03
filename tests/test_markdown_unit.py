"""node 单元测试（verify-markdown.mjs），无浏览器依赖。

单独文件是因为 pytest 的 mark 是合并而非覆盖——放在
test_markdown_render.py（模块级 e2e mark）里时，类级 pytestmark
无法去掉 e2e，导致被 `-m "not e2e"` 排除，无法与单元测试混跑。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[1]


class TestMarkdownUnit:
    def test_node_markdown_security_checks(self):
        script = ROOT / "dashboard" / "scripts" / "verify-markdown.mjs"
        proc = subprocess.run(
            ["node", str(script)],
            cwd=ROOT / "dashboard",
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

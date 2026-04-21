"""perf 分区冒烟测试 — 确保目录被 pytest 收集但不触发真实压测。

真实压测通过 locust 运行（见 locustfile.py）。这里只保留一个被
`@pytest.mark.perf` 标记的占位用例，用于验证 marker 注册与目录结构。
"""

from __future__ import annotations

import pytest


@pytest.mark.perf
def test_perf_suite_marker_registered():
    """确认 perf marker 可用且目录能被 pytest 发现。"""
    assert True

"""
全局测试 conftest — 自动给 P0/P1 回归测试贴 marker。

全局门禁要求：`pytest -m p0` / `pytest -m p1` 可分阶段验证。
为避免在每个测试文件里重复写 `pytestmark = pytest.mark.pX`，这里基于
文件名做集中映射，按 `docs/production-readiness-p0-p1-plan.md` 的
"任务→测试" 对照关系配置。新增回归测试请同步更新下表。
"""

from __future__ import annotations

import pytest

# ── 文件名 → marker 映射 ─────────────────────────────────────
# key 使用 `stem`（不含 .py 后缀）
_P0_FILES: set[str] = {
    # Sprint 1 · 引擎核心
    "test_engine_timeout",           # P0-1
    "test_engine_cancel",            # P0-1
    "test_engine_errors",            # P0-2
    "test_run_stream_checkpoint",    # P0-3
    "test_error_handler",            # P0-9
    "test_workspace_path_traversal", # P0-10
    # Sprint 2 · 安全与可观测
    "test_request_context",          # P0-5
    "test_observability",            # P0-6
    "test_cors",                     # P0-7
    "test_auth_timing_safe",         # P0-8
    "test_rate_limit_client_id",     # P0-8
}

_P1_FILES: set[str] = {
    # Sprint 3 · 性能与契约
    "test_connection_pool",          # P1-1
    "test_sse_under_middleware",     # P1-2
    "test_shutdown_grace",           # P1-5
    "test_execute_response_schema",  # P1-10
    # Sprint 4 · P1 收尾
    "test_rate_limit_backend",       # P1-3
    "test_prompt_adapter_cache",     # P1-4
    "test_checkpoint_retry",         # P1-7
    "test_settings_summary",         # P1-8 + P1-9
    "test_plan_concurrency",         # P1-11
    "test_fake_provider",            # P1-12
    "test_openapi_contract",         # P1-12 (OpenAPI 契约自检)
}

_RESILIENCE_DIRS: set[str] = {"resilience"}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-apply p0/p1/resilience markers based on test file location."""
    for item in items:
        path = item.path if hasattr(item, "path") else None
        if path is None:
            continue
        stem = path.stem
        parts = set(path.parts)

        if stem in _P0_FILES:
            item.add_marker(pytest.mark.p0)
        if stem in _P1_FILES:
            item.add_marker(pytest.mark.p1)
        if parts & _RESILIENCE_DIRS:
            item.add_marker(pytest.mark.resilience)
            item.add_marker(pytest.mark.p1)

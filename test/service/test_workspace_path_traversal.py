"""
P0-10 workspace 路径消毒回归测试

验证：
  1. workspace_root 在 workspace_base 内时允许通过
  2. workspace_root 使用 .. 遍历跳出 workspace_base 时被拒绝
  3. workspace_root 是绝对路径跳出 workspace_base 时被拒绝
  4. workspace_base 为空时不做校验（向后兼容）
  5. Windows 驱动器跨越场景被拒绝
  6. WorkspaceContext.validate_path 防止路径遍历
  7. WorkspaceContext.is_tool_allowed 白名单校验
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import pytest

from Service.services.proxy.workspace_manager import WorkspaceConfig, WorkspaceContext


# ── _is_path_within 工具函数 ──────────────────────────────────

def _is_path_within(target: Path, base: Path) -> bool:
    """复制自 agent_service.py 的路径校验逻辑。"""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


class TestIsPathWithin:
    """workspace_base 路径消毒核心逻辑。"""

    def test_valid_subdirectory(self, tmp_path: Path):
        base = tmp_path / "workspaces"
        base.mkdir()
        target = base / "project-a"
        target.mkdir()
        assert _is_path_within(target, base) is True

    def test_dotdot_traversal_rejected(self, tmp_path: Path):
        base = tmp_path / "workspaces"
        base.mkdir()
        evil = tmp_path / "workspaces" / ".." / "etc"
        assert _is_path_within(evil, base) is False

    def test_absolute_outside_rejected(self, tmp_path: Path):
        base = tmp_path / "workspaces"
        base.mkdir()
        outside = tmp_path / "other"
        outside.mkdir()
        assert _is_path_within(outside, base) is False

    def test_empty_base_equivalent_to_root(self):
        """workspace_base 为空字符串时 agent_service 不做校验，此处仅测工具函数。"""
        target = Path("/some/path")
        base = Path("/")
        assert _is_path_within(target, base) is True

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_cross_drive_rejected(self):
        assert _is_path_within(Path("D:\\evil"), Path("C:\\workspaces")) is False


# ── WorkspaceContext.validate_path ────────────────────────────

class TestWorkspaceContextValidatePath:
    """WorkspaceContext 内部路径校验。"""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> WorkspaceContext:
        root = tmp_path / "ws"
        root.mkdir()
        config = WorkspaceConfig(root_path=str(root))
        return WorkspaceContext(workspace_id="test", config=config)

    def test_valid_path(self, workspace: WorkspaceContext, tmp_path: Path):
        valid_file = tmp_path / "ws" / "hello.txt"
        valid_file.touch()
        ok, resolved, err = workspace.validate_path(valid_file)
        assert ok is True
        assert resolved is not None

    def test_dotdot_escape(self, workspace: WorkspaceContext, tmp_path: Path):
        evil = str(tmp_path / "ws" / ".." / "secrets.txt")
        ok, _, err = workspace.validate_path(evil)
        assert ok is False
        assert "outside" in err.lower() or "Path" in err

    def test_absolute_outside(self, workspace: WorkspaceContext, tmp_path: Path):
        outside = tmp_path / "other" / "file.txt"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.touch()
        ok, _, _ = workspace.validate_path(str(outside))
        assert ok is False

    def test_relative_within(self, workspace: WorkspaceContext, tmp_path: Path):
        (tmp_path / "ws" / "sub").mkdir()
        ok, resolved, _ = workspace.validate_path("sub")
        assert ok is True


# ── WorkspaceContext.is_tool_allowed ──────────────────────────

class TestToolAllowlist:
    """allowed_tools / denied_tools 白名单校验。"""

    def _make_context(self, tmp_path: Path, **kwargs: Any) -> WorkspaceContext:
        root = tmp_path / "ws"
        root.mkdir(exist_ok=True)
        config = WorkspaceConfig(root_path=str(root), **kwargs)
        return WorkspaceContext(workspace_id="test", config=config)

    def test_wildcard_allows_all(self, tmp_path: Path):
        ctx = self._make_context(tmp_path, allowed_tools=["*"])
        assert ctx.is_tool_allowed("read_file") is True
        assert ctx.is_tool_allowed("exec_command") is True

    def test_explicit_allow_list(self, tmp_path: Path):
        ctx = self._make_context(tmp_path, allowed_tools=["read_file", "search"])
        assert ctx.is_tool_allowed("read_file") is True
        assert ctx.is_tool_allowed("exec_command") is False

    def test_denied_tools_override(self, tmp_path: Path):
        ctx = self._make_context(
            tmp_path,
            allowed_tools=["*"],
            denied_tools=["exec_command"],
        )
        assert ctx.is_tool_allowed("read_file") is True
        assert ctx.is_tool_allowed("exec_command") is False

    def test_unknown_tool_rejected_when_not_wildcard(self, tmp_path: Path):
        ctx = self._make_context(tmp_path, allowed_tools=["read_file"])
        assert ctx.is_tool_allowed("unknown_tool") is False

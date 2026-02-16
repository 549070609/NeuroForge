"""
工具系统测试
"""

import pytest

from pyagentforge.tools.permission import PermissionChecker, PermissionConfig, PermissionResult
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.tools.builtin.bash import BashTool
from pyagentforge.tools.builtin.read import ReadTool


class TestToolRegistry:
    """工具注册表测试"""

    def test_register_tool(self) -> None:
        """测试注册工具"""
        registry = ToolRegistry()
        tool = BashTool()
        registry.register(tool)

        assert registry.has("bash")
        assert len(registry) == 1

    def test_get_tool(self) -> None:
        """测试获取工具"""
        registry = ToolRegistry()
        registry.register(BashTool())

        tool = registry.get("bash")
        assert tool is not None
        assert tool.name == "bash"

    def test_filter_by_permission(self) -> None:
        """测试权限过滤"""
        registry = ToolRegistry()
        registry.register(BashTool())
        registry.register(ReadTool())

        filtered = registry.filter_by_permission(["bash"])
        assert filtered.has("bash")
        assert not filtered.has("read")

    def test_register_builtin(self) -> None:
        """测试注册内置工具"""
        registry = ToolRegistry()
        registry.register_builtin_tools()

        assert registry.has("bash")
        assert registry.has("read")
        assert registry.has("write")
        assert len(registry) >= 6


class TestPermissionChecker:
    """权限检查器测试"""

    def test_allow_all(self) -> None:
        """测试允许所有"""
        config = PermissionConfig(allowed=["*"])
        checker = PermissionChecker(config)

        assert checker.check("bash", {}) == PermissionResult.ALLOW
        assert checker.check("read", {}) == PermissionResult.ALLOW

    def test_deny_specific(self) -> None:
        """测试拒绝特定工具"""
        config = PermissionConfig(
            allowed=["*"],
            denied=["bash"],
        )
        checker = PermissionChecker(config)

        assert checker.check("bash", {}) == PermissionResult.DENY
        assert checker.check("read", {}) == PermissionResult.ALLOW

    def test_ask_specific(self) -> None:
        """测试需要确认"""
        config = PermissionConfig(
            allowed=["*"],
            ask=["write"],
        )
        checker = PermissionChecker(config)

        assert checker.check("write", {}) == PermissionResult.ASK
        assert checker.check("read", {}) == PermissionResult.ALLOW

    def test_wildcard_pattern(self) -> None:
        """测试通配符匹配"""
        config = PermissionConfig(
            allowed=["read*"],
            denied=["write*"],
        )
        checker = PermissionChecker(config)

        assert checker.check("read_file", {}) == PermissionResult.ALLOW
        assert checker.check("write_file", {}) == PermissionResult.DENY


class TestBashTool:
    """Bash 工具测试"""

    @pytest.mark.asyncio
    async def test_echo_command(self) -> None:
        """测试 echo 命令"""
        tool = BashTool()
        result = await tool.execute(command="echo hello")

        assert "hello" in result

    @pytest.mark.asyncio
    async def test_invalid_command(self) -> None:
        """测试无效命令"""
        tool = BashTool()
        result = await tool.execute(command="nonexistent_command_12345")

        assert "Error" in result or "not found" in result.lower()

"""
Tests for ToolRegistry

Tests for tool registration, unregistration, and retrieval.
"""


from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        }
    }

    async def execute(self, **kwargs):
        return "mock result"


class AnotherMockTool(BaseTool):
    """Another mock tool for testing."""

    name = "another_tool"
    description = "Another mock tool"
    parameters_schema = {}

    async def execute(self, **kwargs):
        return "another result"


class TestToolRegistry:
    """Test cases for ToolRegistry."""

    def test_init(self):
        """Test registry initialization."""
        registry = ToolRegistry()
        assert len(registry) == 0
        assert registry._tools == {}
        assert registry._tool_factories == {}

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = MockTool()

        registry.register(tool)

        assert len(registry) == 1
        assert registry.has("mock_tool")
        assert registry.get("mock_tool") == tool

    def test_register_tool_overwrite(self):
        """Test registering a tool with the same name overwrites."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = MockTool()

        registry.register(tool1)
        registry.register(tool2)

        assert len(registry) == 1
        assert registry.get("mock_tool") == tool2

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        result = registry.unregister("mock_tool")

        assert result is True
        assert len(registry) == 0
        assert registry.get("mock_tool") is None

    def test_unregister_nonexistent_tool(self):
        """Test unregistering a non-existent tool returns False."""
        registry = ToolRegistry()

        result = registry.unregister("nonexistent")

        assert result is False

    def test_get_tool(self):
        """Test getting a tool by name."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        retrieved = registry.get("mock_tool")

        assert retrieved == tool
        assert retrieved.name == "mock_tool"

    def test_get_nonexistent_tool(self):
        """Test getting a non-existent tool returns None."""
        registry = ToolRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_has_tool(self):
        """Test checking if a tool exists."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert registry.has("mock_tool") is True
        assert registry.has("nonexistent") is False

    def test_get_all(self):
        """Test getting all tools."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        all_tools = registry.get_all()

        assert len(all_tools) == 2
        assert "mock_tool" in all_tools
        assert "another_tool" in all_tools

        # Verify it's a copy
        all_tools["new_tool"] = "test"
        assert "new_tool" not in registry._tools

    def test_list_tools(self):
        """Test listing all tool names."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        tools = list(registry)  # Uses __iter__

        assert len(tools) == 2
        assert tool1 in tools
        assert tool2 in tools

    def test_get_schemas(self):
        """Test getting all tool schemas."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        schemas = registry.get_schemas()

        assert len(schemas) == 2
        names = [s["name"] for s in schemas]
        assert "mock_tool" in names
        assert "another_tool" in names

        # Verify schema format
        mock_schema = next(s for s in schemas if s["name"] == "mock_tool")
        assert "description" in mock_schema
        assert "input_schema" in mock_schema

    def test_filter_by_permission_all(self):
        """Test filtering tools with wildcard permission."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        filtered = registry.filter_by_permission(["*"])

        assert len(filtered) == 2
        assert filtered.has("mock_tool")
        assert filtered.has("another_tool")

    def test_filter_by_permission_specific(self):
        """Test filtering tools with specific permissions."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        filtered = registry.filter_by_permission(["mock_tool"])

        assert len(filtered) == 1
        assert filtered.has("mock_tool")
        assert not filtered.has("another_tool")

    def test_filter_by_permission_empty(self):
        """Test filtering with empty permission list."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        filtered = registry.filter_by_permission([])

        assert len(filtered) == 0

    def test_register_builtin_tools(self):
        """Test registering builtin tools."""
        registry = ToolRegistry()

        registry.register_builtin_tools()

        # Verify all 6 builtin tools are registered
        assert registry.has("bash")
        assert registry.has("read")
        assert registry.has("write")
        assert registry.has("edit")
        assert registry.has("glob")
        assert registry.has("grep")
        assert len(registry) == 6

    def test_register_factory(self):
        """Test registering a tool factory."""
        registry = ToolRegistry()

        factory_called = []

        def create_tool():
            factory_called.append(True)
            return MockTool()

        registry.register_factory("mock_tool", create_tool)

        assert "mock_tool" in registry._tool_factories
        assert len(factory_called) == 0  # Not called yet

    def test_get_or_create_from_factory(self):
        """Test getting or creating a tool from factory."""
        registry = ToolRegistry()

        def create_tool():
            return MockTool()

        registry.register_factory("mock_tool", create_tool)

        # First call creates the tool
        tool = registry.get_or_create("mock_tool")
        assert tool is not None
        assert tool.name == "mock_tool"
        assert registry.has("mock_tool")

        # Second call returns the registered tool
        tool2 = registry.get_or_create("mock_tool")
        assert tool2 == tool

    def test_get_or_create_nonexistent(self):
        """Test getting or creating non-existent tool returns None."""
        registry = ToolRegistry()

        result = registry.get_or_create("nonexistent")

        assert result is None

    def test_contains(self):
        """Test __contains__ method."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert "mock_tool" in registry
        assert "nonexistent" not in registry

    def test_repr(self):
        """Test __repr__ method."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        repr_str = repr(registry)

        assert "ToolRegistry" in repr_str
        assert "mock_tool" in repr_str

    def test_iter(self):
        """Test __iter__ method."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = AnotherMockTool()
        registry.register(tool1)
        registry.register(tool2)

        tools = list(registry)

        assert len(tools) == 2

    def test_len(self):
        """Test __len__ method."""
        registry = ToolRegistry()
        assert len(registry) == 0

        registry.register(MockTool())
        assert len(registry) == 1

        registry.register(AnotherMockTool())
        assert len(registry) == 2


class TestToolRegistryAutoDiscovery:
    """Test cases for auto-discovery functionality."""

    def test_auto_discover_tools(self):
        """Test auto-discovering tools from a package."""
        registry = ToolRegistry()

        count = registry.auto_discover_tools("pyagentforge.tools.builtin")

        # Should discover at least the 6 builtin tools
        assert count >= 6
        assert registry.has("bash")
        assert registry.has("read")

    def test_auto_discover_tools_skip_dunder(self):
        """Test that __init__ and __dunder__ files are skipped."""
        registry = ToolRegistry()

        registry.auto_discover_tools("pyagentforge.tools.builtin")

        # Should not have any dunder-named tools
        for name in registry._tools:
            assert not name.startswith("_")


class TestToolRegistryPriorityLevels:
    """Test cases for priority level registration."""

    def test_register_p0_tools(self):
        """Test registering P0 tools."""
        registry = ToolRegistry()

        registry.register_p0_tools()

        assert len(registry) >= 2  # At least ls, lsp

    def test_register_p2_tools(self):
        """Test registering P2 tools."""
        registry = ToolRegistry()

        # P2 tools depend on existing tools for InvalidTool
        registry.register_builtin_tools()
        registry.register_p2_tools()

        assert registry.has("invalid")

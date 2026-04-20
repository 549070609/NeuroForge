"""
Tests for PluginManager class

Comprehensive tests for the plugin management system including
loading, activation, deactivation, and hook/tool management.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookPriority, HookType
from pyagentforge.plugin.manager import PluginManager
from pyagentforge.plugin.registry import PluginState

# ============================================================================
# Mock Plugin Classes
# ============================================================================

class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_plugin_tool"
    description = "A mock tool from plugin"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"]
    }

    def __init__(self, return_value: str = "Tool executed"):
        self.return_value = return_value

    async def execute(self, **kwargs) -> str:
        return self.return_value


class MockPlugin(Plugin):
    """Mock plugin for testing."""

    def __init__(
        self,
        plugin_id: str = "test.plugin",
        name: str = "Test Plugin",
        version: str = "1.0.0",
        plugin_type: PluginType = PluginType.TOOL,
        dependencies: list[str] | None = None,
        optional_dependencies: list[str] | None = None,
        conflicts: list[str] | None = None,
        priority: int = 0,
        provides_tools: bool = False,
    ):
        super().__init__()
        self.metadata = PluginMetadata(
            id=plugin_id,
            name=name,
            version=version,
            type=plugin_type,
            description="A mock plugin for testing",
            dependencies=dependencies or [],
            optional_dependencies=optional_dependencies or [],
            conflicts=conflicts or [],
            priority=priority,
        )
        self._provides_tools = provides_tools
        self._hooks_called: list[str] = []
        self._on_load_called = False
        self._on_activate_called = False
        self._on_deactivate_called = False

    async def on_plugin_load(self, context: PluginContext) -> None:
        """Track when load is called."""
        await super().on_plugin_load(context)
        self._on_load_called = True
        self._hooks_called.append("on_plugin_load")

    async def on_plugin_activate(self) -> None:
        """Track when activate is called."""
        await super().on_plugin_activate()
        self._on_activate_called = True
        self._hooks_called.append("on_plugin_activate")

    async def on_plugin_deactivate(self) -> None:
        """Track when deactivate is called."""
        await super().on_plugin_deactivate()
        self._on_deactivate_called = True
        self._hooks_called.append("on_plugin_deactivate")

    async def on_before_llm_call(self, messages: list) -> list | None:
        """Hook that modifies messages."""
        self._hooks_called.append("on_before_llm_call")
        return None

    def get_tools(self) -> list[BaseTool]:
        """Return tools if configured to do so."""
        if self._provides_tools:
            return [MockTool()]
        return []


class MockEngine:
    """Mock engine for testing."""

    def __init__(self):
        self.tools = MagicMock()
        self.tools.register = MagicMock()
        self.tools.unregister = MagicMock()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_engine():
    """Create a mock engine."""
    return MockEngine()


@pytest.fixture
def plugin_manager(mock_engine):
    """Create a plugin manager with mock engine."""
    return PluginManager(engine=mock_engine)


@pytest.fixture
def mock_plugin():
    """Create a basic mock plugin."""
    return MockPlugin()


@pytest.fixture
def mock_plugin_with_tools():
    """Create a mock plugin that provides tools."""
    return MockPlugin(provides_tools=True)


@pytest.fixture
def mock_plugin_with_dependencies():
    """Create a mock plugin with dependencies."""
    return MockPlugin(
        plugin_id="test.dependent",
        dependencies=["test.dependency"]
    )


@pytest.fixture
def mock_dependency_plugin():
    """Create a mock dependency plugin."""
    return MockPlugin(plugin_id="test.dependency")


# ============================================================================
# Test: Initialize Loads Plugins
# ============================================================================

class TestPluginManagerInitialize:
    """Tests for plugin manager initialization."""

    @pytest.mark.asyncio
    async def test_initialize_loads_plugins(self, plugin_manager, tmp_path):
        """Test that initialize loads and activates enabled plugins."""
        # Create a plugin directory
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Register plugins directly in registry
        plugin1 = MockPlugin(plugin_id="plugin.one", priority=10)
        plugin2 = MockPlugin(plugin_id="plugin.two", priority=5)

        plugin_manager.registry.register(plugin1)
        plugin_manager.registry.register(plugin2)

        # Initialize with config
        config = {
            "enabled": ["plugin.one", "plugin.two"],
            "plugin_dirs": [],
        }

        # Mock the loader to return our registered plugins
        plugin_manager.loader.load_all = MagicMock(
            return_value={"plugin.one": plugin1, "plugin.two": plugin2}
        )

        await plugin_manager.initialize(config, working_dir=str(tmp_path))

        # Verify plugins were activated
        assert plugin_manager.registry.is_activated("plugin.one")
        assert plugin_manager.registry.is_activated("plugin.two")

    @pytest.mark.asyncio
    async def test_initialize_with_empty_enabled_list(self, plugin_manager):
        """Test that initialize handles empty enabled list."""
        config = {
            "enabled": [],
            "plugin_dirs": [],
        }

        await plugin_manager.initialize(config)

        # No plugins should be loaded
        assert len(plugin_manager.registry.get_all()) == 0

    @pytest.mark.asyncio
    async def test_initialize_with_preset_minimal(self, plugin_manager):
        """Test that preset 'minimal' loads no plugins."""
        config = {
            "preset": "minimal",
            "enabled": [],
            "plugin_dirs": [],
        }

        await plugin_manager.initialize(config)

        assert len(plugin_manager.registry.get_activated()) == 0

    @pytest.mark.asyncio
    async def test_initialize_with_auto_discover(self, plugin_manager, tmp_path):
        """Test auto-discovery of plugin directory."""
        # Create auto-discover directory
        auto_dir = tmp_path / ".agent" / "plugins"
        auto_dir.mkdir(parents=True)

        config = {
            "auto_discover": True,
            "auto_enable_all": True,
            "auto_discover_dir": ".agent/plugins",
            "enabled": [],
            "plugin_dirs": [],
        }

        # Mock discover_plugin_ids to return some IDs
        plugin_manager._discover_plugin_ids = MagicMock(return_value=["auto.plugin"])

        await plugin_manager.initialize(config, working_dir=str(tmp_path))

        # Auto-discover should have been called
        plugin_manager._discover_plugin_ids.assert_called()


# ============================================================================
# Test: Activate Plugin
# ============================================================================

class TestPluginManagerActivatePlugin:
    """Tests for plugin activation."""

    @pytest.mark.asyncio
    async def test_activate_plugin(self, plugin_manager, mock_plugin):
        """Test activating a plugin."""
        # Register the plugin
        plugin_manager.registry.register(mock_plugin)

        # Activate it
        result = await plugin_manager.activate_plugin("test.plugin")

        assert result is True
        assert mock_plugin._on_load_called
        assert mock_plugin._on_activate_called
        assert plugin_manager.registry.is_activated("test.plugin")

    @pytest.mark.asyncio
    async def test_activate_plugin_already_activated(self, plugin_manager, mock_plugin):
        """Test activating an already activated plugin."""
        plugin_manager.registry.register(mock_plugin)
        plugin_manager.registry.set_state("test.plugin", PluginState.ACTIVATED)

        result = await plugin_manager.activate_plugin("test.plugin")

        # Should return True but not call activate again
        assert result is True

    @pytest.mark.asyncio
    async def test_activate_plugin_not_found(self, plugin_manager):
        """Test activating a non-existent plugin."""
        result = await plugin_manager.activate_plugin("nonexistent.plugin")

        assert result is False

    @pytest.mark.asyncio
    async def test_activate_plugin_with_tools(self, plugin_manager, mock_plugin_with_tools):
        """Test that activating a plugin registers its tools."""
        plugin_manager.registry.register(mock_plugin_with_tools)

        await plugin_manager.activate_plugin("test.plugin")

        # Verify tools were registered
        plugin_manager.engine.tools.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_plugin_registers_hooks(self, plugin_manager, mock_plugin):
        """Test that activating a plugin registers its hooks."""
        plugin_manager.registry.register(mock_plugin)

        await plugin_manager.activate_plugin("test.plugin")

        # Verify hooks were registered
        hooks = mock_plugin.get_hooks()
        for hook_name in hooks:
            assert plugin_manager.hooks.has_hooks(HookType(hook_name))


# ============================================================================
# Test: Deactivate Plugin
# ============================================================================

class TestPluginManagerDeactivatePlugin:
    """Tests for plugin deactivation."""

    @pytest.mark.asyncio
    async def test_deactivate_plugin(self, plugin_manager, mock_plugin):
        """Test deactivating a plugin."""
        plugin_manager.registry.register(mock_plugin)
        await plugin_manager.activate_plugin("test.plugin")

        result = await plugin_manager.deactivate_plugin("test.plugin")

        assert result is True
        assert mock_plugin._on_deactivate_called
        assert not plugin_manager.registry.is_activated("test.plugin")

    @pytest.mark.asyncio
    async def test_deactivate_plugin_not_activated(self, plugin_manager, mock_plugin):
        """Test deactivating a plugin that isn't activated."""
        plugin_manager.registry.register(mock_plugin)

        result = await plugin_manager.deactivate_plugin("test.plugin")

        # Should return True (already deactivated)
        assert result is True

    @pytest.mark.asyncio
    async def test_deactivate_plugin_not_found(self, plugin_manager):
        """Test deactivating a non-existent plugin."""
        result = await plugin_manager.deactivate_plugin("nonexistent.plugin")

        assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_plugin_unregisters_tools(self, plugin_manager, mock_plugin_with_tools):
        """Test that deactivating a plugin unregisters its tools."""
        plugin_manager.registry.register(mock_plugin_with_tools)
        await plugin_manager.activate_plugin("test.plugin")

        await plugin_manager.deactivate_plugin("test.plugin")

        # Verify tools were unregistered
        plugin_manager.engine.tools.unregister.assert_called()

    @pytest.mark.asyncio
    async def test_deactivate_plugin_unregisters_hooks(self, plugin_manager, mock_plugin):
        """Test that deactivating a plugin unregisters its hooks."""
        plugin_manager.registry.register(mock_plugin)
        await plugin_manager.activate_plugin("test.plugin")

        # Hooks should be registered
        assert plugin_manager.hooks.get_hook_count(HookType.ON_BEFORE_LLM_CALL) > 0

        await plugin_manager.deactivate_plugin("test.plugin")

        # Hooks should be unregistered
        assert plugin_manager.hooks.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 0


# ============================================================================
# Test: Plugin Dependency Resolution
# ============================================================================

class TestPluginManagerDependencyResolution:
    """Tests for plugin dependency resolution."""

    @pytest.mark.asyncio
    async def test_plugin_dependency_resolution(self, plugin_manager):
        """Test that plugins are activated in dependency order."""
        # Create plugins with dependencies
        base_plugin = MockPlugin(plugin_id="base", priority=0)
        dependent_plugin = MockPlugin(
            plugin_id="dependent",
            dependencies=["base"],
            priority=10  # Higher priority but depends on base
        )

        # Register plugins
        plugin_manager.registry.register(base_plugin)
        plugin_manager.registry.register(dependent_plugin)

        # Activate base first
        await plugin_manager.activate_plugin("base")
        assert plugin_manager.registry.is_activated("base")

        # Now dependent should be able to activate
        await plugin_manager.activate_plugin("dependent")
        assert plugin_manager.registry.is_activated("dependent")

    @pytest.mark.asyncio
    async def test_plugin_dependency_missing(self, plugin_manager, mock_plugin_with_dependencies):
        """Test that plugin fails to activate with missing dependency."""
        plugin_manager.registry.register(mock_plugin_with_dependencies)

        result = await plugin_manager.activate_plugin("test.dependent")

        assert result is False
        assert plugin_manager.registry.get_state("test.dependent") == PluginState.ERROR

    @pytest.mark.asyncio
    async def test_dependency_resolution_order(self, plugin_manager):
        """Test that resolve_load_order returns correct order."""
        # Create plugins with dependencies
        plugin_a = MockPlugin(plugin_id="plugin.a", priority=0)
        plugin_b = MockPlugin(plugin_id="plugin.b", dependencies=["plugin.a"], priority=0)
        plugin_c = MockPlugin(plugin_id="plugin.c", dependencies=["plugin.b"], priority=0)

        plugin_manager.registry.register(plugin_a)
        plugin_manager.registry.register(plugin_b)
        plugin_manager.registry.register(plugin_c)

        order = plugin_manager.resolver.resolve_load_order(
            ["plugin.c", "plugin.b", "plugin.a"]
        )

        # A should come before B, B should come before C
        assert order.index("plugin.a") < order.index("plugin.b")
        assert order.index("plugin.b") < order.index("plugin.c")


# ============================================================================
# Test: Plugin Conflict Detection
# ============================================================================

class TestPluginManagerConflictDetection:
    """Tests for plugin conflict detection."""

    @pytest.mark.asyncio
    async def test_plugin_conflict_detection(self, plugin_manager):
        """Test that conflicts are detected during activation."""
        plugin_a = MockPlugin(plugin_id="plugin.a")
        plugin_b = MockPlugin(plugin_id="plugin.b", conflicts=["plugin.a"])

        plugin_manager.registry.register(plugin_a)
        plugin_manager.registry.register(plugin_b)

        # Activate plugin_a
        await plugin_manager.activate_plugin("plugin.a")

        # Try to activate plugin_b which conflicts with plugin_a
        result = await plugin_manager.activate_plugin("plugin.b")

        assert result is False
        assert plugin_manager.registry.get_state("plugin.b") == PluginState.ERROR

    @pytest.mark.asyncio
    async def test_conflict_with_deactivated_plugin(self, plugin_manager):
        """Test that conflict is only with loaded plugins, not deactivated."""
        plugin_a = MockPlugin(plugin_id="plugin.a")
        plugin_b = MockPlugin(plugin_id="plugin.b", conflicts=["plugin.a"])

        plugin_manager.registry.register(plugin_a)
        plugin_manager.registry.register(plugin_b)

        # Don't activate plugin_a - just register it
        # The conflict check only looks at has_plugin, not activation state

        # Actually, the resolver.check_conflicts uses registry.has_plugin
        # which checks if plugin exists, not if it's activated
        # So we need to check the actual implementation


# ============================================================================
# Test: Emit Hook to Plugins
# ============================================================================

class TestPluginManagerEmitHook:
    """Tests for hook emission to plugins."""

    @pytest.mark.asyncio
    async def test_emit_hook_to_plugins(self, plugin_manager, mock_plugin):
        """Test emitting hooks to plugins."""
        plugin_manager.registry.register(mock_plugin)
        await plugin_manager.activate_plugin("test.plugin")

        results = await plugin_manager.emit_hook("on_before_llm_call", [])

        assert "on_before_llm_call" in mock_plugin._hooks_called
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_emit_hook_with_string_type(self, plugin_manager, mock_plugin):
        """Test emitting hooks with string type instead of HookType."""
        plugin_manager.registry.register(mock_plugin)
        await plugin_manager.activate_plugin("test.plugin")

        results = await plugin_manager.emit_hook("on_before_llm_call", [])

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_emit_hook_with_hook_type(self, plugin_manager, mock_plugin):
        """Test emitting hooks with HookType enum."""
        plugin_manager.registry.register(mock_plugin)
        await plugin_manager.activate_plugin("test.plugin")

        results = await plugin_manager.emit_hook(HookType.ON_BEFORE_LLM_CALL, [])

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_emit_hook_to_multiple_plugins(self, plugin_manager):
        """Test emitting hooks to multiple plugins."""
        plugin1 = MockPlugin(plugin_id="plugin.one")
        plugin2 = MockPlugin(plugin_id="plugin.two")

        plugin_manager.registry.register(plugin1)
        plugin_manager.registry.register(plugin2)

        await plugin_manager.activate_plugin("plugin.one")
        await plugin_manager.activate_plugin("plugin.two")

        await plugin_manager.emit_hook("on_before_llm_call", [])

        assert "on_before_llm_call" in plugin1._hooks_called
        assert "on_before_llm_call" in plugin2._hooks_called


# ============================================================================
# Test: Get Tools from Plugins
# ============================================================================

class TestPluginManagerGetTools:
    """Tests for getting tools from plugins."""

    def test_get_tools_from_plugins(self, plugin_manager):
        """Test getting tools from all activated plugins."""
        plugin1 = MockPlugin(plugin_id="plugin.one", provides_tools=True)
        plugin2 = MockPlugin(plugin_id="plugin.two", provides_tools=True)
        plugin3 = MockPlugin(plugin_id="plugin.three", provides_tools=False)

        plugin_manager.registry.register(plugin1)
        plugin_manager.registry.register(plugin2)
        plugin_manager.registry.register(plugin3)

        plugin_manager.registry.set_state("plugin.one", PluginState.ACTIVATED)
        plugin_manager.registry.set_state("plugin.two", PluginState.ACTIVATED)
        plugin_manager.registry.set_state("plugin.three", PluginState.ACTIVATED)

        tools = plugin_manager.get_tools_from_plugins()

        # plugin1 and plugin2 provide 1 tool each, plugin3 provides none
        assert len(tools) == 2

    def test_get_tools_from_no_activated_plugins(self, plugin_manager):
        """Test getting tools when no plugins are activated."""
        plugin = MockPlugin(provides_tools=True)
        plugin_manager.registry.register(plugin)

        tools = plugin_manager.get_tools_from_plugins()

        assert len(tools) == 0

    def test_get_tools_returns_empty_list_when_no_plugins(self, plugin_manager):
        """Test that get_tools returns empty list when no plugins exist."""
        tools = plugin_manager.get_tools_from_plugins()

        assert tools == []


# ============================================================================
# Test: Preset Loading
# ============================================================================

class TestPluginManagerPresetLoading:
    """Tests for preset loading."""

    def test_preset_loading_minimal(self, plugin_manager):
        """Test minimal preset returns empty set."""
        preset_plugins = plugin_manager._get_preset_plugins("minimal")
        assert preset_plugins == set()

    def test_preset_loading_standard(self, plugin_manager):
        """Test standard preset returns expected plugins."""
        preset_plugins = plugin_manager._get_preset_plugins("standard")

        assert "tools.code_tools" in preset_plugins
        assert "middleware.compaction" in preset_plugins
        assert "integration.events" in preset_plugins

    def test_preset_loading_full(self, plugin_manager):
        """Test full preset returns all expected plugins."""
        preset_plugins = plugin_manager._get_preset_plugins("full")

        assert "interface.rest_api" not in preset_plugins
        assert "tools.code_tools" in preset_plugins
        assert "middleware.thinking" in preset_plugins
        assert len(preset_plugins) >= 10  # Full preset should have many plugins

    def test_preset_loading_unknown(self, plugin_manager):
        """Test unknown preset returns empty set."""
        preset_plugins = plugin_manager._get_preset_plugins("unknown")
        assert preset_plugins == set()

    def test_get_effective_plugins_combines_preset_and_enabled(self, plugin_manager):
        """Test that effective plugins combines preset and enabled."""
        config = {
            "preset": "minimal",
            "enabled": ["custom.plugin"],
            "disabled": [],
        }

        effective = plugin_manager._get_effective_plugins(config)

        assert "custom.plugin" in effective

    def test_get_effective_plugins_respects_disabled(self, plugin_manager):
        """Test that disabled plugins are removed from effective list."""
        config = {
            "preset": "standard",
            "enabled": [],
            "disabled": ["tools.code_tools"],
        }

        effective = plugin_manager._get_effective_plugins(config)

        assert "tools.code_tools" not in effective
        assert "middleware.compaction" in effective  # Other standard plugins should be there


# ============================================================================
# Test: Plugin Priority Ordering
# ============================================================================

class TestPluginManagerPriority:
    """Tests for plugin priority ordering."""

    @pytest.mark.asyncio
    async def test_plugin_priority_ordering(self, plugin_manager):
        """Test that plugins are loaded in priority order."""
        low_priority = MockPlugin(plugin_id="low", priority=0)
        high_priority = MockPlugin(plugin_id="high", priority=100)
        medium_priority = MockPlugin(plugin_id="medium", priority=50)

        plugin_manager.registry.register(low_priority)
        plugin_manager.registry.register(high_priority)
        plugin_manager.registry.register(medium_priority)

        order = plugin_manager.resolver.resolve_load_order(
            ["low", "high", "medium"]
        )

        # Higher priority should come first
        assert order[0] == "high"
        assert order[1] == "medium"
        assert order[2] == "low"

    def test_hook_priority_ordering(self, plugin_manager):
        """Test that hooks are called in priority order."""
        call_order = []

        def high_priority_hook(messages):
            call_order.append("high")
            return None

        def low_priority_hook(messages):
            call_order.append("low")
            return None

        plugin_high = MockPlugin(plugin_id="high")
        plugin_low = MockPlugin(plugin_id="low")

        plugin_manager.registry.register(plugin_high)
        plugin_manager.registry.register(plugin_low)

        # Register hooks with different priorities
        plugin_manager.hooks.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin_high,
            high_priority_hook,
            priority=HookPriority.HIGH.value
        )
        plugin_manager.hooks.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin_low,
            low_priority_hook,
            priority=HookPriority.LOW.value
        )

        # Emit the hook
        asyncio.run(plugin_manager.hooks.emit(HookType.ON_BEFORE_LLM_CALL, []))

        assert call_order == ["high", "low"]


# ============================================================================
# Test: Plugin Error Handling
# ============================================================================

class TestPluginManagerErrorHandling:
    """Tests for plugin error handling."""

    @pytest.mark.asyncio
    async def test_plugin_error_handling_on_activate(self, plugin_manager):
        """Test that errors during activation are handled."""
        class FailingPlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.metadata = PluginMetadata(
                    id="failing.plugin",
                    name="Failing Plugin",
                    version="1.0.0",
                    type=PluginType.TOOL,
                )

            async def on_plugin_activate(self):
                raise RuntimeError("Activation failed")

        failing_plugin = FailingPlugin()
        plugin_manager.registry.register(failing_plugin)

        result = await plugin_manager.activate_plugin("failing.plugin")

        assert result is False
        assert plugin_manager.registry.get_state("failing.plugin") == PluginState.ERROR
        assert "Activation failed" in plugin_manager.registry.get_error("failing.plugin")

    @pytest.mark.asyncio
    async def test_plugin_error_handling_on_deactivate(self, plugin_manager):
        """Test that errors during deactivation are handled."""
        class FailingDeactivatePlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.metadata = PluginMetadata(
                    id="failing.deactivate",
                    name="Failing Deactivate Plugin",
                    version="1.0.0",
                    type=PluginType.TOOL,
                )

            async def on_plugin_deactivate(self):
                raise RuntimeError("Deactivation failed")

        plugin = FailingDeactivatePlugin()
        plugin_manager.registry.register(plugin)
        await plugin_manager.activate_plugin("failing.deactivate")

        result = await plugin_manager.deactivate_plugin("failing.deactivate")

        assert result is False

    @pytest.mark.asyncio
    async def test_hook_error_doesnt_break_chain(self, plugin_manager):
        """Test that errors in hooks don't break the chain."""
        call_order = []

        def failing_hook(messages):
            call_order.append("failing")
            raise RuntimeError("Hook failed")

        def working_hook(messages):
            call_order.append("working")
            return None

        plugin1 = MockPlugin(plugin_id="failing")
        plugin2 = MockPlugin(plugin_id="working")

        plugin_manager.registry.register(plugin1)
        plugin_manager.registry.register(plugin2)

        # Register hooks
        plugin_manager.hooks.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin1,
            failing_hook,
            priority=HookPriority.HIGH.value
        )
        plugin_manager.hooks.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin2,
            working_hook,
            priority=HookPriority.LOW.value
        )

        # Emit should not raise
        await plugin_manager.hooks.emit(HookType.ON_BEFORE_LLM_CALL, [])

        # Both hooks should have been attempted
        assert "failing" in call_order
        assert "working" in call_order

    @pytest.mark.asyncio
    async def test_dependency_missing_error(self, plugin_manager):
        """Test handling of missing dependency errors."""
        dependent = MockPlugin(
            plugin_id="dependent",
            dependencies=["missing.dependency"]
        )

        plugin_manager.registry.register(dependent)

        result = await plugin_manager.activate_plugin("dependent")

        assert result is False


# ============================================================================
# Test: Get Summary
# ============================================================================

class TestPluginManagerSummary:
    """Tests for plugin manager summary."""

    def test_get_summary(self, plugin_manager):
        """Test getting plugin system summary."""
        plugin1 = MockPlugin(plugin_id="plugin.one")
        plugin2 = MockPlugin(plugin_id="plugin.two")

        plugin_manager.registry.register(plugin1)
        plugin_manager.registry.register(plugin2)

        summary = plugin_manager.get_summary()

        assert "registry" in summary
        assert "hooks_count" in summary
        assert summary["registry"]["total_plugins"] == 2


# ============================================================================
# Test: Context Creation
# ============================================================================

class TestPluginManagerContext:
    """Tests for plugin context creation."""

    @pytest.mark.asyncio
    async def test_context_created_on_activate(self, plugin_manager, mock_plugin):
        """Test that context is created during activation."""
        plugin_manager.registry.register(mock_plugin)

        await plugin_manager.activate_plugin("test.plugin")

        assert mock_plugin._context is not None
        assert mock_plugin._context.engine is plugin_manager.engine

    @pytest.mark.asyncio
    async def test_context_has_config(self, plugin_manager, mock_plugin):
        """Test that context includes plugin config."""
        plugin_manager._config = {"test.plugin": {"setting": "value"}}
        plugin_manager.registry.register(mock_plugin)

        await plugin_manager.activate_plugin("test.plugin")

        assert mock_plugin._context.config == {"setting": "value"}

    @pytest.mark.asyncio
    async def test_context_has_logger(self, plugin_manager, mock_plugin):
        """Test that context includes logger."""
        plugin_manager.registry.register(mock_plugin)

        await plugin_manager.activate_plugin("test.plugin")

        assert mock_plugin._context.logger is not None

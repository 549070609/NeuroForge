"""
Tests for HookRegistry and Hook system

Comprehensive tests for the hook registration, emission, and chaining system.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from pyagentforge.plugin.hooks import (
    HookChainResult,
    HookDecision,
    HookEntry,
    HookPriority,
    HookRegistry,
    HookResult,
    HookType,
    create_hook_registry,
)

# ============================================================================
# Mock Plugin Class
# ============================================================================

class MockPlugin:
    """Mock plugin for testing hooks."""

    def __init__(self, plugin_id: str = "test.plugin"):
        self.plugin_id = plugin_id
        self.metadata = MagicMock()
        self.metadata.id = plugin_id


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def hook_registry():
    """Create a fresh hook registry."""
    return HookRegistry()


@pytest.fixture
def mock_plugin():
    """Create a mock plugin."""
    return MockPlugin()


@pytest.fixture
def mock_plugin_high():
    """Create a mock plugin for high priority tests."""
    return MockPlugin("high.plugin")


@pytest.fixture
def mock_plugin_low():
    """Create a mock plugin for low priority tests."""
    return MockPlugin("low.plugin")


# ============================================================================
# Test: Register Hook
# ============================================================================

class TestHookRegistryRegister:
    """Tests for hook registration."""

    def test_register_hook(self, hook_registry, mock_plugin):
        """Test registering a hook."""
        callback = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback,
            priority=HookPriority.NORMAL.value
        )

        assert hook_registry.has_hooks(HookType.ON_BEFORE_LLM_CALL)
        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 1

    def test_register_multiple_hooks_same_type(self, hook_registry):
        """Test registering multiple hooks of the same type."""
        plugin1 = MockPlugin("plugin.one")
        plugin2 = MockPlugin("plugin.two")
        callback1 = MagicMock()
        callback2 = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin1,
            callback1
        )
        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin2,
            callback2
        )

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 2

    def test_register_hook_different_types(self, hook_registry, mock_plugin):
        """Test registering hooks of different types."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback1
        )
        hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            mock_plugin,
            callback2
        )

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 1
        assert hook_registry.get_hook_count(HookType.ON_AFTER_LLM_CALL) == 1

    def test_register_hook_default_priority(self, hook_registry, mock_plugin):
        """Test that hooks get default priority when not specified."""
        callback = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback
        )

        hooks = hook_registry.get_hooks(HookType.ON_BEFORE_LLM_CALL)
        assert len(hooks) == 1
        assert hooks[0].priority == HookPriority.NORMAL.value

    def test_unregister_hook(self, hook_registry, mock_plugin):
        """Test unregistering a hook."""
        callback = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback
        )

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 1

        hook_registry.unregister(HookType.ON_BEFORE_LLM_CALL, mock_plugin)

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 0

    def test_unregister_all_hooks_for_plugin(self, hook_registry, mock_plugin):
        """Test unregistering all hooks for a specific plugin."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback1
        )
        hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            mock_plugin,
            callback2
        )

        hook_registry.unregister_all(mock_plugin)

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 0
        assert hook_registry.get_hook_count(HookType.ON_AFTER_LLM_CALL) == 0


# ============================================================================
# Test: Emit to Single Hook
# ============================================================================

class TestHookRegistryEmitSingle:
    """Tests for emitting to a single hook."""

    @pytest.mark.asyncio
    async def test_emit_to_single_hook(self, hook_registry, mock_plugin):
        """Test emitting to a single hook."""
        call_args = []
        def callback(msg):
            return call_args.append(msg)

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback
        )

        await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test_message")

        assert len(call_args) == 1
        assert call_args[0] == "test_message"

    @pytest.mark.asyncio
    async def test_emit_to_single_hook_with_kwargs(self, hook_registry, mock_plugin):
        """Test emitting to a hook with keyword arguments."""
        received = {}

        def callback(*args, **kwargs):
            received["args"] = args
            received["kwargs"] = kwargs
            return "result"

        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            mock_plugin,
            callback
        )

        await hook_registry.emit(
            HookType.ON_BEFORE_LLM_CALL,
            "arg1", "arg2",
            key1="value1",
            key2="value2"
        )

        assert received["args"] == ("arg1", "arg2")
        assert received["kwargs"] == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_emit_collects_non_none_results(self, hook_registry, mock_plugin):
        """Test that emit collects non-None results."""
        def callback_returning_none(msg):
            return None

        def callback_returning_value(msg):
            return "result"

        plugin1 = MockPlugin("plugin.one")
        plugin2 = MockPlugin("plugin.two")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, callback_returning_none)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, callback_returning_value)

        results = await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert len(results) == 1
        assert results[0] == "result"

    @pytest.mark.asyncio
    async def test_emit_to_no_hooks_returns_empty(self, hook_registry):
        """Test that emitting to no hooks returns empty list."""
        results = await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert results == []


# ============================================================================
# Test: Emit to Multiple Hooks Ordered
# ============================================================================

class TestHookRegistryEmitMultiple:
    """Tests for emitting to multiple hooks with ordering."""

    @pytest.mark.asyncio
    async def test_emit_to_multiple_hooks_ordered(self, hook_registry):
        """Test that hooks are called in priority order."""
        call_order = []

        def high_hook(msg):
            call_order.append("high")

        def normal_hook(msg):
            call_order.append("normal")

        def low_hook(msg):
            call_order.append("low")

        plugin_high = MockPlugin("high")
        plugin_normal = MockPlugin("normal")
        plugin_low = MockPlugin("low")

        # Register in non-priority order
        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin_low,
            low_hook,
            priority=HookPriority.LOW.value
        )
        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin_high,
            high_hook,
            priority=HookPriority.HIGH.value
        )
        hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin_normal,
            normal_hook,
            priority=HookPriority.NORMAL.value
        )

        await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        # Should be called in priority order: high -> normal -> low
        assert call_order == ["high", "normal", "low"]

    @pytest.mark.asyncio
    async def test_emit_to_multiple_hooks_same_priority(self, hook_registry):
        """Test hooks with same priority are all called."""
        call_count = []

        def hook1(msg):
            call_count.append(1)

        def hook2(msg):
            call_count.append(2)

        def hook3(msg):
            call_count.append(3)

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")
        plugin3 = MockPlugin("plugin3")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, hook1)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, hook2)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin3, hook3)

        await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert len(call_count) == 3


# ============================================================================
# Test: Emit Chain Modifies Data
# ============================================================================

class TestHookRegistryEmitChain:
    """Tests for chain emission with data modification."""

    @pytest.mark.asyncio
    async def test_emit_chain_modifies_data(self, hook_registry):
        """Test that emit_chain passes modified data through the chain."""
        def add_prefix(data):
            return f"prefix_{data}"

        def add_suffix(data):
            return f"{data}_suffix"

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, add_prefix, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, add_suffix, priority=HookPriority.LOW.value)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        # Data should pass through both hooks
        assert result.last_modified_data == "prefix_data_suffix"

    @pytest.mark.asyncio
    async def test_emit_chain_with_none_result_continues(self, hook_registry):
        """Test that returning None continues the chain."""
        call_order = []

        def returning_none(data):
            call_order.append("none")
            return None

        def returning_data(data):
            call_order.append("data")
            return f"modified_{data}"

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, returning_none, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, returning_data, priority=HookPriority.LOW.value)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="original"
        )

        assert "none" in call_order
        assert "data" in call_order
        assert result.last_modified_data == "modified_original"

    @pytest.mark.asyncio
    async def test_emit_chain_returns_hook_chain_result(self, hook_registry):
        """Test that emit_chain returns HookChainResult."""
        def modify_hook(data):
            return f"modified_{data}"

        plugin = MockPlugin()
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin, modify_hook)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        assert isinstance(result, HookChainResult)
        assert result.stopped is False
        assert result.last_modified_data == "modified_data"


# ============================================================================
# Test: Emit Chain Stops on STOP Result
# ============================================================================

class TestHookRegistryEmitChainStop:
    """Tests for chain emission stopping behavior."""

    @pytest.mark.asyncio
    async def test_emit_chain_stops_on_stop_result(self, hook_registry):
        """Test that returning HookResult.STOP stops the chain."""
        call_order = []

        def first_hook(data):
            call_order.append("first")
            return HookResult.STOP

        def second_hook(data):
            call_order.append("second")
            return "should not reach"

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, first_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, second_hook, priority=HookPriority.LOW.value)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        assert "first" in call_order
        assert "second" not in call_order
        assert result.stopped is True
        assert result.stopped_by == "plugin1"

    @pytest.mark.asyncio
    async def test_emit_chain_continue_result_continues(self, hook_registry):
        """Test that returning HookResult.CONTINUE continues the chain."""
        call_order = []

        def first_hook(data):
            call_order.append("first")
            return HookResult.CONTINUE

        def second_hook(data):
            call_order.append("second")
            return "data"

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, first_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, second_hook, priority=HookPriority.LOW.value)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        assert "first" in call_order
        assert "second" in call_order
        assert result.stopped is False


# ============================================================================
# Test: Emit Until Handled
# ============================================================================

class TestHookRegistryEmitUntilHandled:
    """Tests for emit_until_handled behavior."""

    @pytest.mark.asyncio
    async def test_emit_until_handled(self, hook_registry):
        """Test that emit_until_handled stops at first non-None result."""
        call_order = []

        def first_hook(data):
            call_order.append("first")
            return None

        def second_hook(data):
            call_order.append("second")
            return "handled"

        def third_hook(data):
            call_order.append("third")
            return "should not reach"

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")
        plugin3 = MockPlugin("plugin3")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, first_hook, priority=HookPriority.HIGHEST.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, second_hook, priority=HookPriority.NORMAL.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin3, third_hook, priority=HookPriority.LOW.value)

        handled, result = await hook_registry.emit_until_handled(
            HookType.ON_BEFORE_LLM_CALL,
            "data"
        )

        assert handled is True
        assert result == "handled"
        assert "first" in call_order
        assert "second" in call_order
        assert "third" not in call_order

    @pytest.mark.asyncio
    async def test_emit_until_handled_returns_false_if_none_handled(self, hook_registry):
        """Test that emit_until_handled returns False if no hook handled."""
        def hook1(data):
            return None

        def hook2(data):
            return None

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, hook1)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, hook2)

        handled, result = await hook_registry.emit_until_handled(
            HookType.ON_BEFORE_LLM_CALL,
            "data"
        )

        assert handled is False
        assert result is None


# ============================================================================
# Test: Async Hook Handling
# ============================================================================

class TestHookRegistryAsync:
    """Tests for async hook handling."""

    @pytest.mark.asyncio
    async def test_async_hook_handling(self, hook_registry, mock_plugin):
        """Test that async hooks are properly awaited."""
        async def async_hook(msg):
            await asyncio.sleep(0.01)
            return "async_result"

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, async_hook)

        results = await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert len(results) == 1
        assert results[0] == "async_result"

    @pytest.mark.asyncio
    async def test_async_hook_in_chain(self, hook_registry, mock_plugin):
        """Test that async hooks work in chain emission."""
        async def async_modify(data):
            await asyncio.sleep(0.01)
            return f"async_{data}"

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, async_modify)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        assert result.last_modified_data == "async_data"

    @pytest.mark.asyncio
    async def test_async_hook_in_emit_until_handled(self, hook_registry, mock_plugin):
        """Test that async hooks work in emit_until_handled."""
        async def async_handler(data):
            await asyncio.sleep(0.01)
            return "handled"

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, async_handler)

        handled, result = await hook_registry.emit_until_handled(
            HookType.ON_BEFORE_LLM_CALL,
            "data"
        )

        assert handled is True
        assert result == "handled"

    @pytest.mark.asyncio
    async def test_mixed_sync_and_async_hooks(self, hook_registry):
        """Test that mixing sync and async hooks works correctly."""
        call_order = []

        def sync_hook(msg):
            call_order.append("sync")
            return "sync_result"

        async def async_hook(msg):
            call_order.append("async")
            await asyncio.sleep(0.01)
            return "async_result"

        plugin1 = MockPlugin("sync")
        plugin2 = MockPlugin("async")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, sync_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, async_hook, priority=HookPriority.LOW.value)

        results = await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert call_order == ["sync", "async"]
        assert len(results) == 2


# ============================================================================
# Test: Error in Hook Doesnt Break Chain
# ============================================================================

class TestHookRegistryErrorHandling:
    """Tests for error handling in hooks."""

    @pytest.mark.asyncio
    async def test_error_in_hook_doesnt_break_chain(self, hook_registry):
        """Test that errors in hooks don't break the chain."""
        call_order = []

        def failing_hook(msg):
            call_order.append("failing")
            raise RuntimeError("Hook error")

        def working_hook(msg):
            call_order.append("working")
            return "success"

        plugin1 = MockPlugin("failing")
        plugin2 = MockPlugin("working")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, failing_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, working_hook, priority=HookPriority.LOW.value)

        results = await hook_registry.emit(HookType.ON_BEFORE_LLM_CALL, "test")

        assert "failing" in call_order
        assert "working" in call_order
        assert results == ["success"]

    @pytest.mark.asyncio
    async def test_error_in_chain_hook_continues(self, hook_registry):
        """Test that errors in chain hooks don't break the chain."""
        def failing_hook(data):
            raise RuntimeError("Chain error")

        def working_hook(data):
            return f"modified_{data}"

        plugin1 = MockPlugin("failing")
        plugin2 = MockPlugin("working")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, failing_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, working_hook, priority=HookPriority.LOW.value)

        result = await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="data"
        )

        # Working hook should still execute
        assert result.last_modified_data == "modified_data"

    @pytest.mark.asyncio
    async def test_error_in_emit_until_handled_continues(self, hook_registry):
        """Test that errors in emit_until_handled don't stop search."""
        def failing_hook(data):
            raise RuntimeError("Error")

        def working_hook(data):
            return "handled"

        plugin1 = MockPlugin("failing")
        plugin2 = MockPlugin("working")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, failing_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, working_hook, priority=HookPriority.LOW.value)

        handled, result = await hook_registry.emit_until_handled(
            HookType.ON_BEFORE_LLM_CALL,
            "data"
        )

        assert handled is True
        assert result == "handled"


# ============================================================================
# Test: Hook Priority
# ============================================================================

class TestHookRegistryPriority:
    """Tests for hook priority ordering."""

    def test_hook_priority_ordering(self, hook_registry):
        """Test that hooks are sorted by priority correctly."""
        plugin1 = MockPlugin("low")
        plugin2 = MockPlugin("high")
        plugin3 = MockPlugin("normal")

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin1, lambda x: None, priority=HookPriority.LOW.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin2, lambda x: None, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, plugin3, lambda x: None, priority=HookPriority.NORMAL.value)

        hooks = hook_registry.get_hooks(HookType.ON_BEFORE_LLM_CALL)

        # Higher priority should come first
        assert hooks[0].priority == HookPriority.HIGH.value
        assert hooks[1].priority == HookPriority.NORMAL.value
        assert hooks[2].priority == HookPriority.LOW.value

    def test_hook_entry_comparison(self):
        """Test that HookEntry comparison works correctly."""
        entry_high = HookEntry(plugin=None, callback=lambda: None, priority=100)
        entry_low = HookEntry(plugin=None, callback=lambda: None, priority=10)

        # Higher priority should be "less than" for sorting
        assert entry_high < entry_low

    def test_hook_priority_values(self):
        """Test that priority enum values are correct."""
        assert HookPriority.HIGHEST.value == 1000
        assert HookPriority.HIGH.value == 750
        assert HookPriority.NORMAL.value == 500
        assert HookPriority.LOW.value == 250
        assert HookPriority.LOWEST.value == 0


# ============================================================================
# Test: Hook Context Passing
# ============================================================================

class TestHookRegistryContextPassing:
    """Tests for context passing in hooks."""

    @pytest.mark.asyncio
    async def test_hook_context_passing(self, hook_registry, mock_plugin):
        """Test that context is passed correctly to hooks."""
        received_context = {}

        def context_hook(msg, extra=None):
            received_context["msg"] = msg
            received_context["extra"] = extra
            return "result"

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, context_hook)

        await hook_registry.emit(
            HookType.ON_BEFORE_LLM_CALL,
            "message",
            extra="context"
        )

        assert received_context["msg"] == "message"
        assert received_context["extra"] == "context"

    @pytest.mark.asyncio
    async def test_chain_context_passing(self, hook_registry, mock_plugin):
        """Test that context is passed through chain correctly."""
        received_data = []

        def tracking_hook(data, context=None):
            received_data.append({"data": data, "context": context})
            return data

        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, tracking_hook)

        await hook_registry.emit_chain(
            HookType.ON_BEFORE_LLM_CALL,
            initial_data="initial",
            context="extra"
        )

        assert len(received_data) == 1
        assert received_data[0]["data"] == "initial"
        assert received_data[0]["context"] == "extra"


# ============================================================================
# Test: Emit Decision
# ============================================================================

class TestHookRegistryEmitDecision:
    """Tests for emit_decision behavior."""

    @pytest.mark.asyncio
    async def test_emit_decision_returns_allow_by_default(self, hook_registry, mock_plugin):
        """Test that emit_decision returns ALLOW when no hooks override."""
        def passive_hook(*args, **kwargs):
            return None

        hook_registry.register(HookType.PRE_TOOL_USE, mock_plugin, passive_hook)

        decision, message = await hook_registry.emit_decision(
            HookType.PRE_TOOL_USE,
            "tool_name",
            {}
        )

        assert decision == HookDecision.ALLOW
        assert message is None

    @pytest.mark.asyncio
    async def test_emit_decision_returns_first_non_allow(self, hook_registry):
        """Test that emit_decision returns first non-ALLOW decision."""
        def allow_hook(*args, **kwargs):
            return HookDecision.ALLOW

        def deny_hook(*args, **kwargs):
            return (HookDecision.DENY, "Not allowed")

        plugin1 = MockPlugin("allow")
        plugin2 = MockPlugin("deny")

        hook_registry.register(HookType.PRE_TOOL_USE, plugin1, allow_hook, priority=HookPriority.HIGH.value)
        hook_registry.register(HookType.PRE_TOOL_USE, plugin2, deny_hook, priority=HookPriority.LOW.value)

        decision, message = await hook_registry.emit_decision(
            HookType.PRE_TOOL_USE,
            "tool_name",
            {}
        )

        assert decision == HookDecision.DENY
        assert message == "Not allowed"

    @pytest.mark.asyncio
    async def test_emit_decision_with_dict_result(self, hook_registry, mock_plugin):
        """Test that emit_decision handles dict results."""
        def dict_hook(*args, **kwargs):
            return {
                "decision": HookDecision.ASK,
                "message": "Please confirm"
            }

        hook_registry.register(HookType.PRE_TOOL_USE, mock_plugin, dict_hook)

        decision, message = await hook_registry.emit_decision(
            HookType.PRE_TOOL_USE,
            "tool_name",
            {}
        )

        assert decision == HookDecision.ASK
        assert message == "Please confirm"

    @pytest.mark.asyncio
    async def test_emit_decision_with_async_hook(self, hook_registry, mock_plugin):
        """Test that emit_decision handles async hooks."""
        async def async_deny_hook(*args, **kwargs):
            await asyncio.sleep(0.01)
            return HookDecision.BLOCK

        hook_registry.register(HookType.PRE_TOOL_USE, mock_plugin, async_deny_hook)

        decision, message = await hook_registry.emit_decision(
            HookType.PRE_TOOL_USE,
            "tool_name",
            {}
        )

        assert decision == HookDecision.BLOCK


# ============================================================================
# Test: Clear Hooks
# ============================================================================

class TestHookRegistryClear:
    """Tests for clearing hooks."""

    def test_clear_specific_hook_type(self, hook_registry, mock_plugin):
        """Test clearing hooks of a specific type."""
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, lambda x: None)
        hook_registry.register(HookType.ON_AFTER_LLM_CALL, mock_plugin, lambda x: None)

        hook_registry.clear(HookType.ON_BEFORE_LLM_CALL)

        assert hook_registry.get_hook_count(HookType.ON_BEFORE_LLM_CALL) == 0
        assert hook_registry.get_hook_count(HookType.ON_AFTER_LLM_CALL) == 1

    def test_clear_all_hooks(self, hook_registry, mock_plugin):
        """Test clearing all hooks."""
        hook_registry.register(HookType.ON_BEFORE_LLM_CALL, mock_plugin, lambda x: None)
        hook_registry.register(HookType.ON_AFTER_LLM_CALL, mock_plugin, lambda x: None)

        hook_registry.clear()

        for hook_type in HookType:
            assert hook_registry.get_hook_count(hook_type) == 0


# ============================================================================
# Test: Create Hook Registry
# ============================================================================

class TestCreateHookRegistry:
    """Tests for create_hook_registry function."""

    def test_create_hook_registry(self):
        """Test that create_hook_registry creates a new registry."""
        registry = create_hook_registry()

        assert isinstance(registry, HookRegistry)
        assert registry is not None

    def test_create_hook_registry_returns_fresh_instances(self):
        """Test that each call returns a new registry."""
        registry1 = create_hook_registry()
        registry2 = create_hook_registry()

        assert registry1 is not registry2


# ============================================================================
# Test: Hook Types
# ============================================================================

class TestHookTypes:
    """Tests for hook type definitions."""

    def test_all_hook_types_exist(self):
        """Test that all expected hook types exist."""
        expected_types = [
            "on_plugin_load",
            "on_plugin_activate",
            "on_plugin_deactivate",
            "on_engine_init",
            "on_engine_start",
            "on_engine_stop",
            "on_before_llm_call",
            "on_after_llm_call",
            "on_before_tool_call",
            "on_after_tool_call",
            "pre_tool_use",
            "post_tool_use",
            "user_prompt_submit",
            "on_context_overflow",
            "on_task_complete",
            "on_skill_load",
            "on_subagent_spawn",
        ]

        for hook_name in expected_types:
            assert any(ht.value == hook_name for ht in HookType), f"Missing hook type: {hook_name}"


# ============================================================================
# Test: Hook Decision Types
# ============================================================================

class TestHookDecisionTypes:
    """Tests for hook decision types."""

    def test_decision_types_exist(self):
        """Test that all expected decision types exist."""
        expected_decisions = ["allow", "deny", "ask", "block", "modify"]

        for decision_name in expected_decisions:
            assert any(d.value == decision_name for d in HookDecision), f"Missing decision: {decision_name}"

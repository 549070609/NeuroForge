"""
Tests for new optimization features

Phase 1: ProcessCleanup
Phase 2: Hook Priority System
Phase 3: Recovery Executor
Phase 4: Session Recovery Plugin
Phase 5: Multi-level Config
Phase 6: Prompt Builder
"""

from unittest.mock import Mock

import pytest


class TestProcessCleanup:
    """Test ProcessCleanup functionality"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.kernel.cleanup import CleanupPriority, ProcessCleanup
        assert ProcessCleanup is not None
        assert CleanupPriority.CRITICAL.value == 100

    def test_register_callback(self):
        """Test callback registration"""
        from pyagentforge.kernel.cleanup import CleanupPriority, ProcessCleanup

        cleanup = ProcessCleanup()
        called = []

        def callback():
            called.append(1)

        cleanup.register(callback, name="test", priority=CleanupPriority.HIGH.value)
        assert cleanup._stats.total_registered == 1

    def test_register_async_callback(self):
        """Test async callback registration"""
        from pyagentforge.kernel.cleanup import ProcessCleanup

        cleanup = ProcessCleanup()

        async def async_callback():
            pass

        cleanup.register_async(async_callback, name="async_test")
        assert cleanup._stats.total_registered == 1

    @pytest.mark.asyncio
    async def test_cleanup_execution(self):
        """Test cleanup execution"""
        from pyagentforge.kernel.cleanup import ProcessCleanup

        cleanup = ProcessCleanup()
        called = []

        def sync_cb():
            called.append("sync")

        async def async_cb():
            called.append("async")

        cleanup.register(sync_cb, name="sync")
        cleanup.register_async(async_cb, name="async")

        stats = await cleanup.cleanup()
        assert stats.total_executed == 2
        assert "sync" in called
        assert "async" in called

    def test_unregister(self):
        """Test callback unregistration"""
        from pyagentforge.kernel.cleanup import ProcessCleanup

        cleanup = ProcessCleanup()

        cleanup.register(lambda: None, name="test")
        assert cleanup._stats.total_registered == 1

        result = cleanup.unregister("test")
        assert result is True
        assert cleanup._stats.total_registered == 0


class TestHookPriority:
    """Test Hook priority system"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.plugin.hooks import HookPriority, HookRegistry, HookResult
        assert HookRegistry is not None
        assert HookResult.CONTINUE.value == "continue"
        assert HookPriority.HIGH.value == 750

    def test_register_with_priority(self):
        """Test hook registration with priority"""
        from pyagentforge.plugin.hooks import HookPriority, HookRegistry, HookType

        registry = HookRegistry()
        plugin = Mock()
        plugin.metadata = Mock(id="test_plugin")

        registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            plugin,
            lambda: None,
            priority=HookPriority.HIGH.value,
        )

        hooks = registry.get_hooks(HookType.ON_BEFORE_LLM_CALL)
        assert len(hooks) == 1
        assert hooks[0].priority == HookPriority.HIGH.value

    @pytest.mark.asyncio
    async def test_priority_order(self):
        """Test hooks execute in priority order"""
        from pyagentforge.plugin.hooks import HookRegistry, HookType

        registry = HookRegistry()
        plugin = Mock()
        plugin.metadata = Mock(id="test_plugin")

        order = []

        async def low_hook():
            order.append("low")

        async def high_hook():
            order.append("high")

        registry.register(HookType.ON_BEFORE_LLM_CALL, plugin, low_hook, priority=100)
        registry.register(HookType.ON_BEFORE_LLM_CALL, plugin, high_hook, priority=500)

        await registry.emit(HookType.ON_BEFORE_LLM_CALL)

        # High priority should execute first
        assert order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_emit_until_handled(self):
        """Test emit_until_handled stops at first handler"""
        from pyagentforge.plugin.hooks import HookRegistry, HookType

        registry = HookRegistry()
        plugin = Mock()
        plugin.metadata = Mock(id="test_plugin")

        calls = []

        def not_handling():
            calls.append(1)
            return None

        def handling():
            calls.append(2)
            return "handled"

        registry.register(HookType.ON_CONTEXT_OVERFLOW, plugin, not_handling)
        registry.register(HookType.ON_CONTEXT_OVERFLOW, plugin, handling)

        handled, result = await registry.emit_until_handled(HookType.ON_CONTEXT_OVERFLOW)

        assert handled is True
        assert result == "handled"


class TestRecoveryExecutor:
    """Test RecoveryExecutor functionality"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.plugins.middleware.error_recovery.error_recovery import RecoveryExecutor, RecoveryStrategy
        assert RecoveryExecutor is not None
        assert RecoveryStrategy.TRUNCATE_MESSAGES.value == "truncate_messages"

    def test_strategies_defined(self):
        """Test all strategies have handlers"""
        from pyagentforge.plugins.middleware.error_recovery.error_recovery import RecoveryExecutor, RecoveryStrategy

        mock_context = Mock()
        mock_context.messages = []

        executor = RecoveryExecutor(mock_context)

        for strategy in RecoveryStrategy:
            assert strategy in executor._strategy_handlers

    @pytest.mark.asyncio
    async def test_truncate_messages(self):
        """Test truncate messages strategy"""
        from pyagentforge.plugins.middleware.error_recovery.error_recovery import RecoveryExecutor, RecoveryStrategy

        mock_context = Mock()
        mock_context.messages = [Mock() for _ in range(20)]
        mock_context.truncate = Mock(return_value=10)

        executor = RecoveryExecutor(mock_context)
        result = await executor.execute(RecoveryStrategy.TRUNCATE_MESSAGES)

        assert result.success is True
        assert result.messages_removed == 10


class TestMultiLevelConfig:
    """Test Multi-level configuration"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.config.multi_level import MultiLevelConfig
        assert MultiLevelConfig is not None

    def test_default_paths(self):
        """Test default config paths"""
        from pyagentforge.config.multi_level import MultiLevelConfig

        config = MultiLevelConfig()

        assert "pyagentforge" in str(config.user_config_path)
        assert config.project_config_path.name == "pyagentforge.yaml"

    def test_load_merged_empty(self):
        """Test loading with no config files"""
        from pyagentforge.config.multi_level import MultiLevelConfig

        config = MultiLevelConfig()
        merged = config.load_merged()

        assert isinstance(merged, dict)

    def test_generate_templates(self):
        """Test template generation"""
        from pyagentforge.config.multi_level import MultiLevelConfig

        config = MultiLevelConfig()

        user_template = config.generate_user_config_template()
        project_template = config.generate_project_config_template()

        assert "llm:" in user_template
        assert "agent:" in project_template


class TestPromptBuilder:
    """Test PromptBuilder functionality"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.utils.prompt_builder import PromptBuilder
        assert PromptBuilder is not None

    def test_add_section(self):
        """Test adding sections"""
        from pyagentforge.utils.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        builder.add_section("Hello", priority=100)
        builder.add_section("World", priority=50)

        assert builder.get_section_count() == 2

    def test_build_with_priority(self):
        """Test build respects priority"""
        from pyagentforge.utils.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        builder.add_section("Second", name="second", priority=50)
        builder.add_section("First", name="first", priority=100)

        result = builder.build()

        assert result == "First\n\nSecond"

    def test_variable_replacement(self):
        """Test variable replacement"""
        from pyagentforge.utils.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        builder.add_section("Hello {name}!", priority=100)
        builder.add_section("Task: {task}", priority=50)

        result = builder.build(name="World", task="Fix bug")

        assert "Hello World!" in result
        assert "Task: Fix bug" in result

    def test_chain_calls(self):
        """Test chain calls"""
        from pyagentforge.utils.prompt_builder import PromptBuilder

        builder = (
            PromptBuilder()
            .add_section("A", priority=1)
            .add_section("B", priority=2)
            .add_section("C", priority=3)
        )

        assert builder.get_section_count() == 3

    def test_add_section_if(self):
        """Test conditional section"""
        from pyagentforge.utils.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        builder.add_section_if(True, "Included", priority=100)
        builder.add_section_if(False, "Excluded", priority=50)

        assert builder.get_section_count() == 1

        result = builder.build()
        assert "Included" in result
        assert "Excluded" not in result


class TestSessionRecoveryPlugin:
    """Test SessionRecoveryPlugin"""

    def test_import(self):
        """Test import works"""
        from pyagentforge.plugins.integration.session_recovery import (
            SessionRecoveryConfig,
            SessionRecoveryPlugin,
        )
        assert SessionRecoveryPlugin is not None
        assert SessionRecoveryConfig is not None

    def test_config_defaults(self):
        """Test config defaults"""
        from pyagentforge.plugins.integration.session_recovery import SessionRecoveryConfig

        config = SessionRecoveryConfig()

        assert config.enabled is True
        assert config.auto_save is True
        assert config.auto_save_interval == 5

    def test_plugin_metadata(self):
        """Test plugin metadata"""
        from pyagentforge.plugins.integration.session_recovery import SessionRecoveryPlugin

        assert SessionRecoveryPlugin.metadata.id == "integration.session_recovery"
        assert SessionRecoveryPlugin.metadata.name == "Session Recovery"

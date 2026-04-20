"""
Dynamic Prompt Plugin

Integrates the DynamicPromptBuilder into the system.
"""

from typing import Any

from pyagentforge.agents.dynamic_prompt_builder import (
    DynamicPromptBuilder,
    PromptContext,
    create_prompt_context,
)
from pyagentforge.agents.metadata import BUILTIN_AGENTS
from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class DynamicPromptPlugin(Plugin):
    """
    Dynamic Prompt Plugin

    Integrates the DynamicPromptBuilder into the AgentEngine.
    Automatically updates system prompts when skills or agents change.
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="integration.dynamic_prompt",
            name="Dynamic Prompt Builder",
            version="1.0.0",
            type=PluginType.INTEGRATION,
            description="Generates dynamic system prompts based on available resources",
            author="PyAgentForge Team",
            dependencies=[],
            provides=["dynamic_prompt"],
            priority=50,  # Medium priority
        )

    def __init__(self):
        super().__init__()
        self._builder: DynamicPromptBuilder | None = None
        self._current_context: PromptContext | None = None
        self._enabled: bool = True

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时初始化"""
        await super().on_plugin_load(context)

        # Get configuration
        config = context.config.get("integration.dynamic_prompt", {})
        self._enabled = config.get("enabled", True)

        if self._enabled:
            # Initialize builder
            self._builder = DynamicPromptBuilder()

            context.logger.info("Dynamic Prompt plugin loaded")

    async def on_plugin_activate(self) -> None:
        """插件激活时"""
        await super().on_plugin_activate()

        if self._builder and self.context:
            # Initial prompt update
            await self._update_engine_prompt()

            self.context.logger.info("Dynamic Prompt plugin activated")

    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        return []

    async def on_skill_load(self, skill: Any) -> None:
        """
        技能加载时更新提示

        Args:
            skill: 加载的技能对象
        """
        if not self._enabled or not self._builder:
            return

        await self._update_engine_prompt()

    async def on_engine_start(self, engine: Any) -> None:
        """
        引擎启动时更新提示

        Args:
            engine: AgentEngine 实例
        """
        if not self._enabled or not self._builder:
            return

        await self._update_engine_prompt()

    async def _update_engine_prompt(self) -> None:
        """更新引擎的系统提示"""
        if not self._builder or not self.context:
            return

        try:
            # Build prompt context
            prompt_context = await self._build_prompt_context()

            if prompt_context:
                # Generate dynamic system prompt
                dynamic_prompt = self._builder.build_system_prompt(prompt_context)

                # Update engine's system prompt
                if self.context.engine and hasattr(self.context.engine, "config"):
                    # Prepend dynamic prompt to existing system prompt
                    base_prompt = self.context.engine.config.system_prompt
                    self.context.engine.config.system_prompt = (
                        f"{dynamic_prompt}\n\n---\n\n{base_prompt}"
                    )

                    self._current_context = prompt_context

                    self.context.logger.info(
                        f"Updated system prompt with dynamic content "
                        f"(agents: {len(prompt_context.available_agents)}, "
                        f"tools: {len(prompt_context.available_tools)}, "
                        f"skills: {len(prompt_context.available_skills)})"
                    )

        except Exception as e:
            if self.context:
                self.context.logger.error(f"Failed to update dynamic prompt: {e}")

    async def _build_prompt_context(self) -> PromptContext | None:
        """
        构建提示上下文

        Returns:
            PromptContext 或 None
        """
        if not self.context or not self.context.engine:
            return None

        engine = self.context.engine

        # Get available agents
        available_agents = list(BUILTIN_AGENTS.values())

        # Get available tools
        available_tools = []
        if hasattr(engine, "tools") and hasattr(engine.tools, "get_schemas"):
            schemas = engine.tools.get_schemas()
            for schema in schemas:
                if isinstance(schema, dict):
                    available_tools.append({
                        "name": schema.get("name", "unknown"),
                        "description": schema.get("description", ""),
                    })

        # Get available skills
        available_skills = []
        if hasattr(engine, "context") and hasattr(engine.context, "get_loaded_skills"):
            available_skills = list(engine.context.get_loaded_skills())

        # Get working directory
        working_directory = ""
        if hasattr(engine, "context") and hasattr(engine.context, "working_directory"):
            working_directory = engine.context.working_directory

        # Get model ID
        model_id = ""
        if hasattr(engine, "provider") and hasattr(engine.provider, "model"):
            model_id = engine.provider.model

        # Create context
        return create_prompt_context(
            available_agents=available_agents,
            available_tools=available_tools,
            available_skills=available_skills,
            working_directory=working_directory,
            model_id=model_id,
        )

    def get_current_prompt(self) -> str | None:
        """
        获取当前生成的动态提示

        Returns:
            当前提示字符串或 None
        """
        if not self._builder or not self._current_context:
            return None

        return self._builder.build_system_prompt(self._current_context)

    def force_update(self) -> bool:
        """
        强制更新动态提示

        Returns:
            是否成功更新
        """
        if not self._enabled or not self._builder:
            return False

        # Schedule async update
        import asyncio
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._update_engine_prompt())
            return True
        except RuntimeError:
            # No running loop
            asyncio.run(self._update_engine_prompt())
            return True

    def set_enabled(self, enabled: bool) -> None:
        """
        启用或禁用动态提示

        Args:
            enabled: 是否启用
        """
        self._enabled = enabled

        if self.context:
            self.context.logger.info(
                f"Dynamic prompt: {'enabled' if enabled else 'disabled'}"
            )


# Plugin export
__all__ = ["DynamicPromptPlugin"]

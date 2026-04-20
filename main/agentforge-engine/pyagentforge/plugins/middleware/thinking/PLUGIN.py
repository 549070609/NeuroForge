"""
Thinking Plugin

支持不同深度的推理模式，适配各模型的 extended thinking 能力
"""


from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class ThinkingPlugin(Plugin):
    """扩展思考插件"""

    metadata = PluginMetadata(
        id="middleware.thinking",
        name="Extended Thinking",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="支持不同深度的推理模式，适配各模型的 extended thinking 能力",
        author="PyAgentForge",
        dependencies=[],
        provides=["thinking"],
        priority=10,
    )

    def __init__(self):
        super().__init__()
        self._thinking_config = None
        self._thinking_level = None

    async def on_plugin_load(self, context) -> None:
        """加载插件"""
        await super().on_plugin_load(context)
        from pyagentforge.plugins.middleware.thinking.thinking import (
            ThinkingLevel,
        )

        config = context.config or {}
        level_str = config.get("level", "off")
        self._thinking_level = ThinkingLevel.parse(level_str)

    async def on_plugin_activate(self) -> None:
        """激活插件"""
        await super().on_plugin_activate()
        self.context.logger.info(f"Thinking plugin activated: level={self._thinking_level}")

    async def on_before_llm_call(self, messages: list) -> list | None:
        """LLM调用前注入思考配置"""
        # 思考配置在 create_message 时作为 kwargs 传递
        # 这里可以修改 messages 或返回额外的 kwargs
        return None

    def get_thinking_config(self, model_id: str = None):
        """获取思考配置"""
        from pyagentforge.plugins.middleware.thinking.thinking import create_thinking_config

        return create_thinking_config(
            level=self._thinking_level,
            model_id=model_id,
        )

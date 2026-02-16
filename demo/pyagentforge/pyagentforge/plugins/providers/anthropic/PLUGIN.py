"""
Anthropic Provider Plugin

支持 Claude 系列模型
"""

import logging
from typing import Any, List, Type

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.base_tool import BaseTool


class AnthropicPlugin(Plugin):
    """Anthropic Provider 插件"""

    metadata = PluginMetadata(
        id="providers.anthropic",
        name="Anthropic Provider",
        version="1.0.0",
        type=PluginType.PROVIDER,
        description="支持 Claude 系列模型",
        author="PyAgentForge",
        dependencies=[],
        provides=["provider.anthropic"],
    )

    def get_providers(self) -> List[Type[BaseProvider]]:
        """返回插件提供的 Provider 类"""
        from pyagentforge.plugins.providers.anthropic.anthropic_provider import AnthropicProvider
        return [AnthropicProvider]

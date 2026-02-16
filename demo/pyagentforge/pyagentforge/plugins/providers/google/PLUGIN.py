"""
Google Provider Plugin

支持 Gemini 系列模型
"""

import logging
from typing import Any, List, Type

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_provider import BaseProvider


class GooglePlugin(Plugin):
    """Google Provider 插件"""

    metadata = PluginMetadata(
        id="providers.google",
        name="Google Provider",
        version="1.0.0",
        type=PluginType.PROVIDER,
        description="支持 Gemini 系列模型",
        author="PyAgentForge",
        dependencies=[],
        provides=["provider.google"],
    )

    def get_providers(self) -> List[Type[BaseProvider]]:
        """返回插件提供的 Provider 类"""
        from pyagentforge.plugins.providers.google.google_provider import GoogleProvider
        return [GoogleProvider]

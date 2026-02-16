"""
LLM 提供商基类

定义所有 LLM 提供商的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any

from pyagentforge.core.message import ProviderResponse


class BaseProvider(ABC):
    """LLM 提供商基类"""

    def __init__(
        self,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_params = kwargs

    @abstractmethod
    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        创建消息

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 可用工具列表
            **kwargs: 额外参数

        Returns:
            提供商响应
        """
        pass

    @abstractmethod
    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        计算 Token 数量

        Args:
            messages: 消息列表

        Returns:
            Token 数量
        """
        pass

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """
        流式创建消息

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 可用工具列表
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        # 默认实现：调用非流式方法
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response

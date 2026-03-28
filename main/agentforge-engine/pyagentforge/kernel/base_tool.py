"""
工具基类

定义工具的标准接口
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """工具基类"""

    name: str = "base_tool"
    description: str = "基础工具"
    parameters_schema: dict[str, Any] = {}
    timeout: int = 60
    risk_level: str = "low"  # low, medium, high

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        pass

    def to_anthropic_schema(self) -> dict[str, Any]:
        """转换为 messages 风格工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 chat 风格工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def __repr__(self) -> str:
        return f"Tool(name={self.name!r}, description={self.description!r})"

"""
工具装饰器

简化工具定义
"""

import inspect
from typing import Any, Callable

from pydantic import BaseModel

from pyagentforge.tools.base import BaseTool


def tool(
    name: str,
    description: str,
    parameters_schema: dict[str, Any] | None = None,
    timeout: int = 60,
):
    """
    工具装饰器

    将函数包装为工具

    Args:
        name: 工具名称
        description: 工具描述
        parameters_schema: 参数 Schema
        timeout: 超时时间

    Example:
        @tool("greet", "问候用户", {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "用户名"}
            },
            "required": ["name"]
        })
        async def greet(name: str) -> str:
            return f"Hello, {name}!"
    """

    def decorator(func: Callable) -> "ToolWrapper":
        return ToolWrapper(
            func=func,
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            timeout=timeout,
        )

    return decorator


def generate_schema_from_func(func: Callable) -> dict[str, Any]:
    """从函数签名生成 JSON Schema"""
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = "string"
        param_desc = ""

        if param.annotation != inspect.Parameter.empty:
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            elif param.annotation == dict:
                param_type = "object"

        properties[param_name] = {
            "type": param_type,
            "description": param_desc,
        }

        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


class ToolWrapper(BaseTool):
    """工具包装器 - 将函数包装为工具"""

    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        parameters_schema: dict[str, Any] | None,
        timeout: int,
    ) -> None:
        self.func = func
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema or generate_schema_from_func(func)
        self.timeout = timeout

    async def execute(self, **kwargs: Any) -> str:
        """执行工具"""
        result = self.func(**kwargs)

        # 处理协程
        if inspect.iscoroutine(result):
            result = await result

        # 处理 Pydantic 模型
        if isinstance(result, BaseModel):
            result = result.model_dump_json()

        return str(result)

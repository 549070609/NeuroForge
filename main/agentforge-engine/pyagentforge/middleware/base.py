"""
Middleware Base - 中间件基类

定义中间件的抽象接口和上下文。
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MiddlewareContext:
    """
    中间件上下文

    每个中间件接收统一的上下文对象，包含请求处理所需的所有信息。

    Attributes:
        session_key: 当前会话标识
        messages: 消息历史
        tools: 可用工具列表
        config: 配置参数
        metadata: 元数据 (可扩展)

    Examples:
        >>> ctx = MiddlewareContext(
        ...     session_key="telegram:123",
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     tools=[],
        ...     config={}
        ... )
    """
    session_key: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **kwargs: Any) -> "MiddlewareContext":
        """
        创建带额外元数据的新上下文

        Args:
            **kwargs: 要添加的元数据

        Returns:
            新的 MiddlewareContext 实例
        """
        new_metadata = {**self.metadata, **kwargs}
        return MiddlewareContext(
            session_key=self.session_key,
            messages=self.messages,
            tools=self.tools,
            config=self.config,
            metadata=new_metadata,
        )


# 下一个中间件类型
NextMiddleware = Callable[[MiddlewareContext], Awaitable[Any]]


class BaseMiddleware(ABC):
    """
    中间件抽象基类

    所有中间件必须继承此类并实现 process 方法。

    Class Attributes:
        name: 中间件名称
        priority: 优先级 (越小越先执行)

    Examples:
        >>> class LoggingMiddleware(BaseMiddleware):
        ...     name = "logging"
        ...     priority = 10
        ...
        ...     async def process(self, ctx: MiddlewareContext, next_middleware: NextMiddleware) -> Any:
        ...         print(f"Request: {ctx.session_key}")
        ...         result = await next_middleware(ctx)
        ...         print(f"Response: {result}")
        ...         return result
    """

    name: str = "base"
    priority: int = 100

    @abstractmethod
    async def process(
        self,
        ctx: MiddlewareContext,
        next_middleware: NextMiddleware
    ) -> Any:
        """
        处理请求

        中间件可以在调用 next_middleware 前后添加自定义逻辑。
        必须调用 next_middleware(ctx) 将请求传递给下一个中间件。

        Args:
            ctx: 中间件上下文
            next_middleware: 下一个中间件 (或最终处理器)

        Returns:
            处理结果

        Examples:
            >>> async def process(self, ctx, next):
            ...     # 前置处理
            ...     ctx.metadata["start_time"] = time.time()
            ...
            ...     # 调用下一个中间件
            ...     result = await next(ctx)
            ...
            ...     # 后置处理
            ...     elapsed = time.time() - ctx.metadata["start_time"]
            ...     print(f"Request took {elapsed:.2f}s")
            ...
            ...     return result
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} priority={self.priority}>"

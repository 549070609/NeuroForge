"""
Middleware Pipeline - 中间件管道

管理中间件的注册和链式执行。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from pyagentforge.middleware.base import BaseMiddleware, MiddlewareContext, NextMiddleware

# 最终处理器类型
FinalHandler = Callable[[MiddlewareContext], Awaitable[Any]]


class MiddlewarePipeline:
    """
    中间件管道

    管理中间件的注册顺序，并支持链式执行。

    Attributes:
        _middlewares: 已注册的中间件列表

    Examples:
        >>> pipeline = MiddlewarePipeline()
        >>> pipeline.add(LoggingMiddleware())
        >>> pipeline.add(TimingMiddleware())
        >>> result = await pipeline.execute(ctx, final_handler)
    """

    def __init__(self):
        """初始化管道"""
        self._middlewares: list[BaseMiddleware] = []

    def add(self, middleware: BaseMiddleware) -> "MiddlewarePipeline":
        """
        添加中间件

        中间件会按 priority 排序，priority 越小越先执行。

        Args:
            middleware: 中间件实例

        Returns:
            self (支持链式调用)

        Examples:
            >>> pipeline = MiddlewarePipeline()
            >>> pipeline.add(AuthMiddleware()).add(LoggingMiddleware())
        """
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.priority)
        return self

    def remove(self, name: str) -> bool:
        """
        移除中间件

        Args:
            name: 中间件名称

        Returns:
            是否成功移除
        """
        for i, m in enumerate(self._middlewares):
            if m.name == name:
                self._middlewares.pop(i)
                return True
        return False

    def clear(self) -> None:
        """清除所有中间件"""
        self._middlewares.clear()

    def get_middlewares(self) -> list[BaseMiddleware]:
        """获取所有中间件 (只读)"""
        return list(self._middlewares)

    async def execute(
        self,
        ctx: MiddlewareContext,
        final_handler: FinalHandler
    ) -> Any:
        """
        执行中间件链

        按顺序执行所有中间件，最后调用 final_handler。

        Args:
            ctx: 中间件上下文
            final_handler: 最终处理器

        Returns:
            处理结果

        Examples:
            >>> async def handler(ctx):
            ...     return "result"
            >>> result = await pipeline.execute(ctx, handler)
        """
        if not self._middlewares:
            return await final_handler(ctx)

        # 构建中间件链
        async def build_chain(index: int) -> NextMiddleware:
            if index >= len(self._middlewares):
                return final_handler

            middleware = self._middlewares[index]

            async def chain(context: MiddlewareContext) -> Any:
                next_chain = await build_chain(index + 1)
                return await middleware.process(context, next_chain)

            return chain

        # 从第一个中间件开始执行
        first_chain = await build_chain(0)
        return await first_chain(ctx)

    def __len__(self) -> int:
        """获取中间件数量"""
        return len(self._middlewares)

    def __repr__(self) -> str:
        names = [m.name for m in self._middlewares]
        return f"<MiddlewarePipeline middlewares={names}>"

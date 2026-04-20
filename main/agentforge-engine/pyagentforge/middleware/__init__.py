"""
Middleware Layer - 中间件管道 (Layer 3)

提供请求/响应处理的可扩展机制，支持在 LLM 调用前后插入自定义逻辑。

核心组件:
- BaseMiddleware: 中间件抽象基类
- MiddlewareContext: 中间件上下文
- MiddlewarePipeline: 中间件管道
"""

from pyagentforge.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
)
from pyagentforge.middleware.pipeline import MiddlewarePipeline

__all__ = [
    "MiddlewareContext",
    "BaseMiddleware",
    "MiddlewarePipeline",
]

"""
Async runner utilities for CLI commands.

Provides decorators and helpers for running async code in CLI context.
"""

import asyncio
import functools
from typing import Any, Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def async_command(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to wrap async functions for Typer commands.

    Creates a new event loop and runs the async function.
    Use this when you need simple async support without service lifecycle.

    For commands that need service access, use CLI.core.context.async_command instead.

    Usage:
        @async_command
        async def my_command():
            await some_async_operation()
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def run_async(coro: Any) -> Any:
    """
    Run an async coroutine synchronously.

    Args:
        coro: Coroutine to run

    Returns:
        Result of the coroutine
    """
    return asyncio.run(coro)

"""
CLI Context - Service lifecycle management for CLI commands.

This module provides:
- CLIContext: Manages service initialization and shutdown
- async_command: Decorator to handle async commands with proper lifecycle
- get_context: Get the global CLI context singleton
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar, ParamSpec
import os

import sys
from pathlib import Path

# Add project roots for imports
_main_path = Path(__file__).resolve().parent.parent.parent
_engine_path = _main_path / "agentforge-engine"
for _path in (_engine_path, _main_path):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

# Prefer centralized config under main/
os.environ.setdefault("LLM_CONFIG_PATH", str(_main_path / "llm_config.json"))

# Configure logging
logging.basicConfig(level=logging.WARNING)

P = ParamSpec("P")
T = TypeVar("T")


class CLIContext:
    """
    Manages service lifecycle for CLI commands.

    This class wraps the ServiceRegistry and provides a convenient
    interface for CLI commands to access services.
    """

    def __init__(self):
        self.registry: Optional["ServiceRegistry"] = None
        self.settings: Optional[Any] = None
        self._initialized = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def initialize(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return

        # Load settings
        from Service.config.settings import get_settings
        self.settings = get_settings()

        # Create registry
        from Service.core.registry import ServiceRegistry
        self.registry = ServiceRegistry()

        # Import and register services
        from Service.services.agent_service import AgentService
        from Service.services.proxy.agent_proxy_service import AgentProxyService
        from Service.services.legacy_runtime_service import LegacyRuntimeService
        from Service.services.model_config_service import ModelConfigService

        self.registry.register("agent", AgentService(self.registry))
        self.registry.register("proxy", AgentProxyService(self.registry))
        self.registry.register("legacy_runtime", LegacyRuntimeService(self.registry))
        self.registry.register("model_config", ModelConfigService(self.registry))

        # Initialize all services
        await self.registry.initialize_all()
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown all services."""
        if self.registry and self._initialized:
            await self.registry.shutdown_all()
            self._initialized = False

    @property
    def agent(self) -> Any:
        """Get AgentService."""
        if not self.registry:
            raise RuntimeError("Context not initialized")
        return self.registry.get("agent")

    @property
    def proxy(self) -> Any:
        """Get AgentProxyService."""
        if not self.registry:
            raise RuntimeError("Context not initialized")
        return self.registry.get("proxy")

    @property
    def legacy_runtime(self) -> Any:
        """Get LegacyRuntimeService."""
        if not self.registry:
            raise RuntimeError("Context not initialized")
        return self.registry.get("legacy_runtime")

    @property
    def model_config(self) -> Any:
        """Get ModelConfigService."""
        if not self.registry:
            raise RuntimeError("Context not initialized")
        return self.registry.get("model_config")

    def is_initialized(self) -> bool:
        """Check if context is initialized."""
        return self._initialized


# Global context singleton
_global_context: Optional[CLIContext] = None


def get_context() -> CLIContext:
    """Get the global CLI context singleton."""
    global _global_context
    if _global_context is None:
        _global_context = CLIContext()
    return _global_context


def async_command(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to handle async CLI commands with proper service lifecycle.

    This decorator:
    1. Creates a new event loop for the command
    2. Initializes services before the command runs
    3. Cleans up services after the command completes

    Usage:
        @async_command
        async def my_command(arg: str):
            ctx = get_context()
            result = await ctx.agent.list_agents()
            return result
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        ctx = get_context()

        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Initialize services
            loop.run_until_complete(ctx.initialize())

            # Run the command
            result = loop.run_until_complete(func(*args, **kwargs))

            return result

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            return None
        except Exception as e:
            # Re-raise exceptions with context
            raise
        finally:
            # Cleanup
            try:
                loop.run_until_complete(ctx.shutdown())
            except Exception:
                pass  # Ignore shutdown errors
            loop.close()

    return wrapper


def run_async(coro: Any) -> Any:
    """
    Run an async coroutine in a managed context.

    Use this for REPL mode or when you need to run async code
    from a synchronous context with proper lifecycle management.

    Args:
        coro: An async coroutine to run

    Returns:
        The result of the coroutine
    """
    ctx = get_context()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(ctx.initialize())
        result = loop.run_until_complete(coro)
        return result
    finally:
        loop.run_until_complete(ctx.shutdown())
        loop.close()

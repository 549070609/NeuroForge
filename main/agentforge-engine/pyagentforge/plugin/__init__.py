"""
PyAgentForge Plugin System

插件系统 - 提供可扩展的插件架构
"""

from pyagentforge.plugin.base import (
    Plugin,
    PluginMetadata,
    PluginContext,
    PluginType,
)
from pyagentforge.plugin.hooks import HookType, HookRegistry
from pyagentforge.plugin.registry import PluginRegistry, PluginState
from pyagentforge.plugin.dependencies import (
    DependencyResolver,
    CircularDependencyError,
    DependencyMissingError,
)
from pyagentforge.plugin.loader import PluginLoader, PluginLoadError
from pyagentforge.plugin.manager import PluginManager

__all__ = [
    # Base classes
    "Plugin",
    "PluginMetadata",
    "PluginContext",
    "PluginType",
    # Hooks
    "HookType",
    "HookRegistry",
    # Registry
    "PluginRegistry",
    "PluginState",
    # Dependencies
    "DependencyResolver",
    "CircularDependencyError",
    "DependencyMissingError",
    # Loader
    "PluginLoader",
    "PluginLoadError",
    # Manager
    "PluginManager",
]

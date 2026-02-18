"""
Knowledge Injection Plugin

Auto-inject project knowledge into agent context.
"""

import os
from typing import TYPE_CHECKING, Any

from pyagentforge.core.knowledge_injector import InjectionResult, KnowledgeInjector
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.core.context import ContextManager

logger = get_logger(__name__)


class KnowledgeInjectionPlugin(Plugin):
    """
    Knowledge Injection Plugin

    Features:
    - Auto-inject README.md when entering new directory
    - Inject project rules based on file type
    - Support multiple rules sources (.cursorrules, .agent/rules)
    - Caching for performance
    - Token-aware injection
    """

    metadata = PluginMetadata(
        id="integration.knowledge_injection",
        name="Knowledge Injection",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Auto-inject project knowledge into agent context",
        author="PyAgentForge",
        provides=["knowledge_injection"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._injector: KnowledgeInjector | None = None
        self._enabled: bool = True
        self._include_readme: bool = True
        self._include_rules: bool = True
        self._max_tokens: int = 16000
        self._current_directory: str = ""

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)
        self._include_readme = config.get("include_readme", True)
        self._include_rules = config.get("include_rules", True)
        self._max_tokens = config.get("max_tokens", 16000)

        # Create injector
        self._injector = KnowledgeInjector(
            max_total_tokens=self._max_tokens,
            cache_enabled=True,
        )

        # Set current directory
        self._current_directory = os.getcwd()

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_BEFORE_TOOL_CALL,
            self,
            self._on_before_tool_call,
        )
        self.context.hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            self,
            self._on_before_llm_call,
        )

        self.context.logger.info(
            "Knowledge injection plugin activated",
            extra_data={
                "include_readme": self._include_readme,
                "include_rules": self._include_rules,
                "max_tokens": self._max_tokens,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    def _detect_tool_context(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """
        Detect directory and file context from tool call

        Args:
            tool_name: Tool name
            tool_args: Tool arguments

        Returns:
            (directory, file_path) tuple
        """
        directory = None
        file_path = None

        # Bash commands - detect cd
        if tool_name == "bash":
            cmd = tool_args.get("command", "")
            if "cd " in cmd:
                # Extract directory from cd command
                parts = cmd.split("cd ")
                if len(parts) > 1:
                    dir_part = parts[1].split("&&")[0].split(";")[0].strip()
                    if dir_part and not dir_part.startswith("-"):
                        directory = os.path.abspath(dir_part)

        # File operations - detect file path
        file_tools = ["read", "write", "edit", "glob", "grep"]
        if tool_name in file_tools:
            # Check various argument names
            for arg_name in ["file_path", "path", "pattern", "directory"]:
                if arg_name in tool_args:
                    path = tool_args[arg_name]
                    if path:
                        if tool_name in ("glob", "grep"):
                            directory = os.path.dirname(os.path.abspath(path))
                        else:
                            file_path = os.path.abspath(path)
                            directory = os.path.dirname(file_path)
                        break

        return directory, file_path

    async def _on_before_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before tool call - inject knowledge if needed

        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            context: Context manager

        Returns:
            Injection info
        """
        if not self._enabled or self._injector is None:
            return None

        # Detect context from tool call
        directory, file_path = self._detect_tool_context(tool_name, tool_args)

        # If no directory detected, use current
        if directory is None:
            directory = self._current_directory

        # Check if we need to inject
        result = self._injector.inject_knowledge(
            directory=directory,
            file_path=file_path,
            include_readme=self._include_readme,
            include_rules=self._include_rules,
        )

        if result.content:
            # Inject into context
            context.add_user_message(result.content)

            self.context.logger.info(
                "Injected knowledge before tool call",
                extra_data={
                    "tool_name": tool_name,
                    "sources": result.sources_injected,
                    "tokens": result.total_tokens,
                },
            )

            # Update current directory
            self._current_directory = directory

            return {
                "injected": True,
                "sources": result.sources_injected,
                "tokens": result.total_tokens,
            }

        return None

    async def _on_before_llm_call(
        self,
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before LLM call - inject initial knowledge if needed

        Args:
            context: Context manager

        Returns:
            Injection info
        """
        if not self._enabled or self._injector is None:
            return None

        # Check if we have already injected for current directory
        readme_key = f"readme:{self._current_directory}"
        if self._injector.is_injected(readme_key):
            return None

        # Inject README for current directory
        if self._include_readme:
            result = self._injector.inject_readme(self._current_directory)

            if result.content:
                context.add_user_message(result.content)

                self.context.logger.info(
                    "Injected README before LLM call",
                    extra_data={
                        "directory": self._current_directory,
                        "tokens": result.total_tokens,
                    },
                )

                return {
                    "injected": True,
                    "sources": result.sources_injected,
                    "tokens": result.total_tokens,
                }

        return None

    def get_injector(self) -> KnowledgeInjector | None:
        """Get the knowledge injector"""
        return self._injector

    def force_inject(
        self,
        context: "ContextManager",
        directory: str | None = None,
        file_path: str | None = None,
    ) -> InjectionResult:
        """
        Force inject knowledge

        Args:
            context: Context manager
            directory: Optional directory (uses current if not specified)
            file_path: Optional file path

        Returns:
            Injection result
        """
        if self._injector is None:
            return InjectionResult(success=False, errors=["Injector not initialized"])

        directory = directory or self._current_directory

        result = self._injector.inject_knowledge(
            directory=directory,
            file_path=file_path,
            include_readme=self._include_readme,
            include_rules=self._include_rules,
        )

        if result.content:
            context.add_user_message(result.content)

        return result

    def reset_cache(self) -> None:
        """Reset injection cache"""
        if self._injector:
            self._injector.reset_cache()
            self.context.logger.info("Knowledge injection cache reset")

    def set_current_directory(self, directory: str) -> None:
        """Set current directory"""
        self._current_directory = os.path.abspath(directory)

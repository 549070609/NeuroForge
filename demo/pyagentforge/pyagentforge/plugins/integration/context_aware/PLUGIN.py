"""
Context Aware Plugin

Provides context-aware prompt enhancement functionality
"""

import logging
from typing import Any, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class ContextAwarePlugin(Plugin):
    """Context-aware prompts plugin"""

    metadata = PluginMetadata(
        id="integration.context_aware",
        name="Context Aware",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Provides context-aware prompt enhancement based on conversation history and environment",
        author="PyAgentForge",
        provides=["context_aware"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._context_hints: dict[str, str] = {}
        self._enabled: bool = True

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Get config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)

        # Initialize default context hints
        self._context_hints = {
            "project_type": "unknown",
            "language": "en",
            "verbosity": "normal",
        }

        self.context.logger.info("Context aware plugin initialized")

    async def on_before_llm_call(self, messages: list) -> Optional[list]:
        """
        Enhance messages with context-aware information

        Args:
            messages: Original message list

        Returns:
            Enhanced messages or None to keep original
        """
        if not self._enabled:
            return None

        # Add context hints to system message if present
        enhanced_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                # Enhance system message with context
                enhanced_content = self._enhance_system_prompt(msg.get("content", ""))
                enhanced_msg = {**msg, "content": enhanced_content}
                enhanced_messages.append(enhanced_msg)
            else:
                enhanced_messages.append(msg)

        return enhanced_messages

    def _enhance_system_prompt(self, original_prompt: str) -> str:
        """
        Enhance system prompt with context information

        Args:
            original_prompt: Original system prompt

        Returns:
            Enhanced prompt
        """
        context_parts = []

        # Add project context
        if self._context_hints.get("project_type") != "unknown":
            context_parts.append(
                f"Project type: {self._context_hints['project_type']}"
            )

        # Add language preference
        if self._context_hints.get("language"):
            context_parts.append(
                f"Response language: {self._context_hints['language']}"
            )

        # Add verbosity preference
        verbosity = self._context_hints.get("verbosity", "normal")
        if verbosity != "normal":
            context_parts.append(f"Response style: {verbosity}")

        if not context_parts:
            return original_prompt

        # Prepend context to prompt
        context_block = "\n".join(context_parts)
        return f"{original_prompt}\n\n[Context]\n{context_block}"

    def set_context_hint(self, key: str, value: str) -> None:
        """
        Set a context hint

        Args:
            key: Hint key
            value: Hint value
        """
        self._context_hints[key] = value

    def get_context_hint(self, key: str) -> Optional[str]:
        """
        Get a context hint

        Args:
            key: Hint key

        Returns:
            Hint value or None
        """
        return self._context_hints.get(key)

    def clear_context_hints(self) -> None:
        """Clear all context hints"""
        self._context_hints.clear()

    def analyze_conversation(self, messages: list) -> dict[str, Any]:
        """
        Analyze conversation to extract context

        Args:
            messages: Conversation messages

        Returns:
            Analysis results
        """
        analysis = {
            "total_messages": len(messages),
            "tool_calls": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "topics": set(),
        }

        for msg in messages:
            role = msg.get("role", "")

            if role == "user":
                analysis["user_messages"] += 1
            elif role == "assistant":
                analysis["assistant_messages"] += 1

            # Count tool uses
            content = str(msg.get("content", ""))
            if "tool_use" in content:
                analysis["tool_calls"] += 1

        # Convert set to list for JSON serialization
        analysis["topics"] = list(analysis["topics"])

        return analysis

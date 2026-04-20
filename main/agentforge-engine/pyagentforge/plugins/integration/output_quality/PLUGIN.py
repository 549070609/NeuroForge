"""
Output Quality Plugin

Detects excessive comments and intelligently truncates tool output.
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookDecision
from pyagentforge.plugins.integration.output_quality.comment_checker import (
    CommentChecker,
    CommentCheckResult,
    CommentThresholds,
)
from pyagentforge.plugins.integration.output_quality.output_truncator import (
    OutputTruncator,
    TruncationConfig,
    TruncationResult,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


# Tool categories to check for comments
CODE_OUTPUT_TOOLS = {
    "write_file",
    "edit_file",
    "create_file",
    "python_exec",
    "bash",
}

# Tool categories to truncate
TRUNCATABLE_TOOLS = {
    "read_file",
    "glob",
    "grep",
    "search",
    "list_directory",
    "bash",
}


class OutputQualityPlugin(Plugin):
    """
    Output Quality Plugin

    Provides two main features:
    1. Comment detection - Warns about excessive comments in code output
    2. Output truncation - Intelligently truncates long tool outputs

    Hooks:
    - post_tool_use: Checks output quality and truncates if needed
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="integration.output_quality",
            name="Output Quality Control",
            version="1.0.0",
            type=PluginType.INTEGRATION,
            description="Detects excessive comments and truncates long outputs",
            author="PyAgentForge Team",
            dependencies=[],
            provides=["output_quality"],
            priority=100,  # High priority - runs after other hooks
        )

    def __init__(self):
        super().__init__()
        self._comment_checker: CommentChecker | None = None
        self._output_truncator: OutputTruncator | None = None
        self._check_comments_enabled: bool = True
        self._truncation_enabled: bool = True
        self._warn_only: bool = True  # Warn but don't block

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时初始化"""
        await super().on_plugin_load(context)

        # Get configuration
        config = context.config.get("integration.output_quality", {})
        self._check_comments_enabled = config.get("check_comments", True)
        self._truncation_enabled = config.get("truncation", True)
        self._warn_only = config.get("warn_only", True)

        # Initialize comment checker
        if self._check_comments_enabled:
            thresholds = CommentThresholds(
                max_comment_ratio=config.get("max_comment_ratio", 0.4),
                max_consecutive_comments=config.get("max_consecutive_comments", 5),
            )
            self._comment_checker = CommentChecker(
                thresholds=thresholds,
                min_lines=config.get("min_lines_to_check", 10),
            )

        # Initialize output truncator
        if self._truncation_enabled:
            trunc_config = TruncationConfig(
                max_total_lines=config.get("max_output_lines", 500),
                max_non_code_lines=config.get("max_non_code_lines", 200),
                preserve_code_blocks=config.get("preserve_code_blocks", True),
            )
            self._output_truncator = OutputTruncator(trunc_config)

        context.logger.info(
            f"Output Quality plugin loaded "
            f"(comments: {self._check_comments_enabled}, truncation: {self._truncation_enabled})"
        )

    async def on_plugin_activate(self) -> None:
        """插件激活时"""
        await super().on_plugin_activate()
        if self.context:
            self.context.logger.info("Output Quality plugin activated")

    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        return []

    async def _on_post_tool_use(
        self,
        tool_name: str,
        result: str,
        context: dict[str, Any],
    ) -> tuple[HookDecision, str]:
        """
        工具执行后的钩子

        Args:
            tool_name: 工具名称
            result: 工具返回结果
            context: 执行上下文

        Returns:
            (HookDecision, modified_result)
        """
        modified_result = result

        # Check for excessive comments in code output
        if self._check_comments_enabled and tool_name in CODE_OUTPUT_TOOLS:
            modified_result = self._check_comments(tool_name, modified_result)

        # Truncate long output
        if self._truncation_enabled and tool_name in TRUNCATABLE_TOOLS:
            modified_result = self._truncate_output(tool_name, modified_result)

        return HookDecision.ALLOW, modified_result

    def _check_comments(self, tool_name: str, result: str) -> str:
        """
        Check for excessive comments in code output

        Args:
            tool_name: Tool name
            result: Tool result

        Returns:
            Potentially modified result
        """
        if not self._comment_checker:
            return result

        try:
            # Detect language from result or tool
            language = self._detect_language(tool_name, result)

            # Check comments
            check_result = self._comment_checker.check(result, language)

            if check_result.is_excessive:
                # Generate warning
                warning = self._comment_checker.suggest_improvements(check_result)

                if self._warn_only:
                    # Log warning
                    logger.warning(
                        f"Excessive comments detected in {tool_name} output: "
                        f"{check_result.comment_ratio:.1%} comments"
                    )
                    # Prepend warning to result
                    return f"⚠️ Comment Warning:\n{warning}\n\n---\n\n{result}"
                else:
                    # Block (not recommended)
                    logger.warning(
                        f"Blocked excessive comments in {tool_name} output"
                    )
                    return f"Output blocked due to excessive comments.\n\n{warning}"

        except Exception as e:
            logger.error(f"Comment check failed: {e}")

        return result

    def _truncate_output(self, tool_name: str, result: str) -> str:
        """
        Truncate long tool output

        Args:
            tool_name: Tool name
            result: Tool result

        Returns:
            Potentially truncated result
        """
        if not self._output_truncator:
            return result

        try:
            trunc_result = self._output_truncator.truncate(result)

            if trunc_result.was_truncated:
                logger.info(
                    f"Truncated {tool_name} output: "
                    f"removed {trunc_result.removed_lines} lines "
                    f"(preserved {trunc_result.preserved_code_blocks} code blocks)"
                )
                return trunc_result.content

        except Exception as e:
            logger.error(f"Output truncation failed: {e}")

        return result

    def _detect_language(self, tool_name: str, result: str) -> str:
        """
        Detect programming language

        Args:
            tool_name: Tool name
            result: Tool result

        Returns:
            Detected language
        """
        # Check for language hints in tool name
        if "python" in tool_name.lower():
            return "python"
        if "javascript" in tool_name.lower() or "js" in tool_name.lower():
            return "javascript"
        if "typescript" in tool_name.lower() or "ts" in tool_name.lower():
            return "typescript"

        # Check for language patterns in result
        if "def " in result or "import " in result:
            return "python"
        if "function " in result or "const " in result:
            return "javascript"
        if "interface " in result or ": string" in result:
            return "typescript"

        # Default to Python
        return "python"

    def set_check_comments(self, enabled: bool) -> None:
        """Enable or disable comment checking"""
        self._check_comments_enabled = enabled
        if self.context:
            self.context.logger.info(
                f"Comment checking: {'enabled' if enabled else 'disabled'}"
            )

    def set_truncation(self, enabled: bool) -> None:
        """Enable or disable output truncation"""
        self._truncation_enabled = enabled
        if self.context:
            self.context.logger.info(
                f"Output truncation: {'enabled' if enabled else 'disabled'}"
            )

    def get_stats(self) -> dict[str, Any]:
        """Get plugin statistics"""
        return {
            "check_comments_enabled": self._check_comments_enabled,
            "truncation_enabled": self._truncation_enabled,
            "warn_only": self._warn_only,
        }


# Plugin export
__all__ = [
    "OutputQualityPlugin",
    "CommentChecker",
    "CommentCheckResult",
    "CommentThresholds",
    "OutputTruncator",
    "TruncationConfig",
    "TruncationResult",
]

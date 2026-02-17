"""
Agent 执行引擎

实现 Agent 的核心执行循环
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.executor import ToolExecutor, ToolRegistry
from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.kernel.base_provider import BaseProvider

logger = logging.getLogger(__name__)

# 用户确认回调类型
AskCallback = Callable[[str, dict[str, Any]], bool]


@dataclass
class AgentConfig:
    """Agent 配置"""
    system_prompt: str = "You are a helpful AI assistant."
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 100
    permission_checker: Any = None


class AgentEngine:
    """Agent 执行引擎 - 核心执行循环"""

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        config: AgentConfig | None = None,
        context: ContextManager | None = None,
        ask_callback: AskCallback | None = None,
        plugin_manager: Any = None,  # PluginManager 将在 Phase 2 实现
    ) -> None:
        """
        初始化 Agent 引擎

        Args:
            provider: LLM 提供商
            tool_registry: 工具注册表
            config: Agent 配置
            context: 上下文管理器
            ask_callback: 用户确认回调
            plugin_manager: 插件管理器 (可选)
        """
        self.provider = provider
        self.tools = tool_registry
        self.config = config or AgentConfig()
        self.context = context or ContextManager(
            system_prompt=self.config.system_prompt,
        )
        self.executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=self.config.permission_checker,
        )
        self.ask_callback = ask_callback
        self.plugin_manager = plugin_manager
        self._subagent_depth = 0
        self._session_id = str(uuid.uuid4())

        logger.info(
            f"Initialized AgentEngine: session_id={self._session_id}, model={provider.model}"
        )

    @property
    def session_id(self) -> str:
        """获取会话 ID"""
        return self._session_id

    async def run(self, prompt: str) -> str:
        """
        运行 Agent

        Args:
            prompt: 用户输入

        Returns:
            Agent 响应
        """
        logger.info(
            f"Starting Agent run: session_id={self._session_id}, prompt_len={len(prompt)}"
        )

        # 插件钩子: on_engine_start
        if self.plugin_manager:
            await self.plugin_manager.emit_hook("on_engine_start", self)

        # 添加用户消息
        self.context.add_user_message(prompt)

        # 执行循环
        iteration = 0
        max_iterations = self.config.max_iterations

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                f"[Agent Loop] Iteration {iteration}/{max_iterations}"
            )

            # 插件钩子: on_before_llm_call
            messages = self.context.get_messages_for_api()
            if self.plugin_manager:
                modified = await self.plugin_manager.emit_hook(
                    "on_before_llm_call", messages
                )
                if modified and modified[0]:
                    messages = modified[0]

            # 调用 LLM
            response = await self._call_llm(messages)

            # 插件钩子: on_after_llm_call
            if self.plugin_manager:
                modified = await self.plugin_manager.emit_hook(
                    "on_after_llm_call", response
                )
                if modified and modified[0]:
                    response = modified[0]

            logger.info(
                f"[Agent Loop] Response: stop_reason={response.stop_reason}, "
                f"has_tools={response.has_tool_calls}, text_len={len(response.text)}"
            )

            # 如果没有工具调用，返回文本响应
            if not response.has_tool_calls:
                self.context.add_assistant_text(response.text)

                # 插件钩子: on_task_complete
                if self.plugin_manager:
                    await self.plugin_manager.emit_hook("on_task_complete", response.text)

                logger.info(
                    f"Agent run completed: session_id={self._session_id}, iterations={iteration}"
                )
                return response.text

            # 添加助手消息（包含工具调用）
            self.context.add_assistant_message(response.content)

            # 记录工具调用
            tool_names = [tc.name for tc in response.tool_calls]
            logger.info(f"[Agent Loop] Tool calls: {tool_names}")

            # 执行工具
            tool_results = await self.executor.execute_batch(
                response.tool_calls,
                self.ask_callback,
            )

            # 添加工具结果
            for tool_use_id, result in tool_results:
                self.context.add_tool_result(tool_use_id, result)

            # 检查是否需要截断上下文
            if len(self.context) > self.context.max_messages * 0.8:
                self.context.truncate()

        logger.error(
            f"[Agent Loop] Maximum iterations reached! session_id={self._session_id}"
        )
        return "Error: Maximum iterations reached"

    async def run_stream(self, prompt: str):
        """
        流式运行 Agent

        Args:
            prompt: 用户输入

        Yields:
            流式响应事件
        """
        logger.info(
            f"Starting Agent stream: session_id={self._session_id}, prompt_len={len(prompt)}"
        )

        # 插件钩子: on_engine_start
        if self.plugin_manager:
            await self.plugin_manager.emit_hook("on_engine_start", self)

        # 添加用户消息
        self.context.add_user_message(prompt)

        # 执行循环
        iteration = 0
        max_iterations = self.config.max_iterations

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                f"[Agent Stream] Iteration {iteration}/{max_iterations}"
            )

            # 插件钩子: on_before_llm_call
            messages = self.context.get_messages_for_api()
            if self.plugin_manager:
                modified = await self.plugin_manager.emit_hook(
                    "on_before_llm_call", messages
                )
                if modified and modified[0]:
                    messages = modified[0]

            # 流式调用 LLM
            final_response = None
            async for event in self.provider.stream_message(
                self.config.system_prompt,
                messages,
                self.tools.get_schemas(),
            ):
                if isinstance(event, ProviderResponse):
                    final_response = event
                else:
                    yield {"type": "stream", "event": event}

            if final_response is None:
                logger.warning(
                    f"[Agent Stream] No final response from provider, session_id={self._session_id}"
                )
                break

            # 插件钩子: on_after_llm_call
            if self.plugin_manager:
                modified = await self.plugin_manager.emit_hook(
                    "on_after_llm_call", final_response
                )
                if modified and modified[0]:
                    final_response = modified[0]

            logger.info(
                f"[Agent Stream] Response: stop_reason={final_response.stop_reason}, "
                f"has_tools={final_response.has_tool_calls}"
            )

            if not final_response.has_tool_calls:
                self.context.add_assistant_text(final_response.text)

                # 插件钩子: on_task_complete
                if self.plugin_manager:
                    await self.plugin_manager.emit_hook("on_task_complete", final_response.text)

                yield {"type": "complete", "text": final_response.text}
                return

            # 添加助手消息（包含工具调用）
            self.context.add_assistant_message(final_response.content)

            # 记录工具调用
            tool_names = [tc.name for tc in final_response.tool_calls]
            logger.info(f"[Agent Stream] Tool calls: {tool_names}")

            # 执行工具并 yield 结果
            for tool_call in final_response.tool_calls:
                yield {
                    "type": "tool_start",
                    "tool_name": tool_call.name,
                    "tool_id": tool_call.id,
                }

                result = await self.executor.execute(tool_call, self.ask_callback)
                self.context.add_tool_result(tool_call.id, result)

                yield {
                    "type": "tool_result",
                    "tool_id": tool_call.id,
                    "result": result,
                }

            # 检查是否需要截断上下文
            if len(self.context) > self.context.max_messages * 0.8:
                self.context.truncate()

        logger.error(
            f"[Agent Stream] Maximum iterations reached! session_id={self._session_id}"
        )
        yield {"type": "error", "message": "Maximum iterations reached"}

    async def _call_llm(self, messages: list[dict]) -> ProviderResponse:
        """调用 LLM"""
        return await self.provider.create_message(
            system=self.config.system_prompt,
            messages=messages,
            tools=self.tools.get_schemas(),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

    def reset(self) -> None:
        """重置 Agent 状态"""
        self.context.clear()
        logger.info(f"Agent reset: session_id={self._session_id}")

    def get_context_summary(self) -> dict[str, Any]:
        """获取上下文摘要"""
        return {
            "session_id": self._session_id,
            "message_count": len(self.context),
            "loaded_skills": list(self.context.get_loaded_skills()),
            "config": {
                "model": self.provider.model,
                "max_tokens": self.config.max_tokens,
            },
        }

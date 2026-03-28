"""
Agent 执行引擎

实现 Agent 的核心执行循环
"""

import uuid
from typing import Any, Callable

from pyagentforge.agents.config import AgentConfig
from pyagentforge.client import LLMClient
from pyagentforge.config.settings import get_settings
from pyagentforge.core.compaction import Compactor, CompactionSettings
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.executor import ToolExecutor
from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.plugins.middleware.thinking.thinking import (
    ThinkingLevel,
    create_thinking_config,
)
from pyagentforge.kernel.model_registry import ModelConfig
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

# 用户确认回调类型
AskCallback = Callable[[str, dict[str, Any]], bool]


class AgentEngine:
    """Agent 执行引擎"""

    def __init__(
        self,
        model_id: str,
        tool_registry: ToolRegistry,
        config: AgentConfig | None = None,
        context: ContextManager | None = None,
        ask_callback: AskCallback | None = None,
        thinking_level: ThinkingLevel | str | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        """
        初始化 Agent 引擎

        Args:
            model_id: 模型 ID（如 "default"）
            tool_registry: 工具注册表
            config: Agent 配置
            context: 上下文管理器
            ask_callback: 用户确认回调
            thinking_level: 思考级别
            llm_client: LLM 客户端（可选，用于测试）
        """
        settings = get_settings()
        self.model_id = model_id
        self.llm_client = llm_client or LLMClient()
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
        self._subagent_depth = 0
        self._session_id = str(uuid.uuid4())

        # 思考级别设置
        if thinking_level is None:
            thinking_level = settings.default_thinking_level
        if isinstance(thinking_level, str):
            thinking_level = ThinkingLevel.parse(thinking_level)
        self.thinking_level = thinking_level
        self.thinking_config = create_thinking_config(
            level=thinking_level,
            model_id=model_id,
            budget_tokens=settings.thinking_budget_tokens,
        )

        # 上下文压缩设置
        self.compactor = Compactor(
            llm_client=self.llm_client,
            model_id=model_id,
            settings=CompactionSettings(
                enabled=settings.compaction_enabled,
                reserve_tokens=settings.compaction_reserve_tokens,
                keep_recent_tokens=settings.compaction_keep_recent_tokens,
                trigger_threshold=settings.compaction_threshold,
            ),
            max_context_tokens=settings.max_context_tokens,
        )

        logger.info(
            "Initialized AgentEngine",
            extra_data={
                "session_id": self._session_id,
                "model": model_id,
                "thinking_level": thinking_level.value,
                "compaction_enabled": settings.compaction_enabled,
            },
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
            "Starting Agent run",
            extra_data={
                "session_id": self._session_id,
                "prompt_length": len(prompt),
            },
        )

        # 添加用户消息
        self.context.add_user_message(prompt)

        # 执行循环
        iteration = 0
        max_iterations = 100  # 防止无限循环（增加到100）

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                f"[Agent Loop] Iteration {iteration}/{max_iterations}",
                extra_data={"session_id": self._session_id},
            )

            # 检查是否需要压缩上下文
            await self._maybe_compact()

            # 调用 LLM
            response = await self._call_llm()

            logger.info(
                f"[Agent Loop] Response: stop_reason={response.stop_reason}, has_tools={response.has_tool_calls}, text_len={len(response.text)}",
                extra_data={"session_id": self._session_id},
            )

            # 如果没有工具调用，返回文本响应
            if not response.has_tool_calls:
                self.context.add_assistant_text(response.text)
                logger.info(
                    "Agent run completed",
                    extra_data={
                        "session_id": self._session_id,
                        "iterations": iteration,
                    },
                )
                return response.text

            # 添加助手消息（包含工具调用）
            self.context.add_assistant_message(response.content)

            # 记录工具调用
            tool_names = [tc.name for tc in response.tool_calls]
            logger.info(
                f"[Agent Loop] Tool calls: {tool_names}",
                extra_data={"session_id": self._session_id},
            )

            # 执行工具
            tool_results = await self.executor.execute_batch(
                response.tool_calls,
                self.ask_callback,
            )

            # 添加工具结果
            for tool_use_id, result in tool_results:
                self.context.add_tool_result(tool_use_id, result)

            # 检查是否需要截断上下文（备用机制）
            if len(self.context) > self.context.max_messages * 0.8:
                self.context.truncate()

        logger.error(
            f"[Agent Loop] Maximum iterations reached!",
            extra_data={"session_id": self._session_id, "iterations": iteration},
        )
        return "Error: Maximum iterations reached"

    async def _maybe_compact(self) -> None:
        """检查并执行上下文压缩"""
        if self.compactor.should_compact(self.context.messages):
            logger.info(
                "Context compaction triggered",
                extra_data={
                    "session_id": self._session_id,
                    "message_count": len(self.context.messages),
                },
            )
            result = await self.compactor.compact(self.context.messages)
            if result.removed_messages > 0:
                # 更新上下文消息
                self.context.messages = self.compactor.build_compacted_messages(
                    self.context.messages, result
                )
                logger.info(
                    "Context compacted",
                    extra_data={
                        "tokens_saved": result.tokens_saved,
                        "removed_messages": result.removed_messages,
                    },
                )

    async def run_stream(self, prompt: str):
        """
        流式运行 Agent

        Args:
            prompt: 用户输入

        Yields:
            流式响应事件
        """
        self.context.add_user_message(prompt)

        iteration = 0
        max_iterations = 100  # 增加到100

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                f"[Agent Stream] Iteration {iteration}/{max_iterations}",
                extra_data={"session_id": self._session_id},
            )

            # 流式调用 LLM
            final_response = None
            async for event in self.llm_client.stream_message(
                model_id=self.model_id,
                messages=self.context.get_messages_for_api(),
                system=self.config.system_prompt,
                tools=self.tools.get_schemas(),
            ):
                if isinstance(event, ProviderResponse):
                    final_response = event
                else:
                    yield {"type": "stream", "event": event}

            if final_response is None:
                logger.warning(
                    "[Agent Stream] No final response from provider",
                    extra_data={"session_id": self._session_id},
                )
                break

            logger.info(
                f"[Agent Stream] Response: stop_reason={final_response.stop_reason}, has_tools={final_response.has_tool_calls}",
                extra_data={"session_id": self._session_id},
            )

            if not final_response.has_tool_calls:
                self.context.add_assistant_text(final_response.text)
                yield {"type": "complete", "text": final_response.text}
                return

            self.context.add_assistant_message(final_response.content)

            # 记录工具调用
            tool_names = [tc.name for tc in final_response.tool_calls]
            logger.info(
                f"[Agent Stream] Tool calls: {tool_names}",
                extra_data={"session_id": self._session_id},
            )

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

        logger.error(
            f"[Agent Stream] Maximum iterations reached!",
            extra_data={"session_id": self._session_id, "iterations": iteration},
        )
        yield {"type": "error", "message": "Maximum iterations reached"}

    async def _call_llm(self) -> ProviderResponse:
        """调用 LLM"""
        return await self.llm_client.create_message(
            model_id=self.model_id,
            messages=self.context.get_messages_for_api(),
            system=self.config.system_prompt,
            tools=self.tools.get_schemas(),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

    def reset(self) -> None:
        """重置 Agent 状态"""
        self.context.clear()
        logger.info(
            "Agent reset",
            extra_data={"session_id": self._session_id},
        )

    def get_context_summary(self) -> dict[str, Any]:
        """获取上下文摘要"""
        return {
            "session_id": self._session_id,
            "message_count": len(self.context),
            "loaded_skills": list(self.context.get_loaded_skills()),
            "config": {
                "model": self.model_id,
                "max_tokens": self.config.max_tokens,
                "thinking_level": self.thinking_level.value,
            },
            "compaction": {
                "enabled": self.compactor.settings.enabled,
                "threshold": self.compactor.settings.trigger_threshold,
            },
        }

    def set_thinking_level(self, level: ThinkingLevel | str) -> None:
        """
        设置思考级别

        Args:
            level: 思考级别
        """
        if isinstance(level, str):
            level = ThinkingLevel.parse(level)
        self.thinking_level = level
        self.thinking_config = create_thinking_config(
            level=level,
            model_id=self.model_id,
        )
        logger.info(
            "Thinking level changed",
            extra_data={"level": level.value},
        )

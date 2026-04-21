"""
Agent 执行引擎

实现 Agent 的核心执行循环，支持 checkpoint/resume。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from pyagentforge.kernel.checkpoint import BaseCheckpointer, Checkpoint
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.errors import (
    AgentCancelledError,
    AgentMaxIterationsError,
    AgentTimeoutError,
)
from pyagentforge.kernel.executor import ToolExecutor, ToolRegistry
from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.kernel.base_provider import BaseProvider

logger = logging.getLogger(__name__)

AskCallback = Callable[[str, dict[str, Any]], bool]


@dataclass
class AgentConfig:
    """Agent runtime configuration."""
    name: str = "default"
    description: str = ""
    version: str = "1.0.0"
    model: str = "default"
    system_prompt: str = "You are a helpful AI assistant."
    max_tokens: int = 4096
    temperature: float = 1.0
    timeout: int = 120
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None
    ask_tools: list[str] | None = None
    max_iterations: int = 100
    max_subagent_depth: int = 3
    permission_checker: Any = None
    readonly: bool = False
    supports_background: bool = True
    max_concurrent: int = 3


class AgentEngine:
    """Agent 执行引擎 - 核心执行循环，支持 checkpoint/resume"""

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        config: AgentConfig | None = None,
        context: ContextManager | None = None,
        ask_callback: AskCallback | None = None,
        plugin_manager: Any = None,
        category_registry: Any = None,
        checkpointer: BaseCheckpointer | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tool_registry
        self.config = config or AgentConfig()
        self.context = (
            context
            if context is not None
            else ContextManager(system_prompt=self.config.system_prompt)
        )
        self.executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=self.config.permission_checker,
        )
        self.ask_callback = ask_callback
        self.plugin_manager = plugin_manager
        self.category_registry = category_registry
        self.checkpointer = checkpointer
        self._subagent_depth = 0
        self._session_id = str(uuid.uuid4())

        logger.info(
            f"Initialized AgentEngine: session_id={self._session_id}, model={provider.model}"
        )

    @property
    def session_id(self) -> str:
        """获取会话 ID"""
        return self._session_id

    async def run(
        self,
        prompt: str,
        *,
        resume: bool = False,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """
        运行 Agent

        Args:
            prompt: 用户输入
            resume: 是否从 checkpoint 恢复执行
            cancel_event: 外部取消信号，set() 后引擎在下一迭代入口退出

        Returns:
            Agent 响应

        Raises:
            AgentTimeoutError: LLM 调用或工具执行超时
            AgentCancelledError: cancel_event 被 set
        """
        logger.info(
            f"Starting Agent run: session_id={self._session_id}, prompt_len={len(prompt)}"
        )

        # 插件钩子: on_engine_start
        if self.plugin_manager:
            await self.plugin_manager.emit_hook("on_engine_start", self)

        # 从 checkpoint 恢复
        start_iteration = 0
        if resume and self.checkpointer:
            restored = await self._restore_from_checkpoint()
            if restored is not None:
                start_iteration = restored
                logger.info(
                    f"Resumed from checkpoint at iteration {start_iteration}",
                )
            else:
                self.context.add_user_message(prompt)
        else:
            self.context.add_user_message(prompt)

        # 执行循环
        iteration = start_iteration
        max_iterations = self.config.max_iterations

        while iteration < max_iterations:
            await self._check_cancel(cancel_event, iteration, "Agent Loop")

            iteration += 1
            logger.info(
                f"[Agent Loop] Iteration {iteration}/{max_iterations}"
            )

            messages = await self._prepare_messages()
            response = await self._call_llm(messages)
            response = await self._apply_after_llm_hook(response)

            logger.info(
                f"[Agent Loop] Response: stop_reason={response.stop_reason}, "
                f"has_tools={response.has_tool_calls}, text_len={len(response.text)}"
            )

            if not response.has_tool_calls:
                await self._handle_completion(response.text, iteration)
                return response.text

            # 添加助手消息（包含工具调用）
            self.context.add_assistant_message(response.content)

            tool_names = [tc.name for tc in response.tool_calls]
            logger.info(f"[Agent Loop] Tool calls: {tool_names}")

            # 执行工具（带超时保护）
            try:
                tool_results = await asyncio.wait_for(
                    self.executor.execute_batch(
                        response.tool_calls,
                        self.ask_callback,
                    ),
                    timeout=self.config.timeout,
                )
            except TimeoutError:
                logger.error(
                    f"[Agent Loop] Tool batch execution timed out after "
                    f"{self.config.timeout}s, session_id={self._session_id}"
                )
                await self._delete_checkpoint()
                raise AgentTimeoutError(
                    session_id=self._session_id,
                    iteration=iteration,
                    timeout=self.config.timeout,
                    detail="tool_batch_execution",
                )

            for tool_use_id, result in tool_results:
                self.context.add_tool_result(tool_use_id, result)

            await self._post_tool_iteration(iteration)

        logger.error(
            f"[Agent Loop] Maximum iterations reached! session_id={self._session_id}"
        )
        await self._delete_checkpoint()
        raise AgentMaxIterationsError(
            session_id=self._session_id,
            iteration=iteration,
            max_iterations=max_iterations,
        )

    PHASE_LABELS = {
        1: "快速响应",
        2: "深度分析",
        3: "总结建议",
    }

    async def run_stream(
        self,
        prompt: str,
        *,
        cancel_event: asyncio.Event | None = None,
    ):
        """
        流式运行 Agent（分阶段输出）

        每个迭代对应一个 phase：
          Phase 1 - 快速响应：直接回应用户命令（文本 + 工具调用）
          Phase 2 - 深度分析：基于工具结果输出结构化分析
          Phase 3+ - 总结建议：最终输出

        Args:
            prompt: 用户输入
            cancel_event: 外部取消信号，set() 后引擎在下一迭代入口退出

        Yields:
            带 phase 标记的流式响应事件

        Raises:
            AgentTimeoutError: LLM 调用或工具执行超时
            AgentCancelledError: cancel_event 被 set
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
        phase = 0
        max_iterations = self.config.max_iterations

        while iteration < max_iterations:
            await self._check_cancel(cancel_event, iteration, "Agent Stream")

            iteration += 1
            phase += 1
            phase_label = self.PHASE_LABELS.get(phase, f"阶段 {phase}")

            logger.info(
                f"[Agent Stream] Phase {phase} ({phase_label}), "
                f"iteration {iteration}/{max_iterations}"
            )

            yield {
                "type": "phase_start",
                "phase": phase,
                "phase_label": phase_label,
            }

            messages = await self._prepare_messages()

            # 流式调用 LLM（带超时保护）
            system_prompt = self._adapt_system_prompt()
            final_response = None
            try:
                async with asyncio.timeout(self.config.timeout):
                    async for event in self.provider.stream_message(
                        system_prompt,
                        messages,
                        self.tools.get_schemas(),
                    ):
                        if isinstance(event, ProviderResponse):
                            final_response = event
                        else:
                            yield {"type": "stream", "event": event, "phase": phase}
            except TimeoutError:
                logger.error(
                    f"[Agent Stream] LLM stream timed out after "
                    f"{self.config.timeout}s, session_id={self._session_id}"
                )
                raise AgentTimeoutError(
                    session_id=self._session_id,
                    iteration=iteration,
                    timeout=self.config.timeout,
                    detail="llm_stream",
                )

            if final_response is None:
                logger.warning(
                    f"[Agent Stream] No final response from provider, "
                    f"session_id={self._session_id}"
                )
                break

            final_response = await self._apply_after_llm_hook(final_response)

            logger.info(
                f"[Agent Stream] Phase {phase}: stop_reason={final_response.stop_reason}, "
                f"has_tools={final_response.has_tool_calls}"
            )

            if not final_response.has_tool_calls:
                await self._handle_completion(final_response.text, iteration)
                yield {
                    "type": "complete",
                    "text": final_response.text,
                    "phase": phase,
                }
                return

            # 添加助手消息（包含工具调用）
            self.context.add_assistant_message(final_response.content)

            tool_names = [tc.name for tc in final_response.tool_calls]
            logger.info(f"[Agent Stream] Phase {phase} tool calls: {tool_names}")

            # 执行工具并 yield 结果（带超时保护）
            for tool_call in final_response.tool_calls:
                yield {
                    "type": "tool_start",
                    "tool_name": tool_call.name,
                    "tool_id": tool_call.id,
                    "phase": phase,
                }

                try:
                    result = await asyncio.wait_for(
                        self.executor.execute(tool_call, self.ask_callback),
                        timeout=self.config.timeout,
                    )
                except TimeoutError:
                    logger.error(
                        f"[Agent Stream] Tool '{tool_call.name}' timed out after "
                        f"{self.config.timeout}s, session_id={self._session_id}"
                    )
                    raise AgentTimeoutError(
                        session_id=self._session_id,
                        iteration=iteration,
                        timeout=self.config.timeout,
                        detail=f"tool_execution:{tool_call.name}",
                    )

                self.context.add_tool_result(tool_call.id, result)

                yield {
                    "type": "tool_result",
                    "tool_id": tool_call.id,
                    "result": result,
                    "phase": phase,
                }

            # 共享：保存 checkpoint + 截断上下文
            await self._post_tool_iteration(iteration)

        logger.error(
            f"[Agent Stream] Maximum iterations reached! session_id={self._session_id}"
        )
        await self._delete_checkpoint()
        raise AgentMaxIterationsError(
            session_id=self._session_id,
            iteration=iteration,
            max_iterations=max_iterations,
        )

    async def _call_llm(self, messages: list[dict]) -> ProviderResponse:
        """调用 LLM（带超时保护）

        Raises:
            AgentTimeoutError: 调用超时
        """
        system_prompt = self._adapt_system_prompt()

        try:
            return await asyncio.wait_for(
                self.provider.create_message(
                    system=system_prompt,
                    messages=messages,
                    tools=self.tools.get_schemas(),
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                ),
                timeout=self.config.timeout,
            )
        except TimeoutError:
            logger.error(
                f"[Agent] LLM call timed out after {self.config.timeout}s, "
                f"session_id={self._session_id}"
            )
            raise AgentTimeoutError(
                session_id=self._session_id,
                timeout=self.config.timeout,
                detail="llm_call",
            )

    def _adapt_system_prompt(self) -> str:
        """
        根据模型适配系统提示词（P1-4: 缓存 adapted prompt，model 不变时复用）

        Returns:
            适配后的系统提示词
        """
        cache_key = (self.provider.model, self.config.system_prompt)
        if hasattr(self, "_adapted_cache") and self._adapted_cache[0] == cache_key:
            return self._adapted_cache[1]

        from pyagentforge.kernel.model_registry import get_model
        from pyagentforge.agents.prompts.adapter import get_prompt_adapter
        from pyagentforge.agents.prompts.base import AdaptationContext

        try:
            adapter = get_prompt_adapter()
            model_config = get_model(self.provider.model)

            if not model_config:
                logger.debug(
                    f"No model config found for {self.provider.model}, "
                    f"using base prompt"
                )
                return self.config.system_prompt

            context = AdaptationContext(
                model_id=self.provider.model,
                model_config=model_config,
                base_prompt=self.config.system_prompt,
                available_tools=self.tools.get_schemas(),
            )

            adapted_prompt = adapter.adapt_prompt(context)
            self._adapted_cache = (cache_key, adapted_prompt)
            logger.info(
                f"Adapted system prompt for model={self.provider.model}, "
                f"len={len(adapted_prompt)}"
            )
            return adapted_prompt

        except Exception as e:
            logger.warning(
                f"Failed to adapt system prompt: {e}, "
                f"falling back to base prompt"
            )
            return self.config.system_prompt

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

    async def auto_classify_task(self, prompt: str) -> dict[str, Any]:
        """
        自动分类任务并返回推荐配置

        Args:
            prompt: 用户输入的任务描述

        Returns:
            包含分类结果的字典:
            {
                "category": str,  # 类别名称
                "confidence": float,  # 置信度
                "recommended_model": str,  # 推荐模型
                "recommended_agents": list[str],  # 推荐代理
                "complexity": str,  # 复杂度
                "method": str,  # 分类方法
            }
        """
        if not self.category_registry:
            # 没有分类器，返回默认值
            return {
                "category": "coding",
                "confidence": 0.5,
                "recommended_model": self.provider.model,
                "recommended_agents": ["explore", "plan", "code"],
                "complexity": "standard",
                "method": "fallback",
            }

        try:
            # 尝试使用异步分类
            result = await self.category_registry.classify_async(
                prompt,
                use_semantic=True,
                use_llm=False,  # 默认不使用 LLM 分类以节省成本
            )

            if result and result.category:
                return {
                    "category": result.category.name,
                    "confidence": result.confidence,
                    "recommended_model": result.category.model,
                    "recommended_agents": result.category.agents,
                    "complexity": result.category.complexity.value,
                    "method": result.method,
                    "matched_keywords": result.matched_keywords,
                }

        except Exception as e:
            logger.warning(f"Task classification failed: {e}")

        # Fallback
        return {
            "category": "coding",
            "confidence": 0.5,
            "recommended_model": self.provider.model,
            "recommended_agents": ["explore", "plan", "code"],
            "complexity": "standard",
            "method": "fallback",
        }

    def get_category_registry(self) -> Any:
        """获取类别注册表"""
        return self.category_registry

    # ── Shared iteration helpers ─────────────────────────────────
    # run() 与 run_stream() 共用，确保 hook / checkpoint 行为一致。

    async def _prepare_messages(self) -> list[dict]:
        """获取 API 消息并执行 on_before_llm_call 钩子。"""
        messages = self.context.get_messages_for_api()
        if self.plugin_manager:
            modified = await self.plugin_manager.emit_hook(
                "on_before_llm_call", messages
            )
            if modified and modified[0]:
                messages = modified[0]
        return messages

    async def _apply_after_llm_hook(
        self, response: ProviderResponse
    ) -> ProviderResponse:
        """执行 on_after_llm_call 钩子，返回可能被修改的 response。"""
        if self.plugin_manager:
            modified = await self.plugin_manager.emit_hook(
                "on_after_llm_call", response
            )
            if (
                modified
                and modified[0]
                and isinstance(modified[0], ProviderResponse)
            ):
                return modified[0]
        return response

    async def _handle_completion(self, text: str, iteration: int) -> None:
        """任务完成共享逻辑：更新上下文 → 清理 checkpoint → on_task_complete。"""
        self.context.add_assistant_text(text)
        await self._delete_checkpoint()
        if self.plugin_manager:
            await self.plugin_manager.emit_hook("on_task_complete", text)
        logger.info(
            f"Agent completed: session_id={self._session_id}, iterations={iteration}"
        )

    async def _post_tool_iteration(self, iteration: int) -> None:
        """工具迭代后共享逻辑：保存 checkpoint → 截断上下文。"""
        await self._save_checkpoint(iteration)
        if len(self.context) > self.context.max_messages * 0.8:
            self.context.truncate()

    async def _check_cancel(
        self, cancel_event: asyncio.Event | None, iteration: int, label: str
    ) -> None:
        """检查取消信号，已 set 则抛出 AgentCancelledError。"""
        if cancel_event is not None and cancel_event.is_set():
            logger.info(
                f"[{label}] Cancelled by cancel_event, "
                f"session_id={self._session_id}, iteration={iteration}"
            )
            raise AgentCancelledError(
                session_id=self._session_id,
                iteration=iteration,
            )

    # ── Checkpoint helpers (P1-7: 重试 + 降级) ─────────────────

    _CHECKPOINT_MAX_RETRIES = 3
    _CHECKPOINT_FAIL_THRESHOLD = 5
    _RETRYABLE_ERRORS = (OSError, TimeoutError, ConnectionError)

    async def _save_checkpoint(self, iteration: int) -> None:
        if not self.checkpointer:
            return
        if getattr(self, "_checkpoint_disabled", False):
            return

        cp = Checkpoint(
            session_id=self._session_id,
            iteration=iteration,
            context_data=self.context.to_dict(),
            metadata={
                "model": self.provider.model,
                "max_iterations": self.config.max_iterations,
            },
        )

        last_err: Exception | None = None
        for attempt in range(self._CHECKPOINT_MAX_RETRIES):
            try:
                await self.checkpointer.save(self._session_id, cp)
                self._checkpoint_consecutive_failures = 0
                return
            except self._RETRYABLE_ERRORS as e:
                last_err = e
                wait = 0.1 * (2 ** attempt)
                logger.warning(
                    "Checkpoint save retryable error (attempt %d/%d): %s",
                    attempt + 1, self._CHECKPOINT_MAX_RETRIES, e,
                )
                await asyncio.sleep(wait)
            except Exception as e:
                last_err = e
                logger.warning("Checkpoint save non-retryable error: %s", e)
                break

        count = getattr(self, "_checkpoint_consecutive_failures", 0) + 1
        self._checkpoint_consecutive_failures = count
        if count >= self._CHECKPOINT_FAIL_THRESHOLD:
            self._checkpoint_disabled = True
            logger.error(
                "Checkpoint disabled after %d consecutive failures", count
            )
        if self.plugin_manager:
            await self.plugin_manager.emit_hook(
                "on_checkpoint_failed",
                {"session_id": self._session_id, "error": str(last_err), "consecutive": count},
            )

    async def _restore_from_checkpoint(self) -> int | None:
        """从 checkpoint 恢复上下文，返回恢复的 iteration 编号。"""
        if not self.checkpointer:
            return None
        try:
            cp = await self.checkpointer.load(self._session_id)
            if cp is None:
                return None
            self.context = ContextManager.from_dict(cp.context_data)
            logger.info(
                f"Restored checkpoint: iteration={cp.iteration}, "
                f"messages={len(self.context)}"
            )
            return cp.iteration
        except Exception as e:
            logger.warning(f"Failed to restore checkpoint: {e}")
            return None

    async def _delete_checkpoint(self) -> None:
        if not self.checkpointer:
            return
        try:
            await self.checkpointer.delete(self._session_id)
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")

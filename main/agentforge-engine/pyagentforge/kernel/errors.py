"""
Agent 引擎异常层次

所有引擎级异常均继承自 AgentError，便于 Service 层统一捕获。
每个异常携带 session_id / iteration / detail，支持结构化日志。
"""

from __future__ import annotations


class AgentError(Exception):
    """Agent 引擎基础异常"""

    def __init__(
        self,
        message: str = "",
        *,
        session_id: str = "",
        iteration: int = 0,
        detail: str = "",
    ) -> None:
        self.session_id = session_id
        self.iteration = iteration
        self.detail = detail
        super().__init__(message or self._default_message())

    def _default_message(self) -> str:
        return "Agent error"


class AgentTimeoutError(AgentError):
    """LLM 调用或工具批量执行超时"""

    def __init__(
        self,
        message: str = "",
        *,
        session_id: str = "",
        iteration: int = 0,
        detail: str = "",
        timeout: float = 0,
    ) -> None:
        self.timeout = timeout
        super().__init__(
            message,
            session_id=session_id,
            iteration=iteration,
            detail=detail,
        )

    def _default_message(self) -> str:
        return f"Agent operation timed out after {self.timeout}s"


class AgentCancelledError(AgentError):
    """外部通过 cancel_event 取消执行"""

    def _default_message(self) -> str:
        return "Agent execution was cancelled"


class AgentMaxIterationsError(AgentError):
    """执行循环超过 max_iterations 上限"""

    def __init__(
        self,
        message: str = "",
        *,
        session_id: str = "",
        iteration: int = 0,
        detail: str = "",
        max_iterations: int = 0,
    ) -> None:
        self.max_iterations = max_iterations
        super().__init__(
            message,
            session_id=session_id,
            iteration=iteration,
            detail=detail,
        )

    def _default_message(self) -> str:
        return f"Agent exceeded maximum iterations ({self.max_iterations})"


class AgentProviderError(AgentError):
    """LLM Provider 调用异常（非超时类）"""

    def __init__(
        self,
        message: str = "",
        *,
        session_id: str = "",
        iteration: int = 0,
        detail: str = "",
        provider_error: Exception | None = None,
    ) -> None:
        self.provider_error = provider_error
        super().__init__(
            message,
            session_id=session_id,
            iteration=iteration,
            detail=detail,
        )

    def _default_message(self) -> str:
        if self.provider_error:
            return f"Provider error: {self.provider_error}"
        return "Provider error"


class AgentToolError(AgentError):
    """工具执行异常（非超时类）"""

    def __init__(
        self,
        message: str = "",
        *,
        session_id: str = "",
        iteration: int = 0,
        detail: str = "",
        tool_name: str = "",
        tool_error: Exception | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.tool_error = tool_error
        super().__init__(
            message,
            session_id=session_id,
            iteration=iteration,
            detail=detail,
        )

    def _default_message(self) -> str:
        if self.tool_name:
            return f"Tool '{self.tool_name}' execution failed"
        return "Tool execution failed"

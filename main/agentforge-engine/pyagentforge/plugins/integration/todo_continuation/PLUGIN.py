"""
Todo Continuation Enforcer Plugin

v4.0: 自动续接未完成的 Todo 任务
v4.1: 增强 Todo 检测 + TaskSystem 集成

通过多种模式检测代理是否已完成任务，如未完成则自动注入续接提示。
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.plugin.base import Plugin as BasePlugin
from pyagentforge.plugin.hooks import HookDecision, HookType
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

# 常量
COUNTDOWN_SECONDS = 2
SKIP_AGENTS = ["oracle", "librarian"]
CONTEXT_EXHAUSTED_THRESHOLD = 0.95  # 95% 上下文使用时跳过


@dataclass
class SessionState:
    """会话状态"""

    countdown_timer: asyncio.TimerHandle | None = None
    is_recovering: bool = False
    abort_detected_at: float | None = None
    last_response_time: float = 0.0
    pending_todos: list[str] = field(default_factory=list)


class TodoContinuationEnforcerPlugin(BasePlugin):
    """
    Todo Continuation Enforcer Plugin

    Features:
    - 2 秒倒计时检测任务完成
    - 自动注入续接提示
    - 智能跳过条件
    - 恢复检测
    """

    def __init__(self):
        super().__init__()

        self.metadata = self.PluginMetadata(
            id="todo_continuation",
            name="Todo Continuation Enforcer",
            version="4.0.0",
            description="Auto-continuation for incomplete todo tasks",
            author="PyAgentForge Team",
        )

        # 会话状态管理
        self._session_states: dict[str, SessionState] = {}

    async def on_activate(self) -> None:
        """激活插件"""
        # 注册钩子
        self.register_hook(
            HookType.ON_AFTER_LLM_CALL,
            self._on_after_llm_call,
            priority=500,
        )

        self.register_hook(
            HookType.USER_PROMPT_SUBMIT,
            self._on_user_prompt_submit,
            priority=500,
        )

        logger.info("Todo Continuation Enforcer activated")

    async def on_deactivate(self) -> None:
        """停用插件"""
        # 清理所有定时器
        for state in self._session_states.values():
            if state.countdown_timer:
                state.countdown_timer.cancel()

        self._session_states.clear()

        logger.info("Todo Continuation Enforcer deactivated")

    def _get_session_state(self, session_id: str) -> SessionState:
        """获取或创建会话状态"""
        if session_id not in self._session_states:
            self._session_states[session_id] = SessionState()
        return self._session_states[session_id]

    def should_skip_continuation(
        self,
        session_id: str,
        agent: str | None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        检查是否应该跳过续接（增强版）

        Args:
            session_id: 会话 ID
            agent: 代理名称
            context: 上下文信息

        Returns:
            True if should skip
        """
        state = self._get_session_state(session_id)
        context = context or {}

        # 1. 正在恢复中
        if state.is_recovering:
            logger.debug(f"Skipping continuation - recovering session: {session_id}")
            return True

        # 2. 代理在跳过列表中
        if agent and agent in SKIP_AGENTS:
            logger.debug(f"Skipping continuation - agent in skip list: {agent}")
            return True

        # 3. 有运行中的后台任务
        if self._has_running_background_tasks(session_id, context):
            logger.debug(
                f"Skipping continuation - background tasks running: {session_id}"
            )
            return True

        # 4. 检测到 abort
        if self._is_abort_detected(session_id, context):
            logger.debug(f"Skipping continuation - abort detected: {session_id}")
            return True

        # 5. v4.1: 上下文即将耗尽
        if self._is_context_exhausted(context):
            logger.debug(f"Skipping continuation - context exhausted: {session_id}")
            return True

        # 6. v4.1: 等待用户输入（检测特定模式）
        if self._is_waiting_for_user(context):
            logger.debug(f"Skipping continuation - waiting for user: {session_id}")
            return True

        return False

    def _is_context_exhausted(self, context: dict[str, Any]) -> bool:
        """检查上下文是否即将耗尽"""
        # 检查上下文使用率
        context_usage = context.get("context_usage", 0.0)
        if context_usage >= CONTEXT_EXHAUSTED_THRESHOLD:
            return True

        # 检查剩余 token 数
        remaining_tokens = context.get("remaining_tokens")
        max_tokens = context.get("max_tokens", 200000)

        return bool(remaining_tokens is not None and remaining_tokens < max_tokens * 0.05)

    def _is_waiting_for_user(self, context: dict[str, Any]) -> bool:
        """检查是否在等待用户输入"""
        # 检查最后的响应是否有等待模式
        last_response = context.get("last_response", "")
        if not last_response:
            return False

        wait_patterns = [
            r"\?$",  # 以问号结尾
            r"请问",
            r"请提供",
            r"请选择",
            r"请确认",
            r"需要您",
            r"等待您的",
            r"您希望",
        ]

        return any(re.search(pattern, last_response) for pattern in wait_patterns)

    def _has_running_background_tasks(
        self,
        session_id: str,
        context: dict[str, Any],
    ) -> bool:
        """检查是否有运行中的后台任务"""
        background_manager = context.get("background_manager")
        if not background_manager:
            return False

        active_tasks = background_manager.list_by_session(session_id)
        running = [t for t in active_tasks if t.status in ("pending", "running")]

        return len(running) > 0

    def _is_abort_detected(
        self,
        session_id: str,
        context: dict[str, Any],
    ) -> bool:
        """检测是否发生 abort"""
        state = self._get_session_state(session_id)

        # 检查最近的响应时间
        if state.abort_detected_at:
            time_since_abort = time.time() - state.abort_detected_at
            # 5 秒内的 abort 仍然有效
            if time_since_abort < 5.0:
                return True

        return False

    def _extract_pending_todos(self, response: str) -> list[str]:
        """
        从响应中提取未完成的 Todo（增强版）

        支持多种格式：
        1. Markdown 任务列表: - [ ] task
        2. TODO 标记: TODO:, FIXME:, XXX:
        3. 中文待办: 待办:, 待完成:
        4. 数字列表中的待办项

        Args:
            response: LLM 响应

        Returns:
            待完成的 Todo 列表
        """
        todos = []
        lines = response.split("\n")

        for line in lines:
            stripped = line.strip()

            # 1. Markdown 未完成任务
            if match := re.match(r"^[-*]\s*\[\s*\]\s*(.+)$", stripped):
                todos.append(match.group(1))
                continue

            # 2. TODO/FIXME/XXX 标记
            if match := re.match(r"^(?:TODO|FIXME|XXX)\s*[:：]\s*(.+)$", stripped, re.IGNORECASE):
                todos.append(match.group(1))
                continue

            # 3. 中文待办标记
            if match := re.match(r"^(?:待办|待完成|未完成)\s*[:：]\s*(.+)$", stripped):
                todos.append(match.group(1))
                continue

            # 4. 保留旧逻辑兼容性
            if "[ ]" in stripped or "TODO:" in stripped or "待办:" in stripped:
                if stripped not in todos:
                    todos.append(stripped)

        return todos

    def _get_pending_tasks_from_system(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从 TaskSystem 获取未完成任务

        Args:
            context: 上下文

        Returns:
            未完成任务列表
        """
        task_manager = context.get("task_manager")
        if not task_manager:
            return []

        try:
            # 导入 TaskStatus
            from pyagentforge.plugins.integration.task_system import TaskStatus

            # 获取 pending 和 in_progress 任务
            pending = task_manager.list_tasks(status=TaskStatus.PENDING)
            in_progress = task_manager.list_tasks(status=TaskStatus.IN_PROGRESS)

            return [
                {"id": t.id, "title": t.title, "status": t.status.value}
                for t in pending + in_progress
            ]
        except Exception as e:
            logger.warning(f"Failed to get tasks from TaskSystem: {e}")
            return []

    async def _on_after_llm_call(
        self,
        response: Any,
        context: dict[str, Any],
    ) -> None:
        """
        LLM 调用后的钩子（增强版）

        Args:
            response: LLM 响应
            context: 上下文
        """
        session_id = context.get("session_id", "")
        agent = context.get("agent")

        # 检查是否应该跳过
        if self.should_skip_continuation(session_id, agent, context):
            return

        state = self._get_session_state(session_id)

        # 提取待完成的 Todo（从响应中）
        response_text = getattr(response, "content", str(response))
        pending_todos = self._extract_pending_todos(response_text)

        # v4.1: 同时检查 TaskSystem
        pending_tasks = self._get_pending_tasks_from_system(context)

        # 合并结果
        all_pending = pending_todos.copy()
        if pending_tasks:
            # 添加 TaskSystem 中的任务
            for task in pending_tasks:
                task_str = f"[{task['id']}] {task['title']} ({task['status']})"
                if task_str not in all_pending:
                    all_pending.append(task_str)

        if not all_pending:
            # 没有待完成的 Todo，清理状态
            state.pending_todos = []
            return

        # 更新待办列表
        state.pending_todos = all_pending
        state.last_response_time = time.time()

        # 更新上下文（用于后续检测）
        context["last_response"] = response_text

        # 取消之前的定时器
        if state.countdown_timer:
            state.countdown_timer.cancel()

        # 启动倒计时
        loop = asyncio.get_event_loop()
        state.countdown_timer = loop.call_later(
            COUNTDOWN_SECONDS,
            lambda: asyncio.create_task(
                self._inject_continuation(session_id, context)
            ),
        )

        logger.debug(
            f"Started {COUNTDOWN_SECONDS}s countdown for session: {session_id} "
            f"with {len(all_pending)} pending items"
        )

    async def _on_user_prompt_submit(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> tuple[HookDecision, str | None]:
        """
        用户提交时的钩子

        Args:
            prompt: 用户提示
            context: 上下文

        Returns:
            (decision, message)
        """
        session_id = context.get("session_id", "")
        state = self._get_session_state(session_id)

        # 用户发起新请求，取消续接
        if state.countdown_timer:
            state.countdown_timer.cancel()
            state.countdown_timer = None
            state.pending_todos = []
            logger.debug(f"Cancelled continuation - user submitted prompt: {session_id}")

        return HookDecision.ALLOW, None

    async def _inject_continuation(
        self,
        session_id: str,
        context: dict[str, Any],
    ) -> None:
        """
        注入续接提示

        Args:
            session_id: 会话 ID
            context: 上下文
        """
        state = self._get_session_state(session_id)

        # 检查是否仍有待完成的 Todo
        if not state.pending_todos:
            return

        # 标记为恢复中
        state.is_recovering = True

        try:
            # 构建续接提示
            continuation_prompt = self._build_continuation_prompt(state.pending_todos)

            # 注入提示（需要通过引擎注入）
            # 这里假设 context 中有引擎引用
            engine = context.get("engine")
            if engine and hasattr(engine, "inject_user_message"):
                await engine.inject_user_message(continuation_prompt)

                logger.info(
                    f"Injected continuation prompt for session: {session_id}"
                )

        finally:
            # 清理状态
            state.is_recovering = False
            state.countdown_timer = None
            state.pending_todos = []

    def _build_continuation_prompt(self, todos: list[str]) -> str:
        """
        构建续接提示（增强版）

        Args:
            todos: 待完成的 Todo 列表

        Returns:
            续接提示
        """
        todo_list = "\n".join(f"- {todo}" for todo in todos)

        return f"""看起来还有以下任务未完成：

{todo_list}

请继续完成这些任务。如果其中某些任务需要用户确认或等待其他条件，请先跳过并处理其他任务。"""


# 导出
__all__ = ["TodoContinuationEnforcerPlugin"]

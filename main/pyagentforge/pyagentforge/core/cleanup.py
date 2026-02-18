"""
进程级清理机制

确保程序异常退出时能够正确清理所有资源。

Features:
- 注册 SIGINT, SIGTERM 信号处理器
- 支持注册清理回调函数
- 提供 atexit 兼容性
- Windows 兼容（使用 signal.SIGBREAK）
- 异步清理支持
- 超时保护
"""

import asyncio
import atexit
import signal
import sys
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Union

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CleanupPriority(int, Enum):
    """清理优先级 - 越高越先执行"""

    CRITICAL = 100  # 关键资源（数据库连接等）
    HIGH = 75  # 高优先级（网络连接等）
    NORMAL = 50  # 正常优先级（文件句柄等）
    LOW = 25  # 低优先级（日志刷新等）
    LAST = 0  # 最后执行


@dataclass
class CleanupCallback:
    """清理回调条目"""

    callback: Callable[[], Union[None, Coroutine[Any, Any, None]]]
    name: str
    priority: int = CleanupPriority.NORMAL.value
    is_async: bool = False
    timeout: float = 5.0  # 超时时间（秒）


@dataclass
class CleanupStats:
    """清理统计"""

    total_registered: int = 0
    total_executed: int = 0
    total_failed: int = 0
    total_timeout: int = 0
    execution_time_ms: float = 0.0


class ProcessCleanup:
    """
    进程级清理管理器

    确保程序退出时（正常或异常）能够正确清理所有注册的资源。

    Usage:
        cleanup = ProcessCleanup()

        # 注册同步回调
        cleanup.register(lambda: close_db(), name="close_db", priority=CleanupPriority.HIGH)

        # 注册异步回调
        cleanup.register_async(close_connections, name="close_connections")

        # 启用信号处理
        cleanup.enable_signal_handlers()

        # 使用上下文管理器
        with cleanup.context():
            # ... 程序逻辑
            pass
    """

    _instance: "ProcessCleanup | None" = None

    def __init__(self):
        self._callbacks: list[CleanupCallback] = []
        self._is_cleaning: bool = False
        self._is_enabled: bool = False
        self._stats = CleanupStats()
        self._loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def get_instance(cls) -> "ProcessCleanup":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        callback: Callable[[], None],
        name: str = "",
        priority: int = CleanupPriority.NORMAL.value,
        timeout: float = 5.0,
    ) -> None:
        """
        注册同步清理回调

        Args:
            callback: 清理函数
            name: 回调名称（用于日志）
            priority: 优先级（越高越先执行）
            timeout: 超时时间
        """
        entry = CleanupCallback(
            callback=callback,
            name=name or callback.__name__,
            priority=priority,
            is_async=False,
            timeout=timeout,
        )
        self._callbacks.append(entry)
        self._stats.total_registered += 1

        logger.debug(
            f"Registered cleanup callback: {entry.name}",
            extra_data={"priority": priority, "is_async": False},
        )

    def register_async(
        self,
        callback: Callable[[], Coroutine[Any, Any, None]],
        name: str = "",
        priority: int = CleanupPriority.NORMAL.value,
        timeout: float = 5.0,
    ) -> None:
        """
        注册异步清理回调

        Args:
            callback: 异步清理函数
            name: 回调名称
            priority: 优先级
            timeout: 超时时间
        """
        entry = CleanupCallback(
            callback=callback,
            name=name or callback.__name__,
            priority=priority,
            is_async=True,
            timeout=timeout,
        )
        self._callbacks.append(entry)
        self._stats.total_registered += 1

        logger.debug(
            f"Registered async cleanup callback: {entry.name}",
            extra_data={"priority": priority, "is_async": True},
        )

    def unregister(self, name: str) -> bool:
        """
        注销清理回调

        Args:
            name: 回调名称

        Returns:
            是否成功注销
        """
        for i, entry in enumerate(self._callbacks):
            if entry.name == name:
                self._callbacks.pop(i)
                self._stats.total_registered -= 1
                logger.debug(f"Unregistered cleanup callback: {name}")
                return True
        return False

    def enable_signal_handlers(self) -> None:
        """
        启用信号处理器

        注册 SIGINT (Ctrl+C) 和 SIGTERM 的处理器。
        Windows 下还会注册 SIGBREAK。
        """
        if self._is_enabled:
            return

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Windows 兼容
        if sys.platform == "win32":
            try:
                signal.signal(signal.SIGBREAK, self._signal_handler)  # type: ignore
            except (AttributeError, ValueError):
                pass

        # 注册 atexit 作为最后保障
        atexit.register(self.cleanup_sync)

        self._is_enabled = True
        logger.info("Process cleanup signal handlers enabled")

    def disable_signal_handlers(self) -> None:
        """禁用信号处理器"""
        if not self._is_enabled:
            return

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        if sys.platform == "win32":
            try:
                signal.signal(signal.SIGBREAK, signal.SIG_DFL)  # type: ignore
            except (AttributeError, ValueError):
                pass

        atexit.unregister(self.cleanup_sync)
        self._is_enabled = False
        logger.info("Process cleanup signal handlers disabled")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """信号处理器"""
        signal_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(
            f"Received signal {signal_name}, starting cleanup...",
            extra_data={"signal": signum},
        )

        self.cleanup_sync()
        sys.exit(128 + signum)

    async def cleanup(self) -> CleanupStats:
        """
        执行清理（异步版本）

        按优先级从高到低执行所有注册的清理回调。

        Returns:
            清理统计信息
        """
        if self._is_cleaning:
            logger.warning("Cleanup already in progress, skipping...")
            return self._stats

        self._is_cleaning = True
        start_time = datetime.now()

        # 按优先级排序（高到低）
        sorted_callbacks = sorted(self._callbacks, key=lambda x: -x.priority)

        logger.info(
            f"Starting cleanup with {len(sorted_callbacks)} callbacks",
            extra_data={"callbacks": [cb.name for cb in sorted_callbacks]},
        )

        for entry in sorted_callbacks:
            try:
                if entry.is_async:
                    await self._execute_async_callback(entry)
                else:
                    await self._execute_sync_callback(entry)

            except Exception as e:
                self._stats.total_failed += 1
                logger.error(
                    f"Cleanup callback failed: {entry.name}",
                    extra_data={"error": str(e), "callback": entry.name},
                )

        self._stats.execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            "Cleanup completed",
            extra_data={
                "executed": self._stats.total_executed,
                "failed": self._stats.total_failed,
                "timeout": self._stats.total_timeout,
                "time_ms": self._stats.execution_time_ms,
            },
        )

        self._is_cleaning = False
        return self._stats

    async def _execute_async_callback(self, entry: CleanupCallback) -> None:
        """执行异步回调"""
        try:
            await asyncio.wait_for(entry.callback(), timeout=entry.timeout)  # type: ignore
            self._stats.total_executed += 1
            logger.debug(f"Executed async cleanup: {entry.name}")
        except asyncio.TimeoutError:
            self._stats.total_timeout += 1
            logger.warning(
                f"Cleanup callback timed out: {entry.name}",
                extra_data={"timeout": entry.timeout},
            )
        except Exception as e:
            self._stats.total_failed += 1
            raise e

    async def _execute_sync_callback(self, entry: CleanupCallback) -> None:
        """执行同步回调"""
        try:
            # 在线程池中执行同步回调以支持超时
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, entry.callback),  # type: ignore
                timeout=entry.timeout,
            )
            self._stats.total_executed += 1
            logger.debug(f"Executed sync cleanup: {entry.name}")
        except asyncio.TimeoutError:
            self._stats.total_timeout += 1
            logger.warning(
                f"Cleanup callback timed out: {entry.name}",
                extra_data={"timeout": entry.timeout},
            )
        except Exception as e:
            self._stats.total_failed += 1
            raise e

    def cleanup_sync(self) -> CleanupStats:
        """
        执行清理（同步版本）

        用于信号处理器和 atexit 回调。
        """
        if self._is_cleaning:
            return self._stats

        # 尝试在事件循环中运行
        try:
            loop = asyncio.get_running_loop()
            # 如果已有运行中的循环，创建任务
            asyncio.ensure_future(self.cleanup(), loop=loop)
        except RuntimeError:
            # 没有运行中的循环，创建新的
            asyncio.run(self.cleanup())

        return self._stats

    @contextmanager
    def context(self):
        """
        同步上下文管理器

        Usage:
            with cleanup.context():
                # ... 程序逻辑
        """
        try:
            yield self
        finally:
            self.cleanup_sync()

    @asynccontextmanager
    async def async_context(self):
        """
        异步上下文管理器

        Usage:
            async with cleanup.async_context():
                # ... 程序逻辑
        """
        try:
            yield self
        finally:
            await self.cleanup()

    def get_stats(self) -> CleanupStats:
        """获取清理统计"""
        return self._stats

    def clear(self) -> None:
        """清除所有注册的回调"""
        self._callbacks.clear()
        self._stats = CleanupStats()
        logger.debug("Cleared all cleanup callbacks")


# 全局便捷函数
_global_cleanup: ProcessCleanup | None = None


def get_cleanup() -> ProcessCleanup:
    """获取全局清理管理器"""
    global _global_cleanup
    if _global_cleanup is None:
        _global_cleanup = ProcessCleanup()
    return _global_cleanup


def register_cleanup(
    callback: Callable[[], None],
    name: str = "",
    priority: int = CleanupPriority.NORMAL.value,
) -> None:
    """注册全局清理回调"""
    get_cleanup().register(callback, name, priority)


def register_cleanup_async(
    callback: Callable[[], Coroutine[Any, Any, None]],
    name: str = "",
    priority: int = CleanupPriority.NORMAL.value,
) -> None:
    """注册全局异步清理回调"""
    get_cleanup().register_async(callback, name, priority)


def enable_cleanup_signals() -> None:
    """启用全局清理信号处理"""
    get_cleanup().enable_signal_handlers()

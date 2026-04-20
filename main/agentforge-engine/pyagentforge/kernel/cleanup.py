"""
杩涚▼绾ф竻鐞嗘満鍒?

确保程序异常退出时能够正确清理所有资源。

Features:
- 娉ㄥ唽 SIGINT, SIGTERM 淇彿澶勭悊鍣?
- 鏀寔娉ㄥ唽娓呯悊鍥炶皟鍑芥暟
- 鎻愪緵 atexit 鍏煎鎬?
- Windows 鍏煎锛堜娇鐢?signal.SIGBREAK锛?
- 寮傛娓呯悊鏀寔
- 瓒呮椂淇濇姢
"""

import asyncio
import atexit
import signal
import sys
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager, contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CleanupPriority(int, Enum):
    """"""

    CRITICAL = 100  # 鍏抽敭璧勬簮锛堟暟鎹簱杩炴帴绛夛級
    HIGH = 75  # 楂樹紭鍏堢骇锛堢綉缁滆繛鎺ョ瓑锛?
    NORMAL = 50  # 姝ｅ父浼樺厛绾э紙鏂囦欢鍙ユ焺绛夛級
    LOW = 25  # 浣庝紭鍏堢骇锛堟棩蹇楀埛鏂扮瓑锛?
    LAST = 0  # 最后执行


@dataclass
class CleanupCallback:
    """娓呯悊鍥炶皟鏉＄洰"""

    callback: Callable[[], None | Coroutine[Any, Any, None]]
    name: str
    priority: int = CleanupPriority.NORMAL.value
    is_async: bool = False
    timeout: float = 5.0  # 瓒呮椂鏃堕棿锛堢锛?


@dataclass
class CleanupStats:
    """"""

    total_registered: int = 0
    total_executed: int = 0
    total_failed: int = 0
    total_timeout: int = 0
    execution_time_ms: float = 0.0


class ProcessCleanup:
    """
    杩涚▼绾ф竻鐞嗙鐞嗗櫒

    确保程序退出时（正常或异常）能够正确清理所有注册的资源。

    Usage:
        cleanup = ProcessCleanup()

        #
        cleanup.register(lambda: close_db(), name="close_db", priority=CleanupPriority.HIGH)

        #
        cleanup.register_async(close_connections, name="close_connections")

        #
        cleanup.enable_signal_handlers()

        #
        with cleanup.context():
            # ... 绋嬪簭閫昏緫
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
        """鑾峰彇鍗曚緥瀹炰緥"""
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
        娉ㄥ唽鍚屾娓呯悊鍥炶皟

        Args:
            callback: 娓呯悊鍑芥暟
            name: 鍥炶皟鍚嶇О锛堢敤浜庢棩蹇楋級
            priority: 浼樺厛绾э紙瓒婇珮瓒婂厛鎵ц锛?
            timeout: 瓒呮椂鏃堕棿
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
        娉ㄥ唽寮傛娓呯悊鍥炶皟

        Args:
            callback: 寮傛娓呯悊鍑芥暟
            name: 鍥炶皟鍚嶇О
            priority: 浼樺厛绾?
            timeout: 瓒呮椂鏃堕棿
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
        娉ㄩ攢娓呯悊鍥炶皟

        Args:
            name: 鍥炶皟鍚嶇О

        Returns:
            鏄惁鎴愬姛娉ㄩ攢
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
        鍚敤淇彿澶勭悊鍣?

        娉ㄥ唽 SIGINT (Ctrl+C) 鍜?SIGTERM 鐨勫鐞嗗櫒銆?
        Windows 涓嬭繕浼氭敞鍐?SIGBREAK銆?
        """
        if self._is_enabled:
            return

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        #
        if sys.platform == "win32":
            with suppress(AttributeError, ValueError):
                signal.signal(signal.SIGBREAK, self._signal_handler)  # type: ignore

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
            with suppress(AttributeError, ValueError):
                signal.signal(signal.SIGBREAK, signal.SIG_DFL)  # type: ignore

        atexit.unregister(self.cleanup_sync)
        self._is_enabled = False
        logger.info("Process cleanup signal handlers disabled")

    def _signal_handler(self, signum: int, _frame: Any) -> None:
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
        鎵ц娓呯悊锛堝紓姝ョ増鏈級

        按优先级从高到低执行所有注册的清理回调。

        Returns:
            清理统计信息
        """
        if self._is_cleaning:
            logger.warning("Cleanup already in progress, skipping...")
            return self._stats

        self._is_cleaning = True
        start_time = datetime.now()

        # 鎸変紭鍏堢骇鎺掑簭锛堥珮鍒颁綆锛?
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
        """"""
        try:
            await asyncio.wait_for(entry.callback(), timeout=entry.timeout)  # type: ignore
            self._stats.total_executed += 1
            logger.debug(f"Executed async cleanup: {entry.name}")
        except TimeoutError:
            self._stats.total_timeout += 1
            logger.warning(
                f"Cleanup callback timed out: {entry.name}",
                extra_data={"timeout": entry.timeout},
            )
        except Exception as e:
            self._stats.total_failed += 1
            raise e

    async def _execute_sync_callback(self, entry: CleanupCallback) -> None:
        """"""
        try:
            #
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, entry.callback),  # type: ignore
                timeout=entry.timeout,
            )
            self._stats.total_executed += 1
            logger.debug(f"Executed sync cleanup: {entry.name}")
        except TimeoutError:
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
        鎵ц娓呯悊锛堝悓姝ョ増鏈級

        鐢ㄤ簬淇彿澶勭悊鍣ㄥ拰 atexit 鍥炶皟銆?
        """
        if self._is_cleaning:
            return self._stats

        #
        try:
            loop = asyncio.get_running_loop()
            #
            asyncio.ensure_future(self.cleanup(), loop=loop)
        except RuntimeError:
            #
            asyncio.run(self.cleanup())

        return self._stats

    @contextmanager
    def context(self):
        """
        鍚屾涓婁笅鏂囩鐞嗗櫒

        Usage:
            with cleanup.context():
                # ... 绋嬪簭閫昏緫
        """
        try:
            yield self
        finally:
            self.cleanup_sync()

    @asynccontextmanager
    async def async_context(self):
        """
        寮傛涓婁笅鏂囩鐞嗗櫒

        Usage:
            async with cleanup.async_context():
                # ... 绋嬪簭閫昏緫
        """
        try:
            yield self
        finally:
            await self.cleanup()

    def get_stats(self) -> CleanupStats:
        """"""
        return self._stats

    def clear(self) -> None:
        """清除所有注册的回调"""
        self._callbacks.clear()
        self._stats = CleanupStats()
        logger.debug("Cleared all cleanup callbacks")


# 鍏ㄥ眬渚挎嵎鍑芥暟
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
    """娉ㄥ唽鍏ㄥ眬娓呯悊鍥炶皟"""
    get_cleanup().register(callback, name, priority)


def register_cleanup_async(
    callback: Callable[[], Coroutine[Any, Any, None]],
    name: str = "",
    priority: int = CleanupPriority.NORMAL.value,
) -> None:
    """"""
    get_cleanup().register_async(callback, name, priority)


def enable_cleanup_signals() -> None:
    """启用全局清理信号处理"""
    get_cleanup().enable_signal_handlers()


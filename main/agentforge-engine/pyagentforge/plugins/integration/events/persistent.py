"""
持久化 EventBus

扩展 EventBus，将事件写入文件存储，
支持 Event Sourcing 式的事件回放。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyagentforge.plugins.integration.events.events import (
    Event,
    EventBus,
    EventType,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PersistentEventBus(EventBus):
    """持久化事件总线

    所有 emit 的事件自动追加到 JSONL 文件，
    支持按序列号回放历史事件。
    """

    def __init__(
        self,
        name: str = "persistent",
        storage_dir: str | Path = ".events",
    ) -> None:
        super().__init__(name=name)
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._storage_dir / f"{name}.jsonl"
        self._seq: int = self._count_existing_events()
        logger.info(
            "PersistentEventBus initialized",
            extra_data={"path": str(self._log_path), "existing_events": self._seq},
        )

    async def emit(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        """发布事件并持久化"""
        self._seq += 1
        merged_metadata = {"seq": self._seq, **(metadata or {})}

        pre_event = Event(
            type=event_type,
            data=data or {},
            source=source,
            metadata=merged_metadata,
        )
        self._append_to_log(pre_event)

        return await super().emit(event_type, data, source, metadata=merged_metadata)

    def _append_to_log(self, event: Event) -> None:
        """追加事件到 JSONL 文件"""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist event: {e}")

    def _count_existing_events(self) -> int:
        if not self._log_path.exists():
            return 0
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def replay(
        self,
        from_seq: int = 0,
        event_type: EventType | str | None = None,
    ) -> list[dict[str, Any]]:
        """回放历史事件

        Args:
            from_seq: 从哪个序列号开始
            event_type: 可选过滤事件类型

        Returns:
            事件字典列表
        """
        events: list[dict[str, Any]] = []
        if not self._log_path.exists():
            return events

        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event_dict = json.loads(line)
                    seq = event_dict.get("metadata", {}).get("seq", 0)
                    if seq < from_seq:
                        continue
                    if event_type:
                        type_str = event_type.value if isinstance(event_type, EventType) else event_type
                        if event_dict.get("type") != type_str:
                            continue
                    events.append(event_dict)
                except json.JSONDecodeError:
                    continue

        return events

    def get_event_count(self) -> int:
        return self._seq

    def clear_log(self) -> None:
        """清空事件日志"""
        if self._log_path.exists():
            self._log_path.unlink()
        self._seq = 0
        logger.info("Event log cleared")

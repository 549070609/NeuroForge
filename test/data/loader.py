"""
测试数据加载器

提供便捷的方法加载 knowledge/ 和 memory/ 目录下的预置数据，
用于测试环境中为被动/主动 Agent 注入知识和记忆。

用法示例:
    from test.data.loader import TestDataLoader

    loader = TestDataLoader()

    # 加载被动 Agent 的全部知识
    knowledge = loader.passive_knowledge()

    # 加载主动 Agent 的记忆条目（作为 MemoryEntry 对象）
    memories = loader.active_memories_as_entries()

    # 按主题过滤
    coding_knowledge = loader.passive_knowledge(topic="编程最佳实践")

    # 按标签过滤
    threat_items = loader.active_knowledge(tags=["威胁分级"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
MEMORY_DIR = DATA_DIR / "memory"


def _load_json(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _filter_entries(
    entries: list[dict[str, Any]],
    *,
    topic: str | None = None,
    tags: list[str] | None = None,
    importance_min: float | None = None,
    message_type: str | None = None,
) -> list[dict[str, Any]]:
    """按条件过滤条目列表。"""
    result = entries
    if topic:
        result = [e for e in result if topic in e.get("topic", "")]
    if tags:
        tag_set = set(tags)
        result = [e for e in result if tag_set & set(e.get("tags", []))]
    if importance_min is not None:
        result = [e for e in result if e.get("importance", 0) >= importance_min]
    if message_type:
        result = [e for e in result if e.get("message_type") == message_type]
    return result


class TestDataLoader:
    """测试数据加载与过滤工具。"""

    def __init__(self, data_dir: Path | str | None = None):
        base = Path(data_dir) if data_dir else DATA_DIR
        self._knowledge_dir = base / "knowledge"
        self._memory_dir = base / "memory"

    def passive_knowledge(self, **filters: Any) -> list[dict[str, Any]]:
        """加载被动 Agent 知识库，可按 topic/tags/importance_min/message_type 过滤。"""
        entries = _load_json(self._knowledge_dir / "passive_agent_knowledge.json")
        return _filter_entries(entries, **filters) if filters else entries

    def active_knowledge(self, **filters: Any) -> list[dict[str, Any]]:
        """加载主动 Agent 知识库，可按 topic/tags/importance_min/message_type 过滤。"""
        entries = _load_json(self._knowledge_dir / "active_agent_knowledge.json")
        return _filter_entries(entries, **filters) if filters else entries

    def passive_memories(self, **filters: Any) -> list[dict[str, Any]]:
        """加载被动 Agent 记忆条目（字典格式），可过滤。"""
        entries = _load_json(self._memory_dir / "passive_agent_memories.json")
        return _filter_entries(entries, **filters) if filters else entries

    def active_memories(self, **filters: Any) -> list[dict[str, Any]]:
        """加载主动 Agent 记忆条目（字典格式），可过滤。"""
        entries = _load_json(self._memory_dir / "active_agent_memories.json")
        return _filter_entries(entries, **filters) if filters else entries

    def passive_memories_as_entries(self) -> list[Any]:
        """加载被动 Agent 记忆并转为 MemoryEntry 对象。

        需要 long-memory 模块可导入。
        """
        from long_memory.models import MemoryEntry
        return [MemoryEntry.from_dict(d) for d in self.passive_memories()]

    def active_memories_as_entries(self) -> list[Any]:
        """加载主动 Agent 记忆并转为 MemoryEntry 对象。

        需要 long-memory 模块可导入。
        """
        from long_memory.models import MemoryEntry
        return [MemoryEntry.from_dict(d) for d in self.active_memories()]

    def all_knowledge(self, **filters: Any) -> list[dict[str, Any]]:
        """加载全部知识（被动 + 主动），可过滤。"""
        return self.passive_knowledge(**filters) + self.active_knowledge(**filters)

    def all_memories(self, **filters: Any) -> list[dict[str, Any]]:
        """加载全部记忆（被动 + 主动），可过滤。"""
        return self.passive_memories(**filters) + self.active_memories(**filters)

    def stats(self) -> dict[str, Any]:
        """返回数据集统计信息。"""
        pk = self.passive_knowledge()
        ak = self.active_knowledge()
        pm = self.passive_memories()
        am = self.active_memories()
        return {
            "passive_knowledge_count": len(pk),
            "active_knowledge_count": len(ak),
            "passive_memory_count": len(pm),
            "active_memory_count": len(am),
            "total_entries": len(pk) + len(ak) + len(pm) + len(am),
            "knowledge_topics": sorted(
                {e.get("topic", "") for e in pk + ak} - {""}
            ),
            "memory_topics": sorted(
                {e.get("topic", "") for e in pm + am} - {""}
            ),
        }


if __name__ == "__main__":
    loader = TestDataLoader()
    s = loader.stats()
    print(f"=== 测试数据统计 ===")
    print(f"被动 Agent 知识: {s['passive_knowledge_count']} 条")
    print(f"主动 Agent 知识: {s['active_knowledge_count']} 条")
    print(f"被动 Agent 记忆: {s['passive_memory_count']} 条")
    print(f"主动 Agent 记忆: {s['active_memory_count']} 条")
    print(f"总计: {s['total_entries']} 条")
    print(f"\n知识主题: {', '.join(s['knowledge_topics'])}")
    print(f"记忆主题: {', '.join(s['memory_topics'])}")

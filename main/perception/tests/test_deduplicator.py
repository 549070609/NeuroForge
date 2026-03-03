"""
单元测试 — PLUGIN.AlertDeduplicator
"""

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 在导入 PLUGIN 之前注入最小化的 pyagentforge 桩，避免依赖未安装的包
# ---------------------------------------------------------------------------
def _make_stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    return mod


for _mod in [
    "pyagentforge",
    "pyagentforge.plugin",
    "pyagentforge.plugin.base",
    "pyagentforge.kernel",
    "pyagentforge.kernel.base_tool",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _make_stub(_mod)

# 为 Plugin / PluginMetadata / PluginType / BaseTool 注入可继承的占位类
_base_mod = sys.modules["pyagentforge.plugin.base"]
_base_mod.Plugin = type("Plugin", (), {"__init__": lambda s, *a, **kw: None})  # type: ignore[attr-defined]
_base_mod.PluginMetadata = MagicMock  # type: ignore[attr-defined]
_base_mod.PluginType = MagicMock()   # type: ignore[attr-defined]
_tool_mod = sys.modules["pyagentforge.kernel.base_tool"]
_tool_mod.BaseTool = type("BaseTool", (), {"__init__": lambda s, *a, **kw: None})  # type: ignore[attr-defined]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PLUGIN import AlertDeduplicator  # noqa: E402


class TestAlertDeduplicatorBasic:

    def test_first_occurrence_allowed(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        assert d.should_alert("error", "DB down") is True

    def test_second_occurrence_in_cooldown_suppressed(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        d.should_alert("error", "DB down")
        assert d.should_alert("error", "DB down") is False

    def test_different_message_not_suppressed(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        d.should_alert("error", "DB down")
        assert d.should_alert("error", "OOM killed") is True

    def test_different_level_same_message_not_suppressed(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        d.should_alert("warn", "High CPU")
        assert d.should_alert("error", "High CPU") is True

    def test_cooldown_expired_resets(self):
        d = AlertDeduplicator(cooldown_seconds=1)
        d.should_alert("error", "DB down")
        time.sleep(1.1)
        assert d.should_alert("error", "DB down") is True

    def test_count_increments_on_suppressed(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        d.should_alert("error", "DB down")
        d.should_alert("error", "DB down")
        d.should_alert("error", "DB down")
        fp = d._fingerprint("error", "DB down")
        assert d._cache[fp].count == 3

    def test_after_cooldown_count_resets_to_one(self):
        d = AlertDeduplicator(cooldown_seconds=1)
        d.should_alert("error", "DB down")
        d.should_alert("error", "DB down")  # suppressed, count=2
        time.sleep(1.1)
        d.should_alert("error", "DB down")  # 冷却过后重置，count=1
        fp = d._fingerprint("error", "DB down")
        assert d._cache[fp].count == 1


class TestAlertDeduplicatorFilterEvents:

    def test_filter_events_splits_correctly(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        events = [
            {"level": "error",   "message": "DB down"},
            {"level": "error",   "message": "DB down"},   # 重复
            {"level": "warn",    "message": "High CPU"},
        ]
        to_alert, suppressed = d.filter_events(events)
        assert len(to_alert)   == 2   # DB down(首次) + High CPU
        assert len(suppressed) == 1   # DB down(重复)

    def test_filter_events_empty_list(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        to_alert, suppressed = d.filter_events([])
        assert to_alert   == []
        assert suppressed == []

    def test_filter_events_uses_normalized_level(self):
        """_level_normalized 字段被正确识别"""
        d = AlertDeduplicator(cooldown_seconds=60)
        events = [
            {"_level_normalized": "error", "message": "crash"},
            {"_level_normalized": "error", "message": "crash"},
        ]
        to_alert, suppressed = d.filter_events(events)
        assert len(to_alert)   == 1
        assert len(suppressed) == 1

    def test_filter_events_severity_field(self):
        """severity 字段被正确识别"""
        d = AlertDeduplicator(cooldown_seconds=60)
        events = [
            {"severity": "warn", "message": "mem high"},
            {"severity": "warn", "message": "mem high"},
        ]
        to_alert, suppressed = d.filter_events(events)
        assert len(to_alert)   == 1
        assert len(suppressed) == 1

    def test_filter_events_unknown_level_fallback(self):
        """无 level/severity 字段时 fallback 为 unknown，同样参与去重"""
        d = AlertDeduplicator(cooldown_seconds=60)
        events = [
            {"message": "mystery"},
            {"message": "mystery"},
        ]
        to_alert, suppressed = d.filter_events(events)
        assert len(to_alert)   == 1
        assert len(suppressed) == 1


class TestAlertDeduplicatorCacheEviction:

    def test_max_cache_size_evicts_lru(self):
        d = AlertDeduplicator(cooldown_seconds=60, max_cache_size=3)
        d.should_alert("error", "msg1")
        d.should_alert("error", "msg2")
        d.should_alert("error", "msg3")
        d.should_alert("error", "msg4")   # 触发淘汰
        assert len(d._cache) == 3

    def test_evict_oldest_by_last_seen(self):
        """last_seen 最早的条目被淘汰"""
        d = AlertDeduplicator(cooldown_seconds=60, max_cache_size=2)
        d.should_alert("error", "oldest")
        time.sleep(0.05)
        d.should_alert("error", "newer")
        time.sleep(0.05)
        # 更新 newest 的 last_seen
        d.should_alert("error", "newer")  # suppressed, last_seen updated
        # 触发淘汰：oldest 应被移除
        d.should_alert("error", "brand_new")
        assert len(d._cache) == 2
        fp_oldest = d._fingerprint("error", "oldest")
        assert fp_oldest not in d._cache


class TestAlertDeduplicatorStats:

    def test_stats_returns_correct_counts(self):
        d = AlertDeduplicator(cooldown_seconds=60)
        d.should_alert("error", "msg1")
        d.should_alert("warn",  "msg2")
        stats = d.stats()
        assert stats["cache_size"]    == 2
        assert stats["active_alerts"] == 2
        assert stats["cooldown_s"]    == 60

    def test_stats_active_excludes_expired(self):
        d = AlertDeduplicator(cooldown_seconds=1)
        d.should_alert("error", "msg1")
        time.sleep(1.1)
        stats = d.stats()
        assert stats["active_alerts"] == 0
        assert stats["cache_size"]    == 1  # 条目仍在缓存，只是不再 active


class TestAlertDeduplicatorFingerprint:

    def test_fingerprint_same_input_stable(self):
        fp1 = AlertDeduplicator._fingerprint("error", "DB down")
        fp2 = AlertDeduplicator._fingerprint("error", "DB down")
        assert fp1 == fp2

    def test_fingerprint_case_insensitive_level(self):
        fp1 = AlertDeduplicator._fingerprint("ERROR", "DB down")
        fp2 = AlertDeduplicator._fingerprint("error", "DB down")
        assert fp1 == fp2

    def test_fingerprint_truncates_message_at_100_chars(self):
        msg_short  = "x" * 100
        msg_long   = "x" * 200
        fp1 = AlertDeduplicator._fingerprint("error", msg_short)
        fp2 = AlertDeduplicator._fingerprint("error", msg_long)
        assert fp1 == fp2

    def test_fingerprint_different_messages_differ(self):
        fp1 = AlertDeduplicator._fingerprint("error", "DB down")
        fp2 = AlertDeduplicator._fingerprint("error", "OOM killed")
        assert fp1 != fp2

    def test_fingerprint_length_is_16(self):
        fp = AlertDeduplicator._fingerprint("warn", "high mem")
        assert len(fp) == 16

"""
单元测试 — perception.perceive
"""

import pytest

from pyagentforge.plugins.integration.perception.perception import (
    DecisionType,
    PerceptionResult,
    perceive,
)


# ---------------------------------------------------------------------------
# 基础决策路径
# ---------------------------------------------------------------------------

class TestPerceiveErrorLevel:
    def test_error_triggers_find_user_by_default(self):
        data = {"events": [{"level": "error", "message": "DB timeout"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_error_triggers_execute(self):
        data = {"events": [{"level": "error", "message": "crash"}]}
        result = perceive(data, {"error_triggers": "execute", "levels": ["error"]})
        assert result.decision == DecisionType.EXECUTE

    def test_error_triggers_call_agent(self):
        data = {"events": [{"level": "error", "message": "crash"}]}
        result = perceive(data, {"error_triggers": "call_agent", "levels": ["error"]})
        assert result.decision == DecisionType.CALL_AGENT

    def test_reason_contains_message(self):
        data = {"events": [{"level": "error", "message": "Connection refused"}]}
        result = perceive(data)
        assert "Connection refused" in result.reason

    def test_metadata_rule_is_error_triggers(self):
        data = {"events": [{"level": "error"}]}
        result = perceive(data)
        assert result.metadata is not None
        assert result.metadata["rule"] == "error_triggers"


class TestPerceiveWarnLevel:
    def test_warn_triggers_find_user_by_default(self):
        data = {"events": [{"level": "warn", "message": "High memory"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_warning_alias(self):
        data = {"events": [{"level": "warning", "message": "Disk full"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_warn_triggers_execute(self):
        data = {"events": [{"level": "warn"}]}
        result = perceive(data, {"warn_triggers": "execute", "levels": ["warn"]})
        assert result.decision == DecisionType.EXECUTE


class TestPerceiveCriticalFatal:
    """critical / fatal / crit 应当使用 error_triggers（修复 C-3 后新增）"""

    def test_critical_uses_error_triggers(self):
        data = {"events": [{"level": "critical", "message": "System crash"}]}
        result = perceive(data, {"error_triggers": "find_user", "levels": ["critical"]})
        assert result.decision == DecisionType.FIND_USER
        assert result.metadata["rule"] == "error_triggers"

    def test_fatal_uses_error_triggers(self):
        data = {"events": [{"level": "fatal"}]}
        result = perceive(data, {"levels": ["fatal"]})
        assert result.decision == DecisionType.FIND_USER

    def test_crit_uses_error_triggers(self):
        data = {"events": [{"level": "crit"}]}
        result = perceive(data, {"levels": ["crit"]})
        assert result.decision == DecisionType.FIND_USER


# ---------------------------------------------------------------------------
# levels 白名单过滤（修复 C-3 后行为）
# ---------------------------------------------------------------------------

class TestPerceiveLevelsFilter:
    def test_error_skipped_when_not_in_levels(self):
        data = {"events": [{"level": "error", "message": "crash"}]}
        result = perceive(data, {"levels": ["warn"]})
        assert result.decision == DecisionType.NONE

    def test_warn_skipped_when_not_in_levels(self):
        data = {"events": [{"level": "warn"}]}
        result = perceive(data, {"levels": ["error"]})
        assert result.decision == DecisionType.NONE

    def test_levels_case_insensitive(self):
        data = {"events": [{"level": "ERROR"}]}
        result = perceive(data, {"levels": ["error"]})
        assert result.decision == DecisionType.FIND_USER

    def test_info_not_in_default_levels(self):
        data = {"events": [{"level": "info", "message": "Normal operation"}]}
        result = perceive(data)
        assert result.decision == DecisionType.NONE

    def test_debug_not_in_default_levels(self):
        data = {"events": [{"level": "debug"}]}
        result = perceive(data)
        assert result.decision == DecisionType.NONE


# ---------------------------------------------------------------------------
# 数据提取多样性
# ---------------------------------------------------------------------------

class TestPerceiveDataExtraction:
    def test_list_data_direct(self):
        data = [{"level": "error", "message": "fail"}]
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_logs_key(self):
        data = {"logs": [{"level": "error"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_records_key(self):
        data = {"records": [{"level": "warn"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_empty_events_returns_none(self):
        result = perceive({"events": []})
        assert result.decision == DecisionType.NONE
        assert result.data["events_count"] == 0

    def test_empty_dict_returns_none(self):
        result = perceive({})
        assert result.decision == DecisionType.NONE

    def test_non_dict_event_skipped(self):
        data = {"events": ["not a dict", 42, {"level": "error"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_severity_field_alias(self):
        data = {"events": [{"severity": "error", "message": "fail"}]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER

    def test_first_matching_event_wins(self):
        data = {"events": [
            {"level": "info", "message": "ok"},
            {"level": "error", "message": "crash"},
            {"level": "warn", "message": "alert"},
        ]}
        result = perceive(data)
        assert result.decision == DecisionType.FIND_USER
        assert "crash" in result.reason


# ---------------------------------------------------------------------------
# 聚合模式（aggregate=True）
# ---------------------------------------------------------------------------

class TestPerceiveAggregate:

    def test_aggregate_collects_all_triggered(self):
        data = {"events": [
            {"level": "error", "message": "DB down"},
            {"level": "warn",  "message": "High CPU"},
            {"level": "error", "message": "OOM"},
        ]}
        result = perceive(data, aggregate=True)
        assert result.decision == DecisionType.FIND_USER
        assert result.triggered_events is not None
        assert len(result.triggered_events) == 3

    def test_aggregate_highest_severity_wins(self):
        data = {"events": [
            {"level": "warn",  "message": "Disk space low"},
            {"level": "error", "message": "Service crash"},
        ]}
        result = perceive(data, aggregate=True)
        assert result.data["highest_severity"] == "error"

    def test_aggregate_data_contains_counts(self):
        data = {"events": [
            {"level": "error", "message": "e1"},
            {"level": "error", "message": "e2"},
            {"level": "warn",  "message": "w1"},
        ]}
        result = perceive(data, aggregate=True)
        assert result.data["error_count"] == 2
        assert result.data["warn_count"] == 1
        assert result.data["triggered_count"] == 3

    def test_aggregate_empty_returns_none_with_empty_list(self):
        result = perceive({"events": []}, aggregate=True)
        assert result.decision == DecisionType.NONE
        assert result.triggered_events == []

    def test_aggregate_false_preserves_original_behavior(self):
        """aggregate=False 完全等同于原行为：triggered_events=None，只返回首条"""
        data = {"events": [
            {"level": "error", "message": "first"},
            {"level": "error", "message": "second"},
        ]}
        result = perceive(data, aggregate=False)
        assert result.triggered_events is None
        assert "first" in result.reason

    def test_aggregate_max_events_respected(self):
        data = {"events": [{"level": "error", "message": f"e{i}"} for i in range(100)]}
        result = perceive(data, {"max_events": 10}, aggregate=True)
        assert result.triggered_events is not None
        assert len(result.triggered_events) <= 10

    def test_aggregate_reason_format(self):
        data = {"events": [
            {"level": "error", "message": "DB down"},
            {"level": "warn",  "message": "High CPU"},
        ]}
        result = perceive(data, aggregate=True)
        assert "Aggregated" in result.reason
        assert "error" in result.reason

    def test_aggregate_warn_only_uses_warn_triggers(self):
        data = {"events": [
            {"level": "warn", "message": "w1"},
            {"level": "warn", "message": "w2"},
        ]}
        result = perceive(data, {"warn_triggers": "execute"}, aggregate=True)
        assert result.decision == DecisionType.EXECUTE
        assert result.data["highest_severity"] == "warn"

    def test_aggregate_metadata_contains_aggregate_flag(self):
        data = {"events": [{"level": "error", "message": "boom"}]}
        result = perceive(data, aggregate=True)
        assert result.metadata is not None
        assert result.metadata.get("aggregate") is True

    def test_aggregate_info_level_not_triggered(self):
        """info 不在默认 levels 白名单内，聚合模式下同样不触发"""
        data = {"events": [
            {"level": "info", "message": "normal"},
            {"level": "debug", "message": "verbose"},
        ]}
        result = perceive(data, aggregate=True)
        assert result.decision == DecisionType.NONE
        assert result.triggered_events == []

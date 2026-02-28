"""
单元测试 — perception.perceive
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from perception import perceive, DecisionType, PerceptionResult


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

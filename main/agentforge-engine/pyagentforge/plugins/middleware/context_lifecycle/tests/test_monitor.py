"""
Tests for Context Lifecycle Plugin
"""


from pyagentforge.plugins.middleware.context_lifecycle.context_monitor import ContextMonitor
from pyagentforge.plugins.middleware.context_lifecycle.context_usage import (
    CompactionStrategyType,
    ContextUsage,
)


class TestContextUsage:
    """Tests for ContextUsage dataclass"""

    def test_create_context_usage(self):
        """Test creating ContextUsage instance"""
        usage = ContextUsage(
            total_tokens=50000,
            max_tokens=200000,
            message_count=10,
            loaded_skills=2,
        )

        assert usage.total_tokens == 50000
        assert usage.max_tokens == 200000
        assert usage.usage_percentage == 25.0
        assert not usage.is_high_usage
        assert not usage.is_critical_usage

    def test_high_usage_detection(self):
        """Test high usage detection"""
        usage = ContextUsage(
            total_tokens=170000,
            max_tokens=200000,
            message_count=50,
        )

        assert usage.usage_percentage == 85.0
        assert usage.is_high_usage
        assert not usage.is_critical_usage

    def test_critical_usage_detection(self):
        """Test critical usage detection"""
        usage = ContextUsage(
            total_tokens=195000,
            max_tokens=200000,
            message_count=80,
        )

        assert usage.usage_percentage == 97.5
        assert usage.is_high_usage
        assert usage.is_critical_usage

    def test_available_tokens(self):
        """Test available tokens calculation"""
        usage = ContextUsage(
            total_tokens=100000,
            max_tokens=200000,
        )

        assert usage.available_tokens == 100000

    def test_utilization_level(self):
        """Test utilization level classification"""
        levels = [
            (25, "low"),
            (50, "medium"),
            (60, "medium"),
            (85, "high"),
            (97, "critical"),
        ]

        for percentage, expected_level in levels:
            usage = ContextUsage(
                total_tokens=int(200000 * percentage / 100),
                max_tokens=200000,
            )
            assert usage.utilization_level == expected_level

    def test_to_dict(self):
        """Test serialization to dict"""
        usage = ContextUsage(
            total_tokens=100000,
            max_tokens=200000,
            message_count=20,
            loaded_skills=3,
        )

        data = usage.to_dict()

        assert data["total_tokens"] == 100000
        assert data["max_tokens"] == 200000
        assert data["usage_percentage"] == 50.0
        assert data["message_count"] == 20
        assert data["loaded_skills"] == 3
        assert "timestamp" in data

    def test_format_report(self):
        """Test report formatting"""
        usage = ContextUsage(
            total_tokens=100000,
            max_tokens=200000,
            message_count=20,
            loaded_skills=3,
        )

        report = usage.format_report()

        assert "100,000" in report
        assert "200,000" in report
        assert "50.0%" in report
        assert "MEDIUM" in report

    def test_create_empty(self):
        """Test creating empty usage"""
        usage = ContextUsage.create_empty(max_tokens=100000)

        assert usage.total_tokens == 0
        assert usage.max_tokens == 100000
        assert usage.usage_percentage == 0.0


class TestContextMonitor:
    """Tests for ContextMonitor"""

    def test_count_tokens_english(self):
        """Test token counting for English text"""
        monitor = ContextMonitor()

        # Simple English text
        text = "Hello, this is a test."
        tokens = monitor.count_tokens(text)

        # Should use estimation (chars / 4)
        assert tokens > 0
        assert tokens < len(text)  # Should be less than char count

    def test_count_tokens_empty(self):
        """Test token counting for empty text"""
        monitor = ContextMonitor()

        assert monitor.count_tokens("") == 0
        assert monitor.count_tokens(None) == 0

    def test_count_tokens_chinese(self):
        """Test token counting for Chinese text"""
        monitor = ContextMonitor()

        text = "你好，这是一个测试"
        tokens = monitor.count_tokens(text)

        assert tokens > 0

    def test_calculate_usage_empty(self):
        """Test usage calculation with no messages"""
        monitor = ContextMonitor()

        usage = monitor.calculate_usage([])

        assert usage.total_tokens == 0
        assert usage.message_count == 0

    def test_should_compact_below_threshold(self):
        """Test compaction check below threshold"""
        monitor = ContextMonitor()

        # Create mock messages with low token count
        messages = []

        assert not monitor.should_compact(messages, threshold=0.8)

    def test_get_compaction_recommendation(self):
        """Test compaction recommendation"""
        monitor = ContextMonitor()

        # Empty messages
        rec = monitor.get_compaction_recommendation([])

        assert "needs_compaction" in rec
        assert "urgency" in rec
        assert "suggested_strategy" in rec
        assert "message" in rec


class TestCompactionStrategyType:
    """Tests for CompactionStrategyType enum"""

    def test_strategy_values(self):
        """Test strategy enum values"""
        assert CompactionStrategyType.DEDUPLICATE.value == "deduplicate"
        assert CompactionStrategyType.TRUNCATE.value == "truncate"
        assert CompactionStrategyType.SUMMARIZE.value == "summarize"
        assert CompactionStrategyType.HYBRID.value == "hybrid"

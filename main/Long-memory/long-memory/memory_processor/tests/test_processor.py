"""
记忆加工插件测试
"""

import pytest
from unittest.mock import AsyncMock
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory_processor.config import ProcessorConfig, DEFAULT_TAG_POOL
from memory_processor.llm_analyzer import LLMAnalyzer, AnalysisResult
from memory_processor.processor_engine import ProcessorEngine, ProcessResult


class TestProcessorConfig:
    """测试配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = ProcessorConfig()
        assert config.enabled is True
        assert config.auto_trigger is True
        assert config.max_summary_length == 200
        assert config.max_topic_length == 50
        assert config.max_tags == 5
        assert config.fallback_to_rules is True

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "enabled": False,
            "auto_trigger": False,
            "max_summary_length": 100,
            "max_tags": 3,
        }
        config = ProcessorConfig.from_dict(data)
        assert config.enabled is False
        assert config.auto_trigger is False
        assert config.max_summary_length == 100
        assert config.max_tags == 3

    def test_from_dict_none(self):
        """测试从 None 创建"""
        config = ProcessorConfig.from_dict(None)
        assert config.enabled is True

    def test_flat_tag_pool(self):
        """测试展平标签池"""
        config = ProcessorConfig()
        flat = config.flat_tag_pool
        assert isinstance(flat, list)
        assert "工作" in flat
        assert "代码" in flat

    def test_validate(self):
        """测试配置验证"""
        config = ProcessorConfig(max_summary_length=5)
        errors = config.validate()
        assert len(errors) > 0
        assert any("max_summary_length" in e for e in errors)

        config = ProcessorConfig()
        errors = config.validate()
        assert len(errors) == 0


class TestLLMAnalyzer:
    """测试 LLM 分析器"""

    def test_init(self):
        """测试初始化"""
        analyzer = LLMAnalyzer(
            tag_pool=["工作", "代码", "学习"],
            max_summary_length=100,
        )
        assert analyzer._tag_pool == ["工作", "代码", "学习"]
        assert analyzer._max_summary_length == 100

    def test_rule_based_analyze_work(self):
        """测试规则分析 - 工作相关"""
        analyzer = LLMAnalyzer(
            tag_pool=["工作", "项目", "任务", "代码", "学习"],
            fallback_to_rules=True,
        )

        result = analyzer._rule_based_analyze("这是一个关于项目进度的工作任务")

        assert "工作" in result.tags or "项目" in result.tags or "任务" in result.tags
        assert result.method == "rule"
        assert result.confidence > 0

    def test_rule_based_analyze_code(self):
        """测试规则分析 - 代码相关"""
        analyzer = LLMAnalyzer(
            tag_pool=["代码", "技术", "Bug", "功能"],
            fallback_to_rules=True,
        )

        result = analyzer._rule_based_analyze("修复了一个严重的 Bug，涉及代码重构")

        assert "Bug" in result.tags or "代码" in result.tags
        assert result.method == "rule"

    def test_rule_based_analyze_learning(self):
        """测试规则分析 - 学习相关"""
        analyzer = LLMAnalyzer(
            tag_pool=["学习", "笔记", "教程", "文档"],
            fallback_to_rules=True,
        )

        result = analyzer._rule_based_analyze("今天学习了 Python 教程，做了一些笔记")

        assert "学习" in result.tags or "笔记" in result.tags or "教程" in result.tags

    def test_extract_topic(self):
        """测试主题提取"""
        analyzer = LLMAnalyzer()

        # 测试正常内容
        topic = analyzer._extract_topic("这是一个关于项目配置的记录")
        assert len(topic) > 0

        # 测试短内容
        topic = analyzer._extract_topic("短")
        assert topic == "短"

    def test_extract_summary(self):
        """测试摘要提取"""
        analyzer = LLMAnalyzer(max_summary_length=100)

        content = "这是第一句话。这是第二句话。这是第三句话。"
        summary = analyzer._extract_summary(content)

        assert len(summary) > 0
        assert "。" in summary

    def test_empty_content(self):
        """测试空内容"""
        analyzer = LLMAnalyzer()

        result = analyzer._rule_based_analyze("")
        assert result.tags == []
        assert result.topic == ""
        assert result.summary == ""

    @pytest.mark.asyncio
    async def test_analyze_fallback(self):
        """测试分析回退到规则"""
        analyzer = LLMAnalyzer(
            llm_client=None,  # 没有 LLM 客户端
            tag_pool=["工作", "代码"],
            fallback_to_rules=True,
        )

        result = await analyzer.analyze("这是一个工作任务")

        assert result.method == "rule"


class TestAnalysisResult:
    """测试分析结果"""

    def test_to_dict(self):
        """测试转换为字典"""
        result = AnalysisResult(
            tags=["工作", "项目"],
            topic="项目进度",
            summary="这是一个关于项目进度的记录",
            confidence=0.8,
            method="llm",
        )

        d = result.to_dict()
        assert d["tags"] == ["工作", "项目"]
        assert d["topic"] == "项目进度"
        assert d["confidence"] == 0.8
        assert d["method"] == "llm"

    def test_empty(self):
        """测试空结果"""
        result = AnalysisResult.empty()
        assert result.tags == []
        assert result.topic == ""
        assert result.confidence == 0.0
        assert result.method == "none"


class TestProcessResult:
    """测试加工结果"""

    def test_to_dict_success(self):
        """测试成功结果转换"""
        from models import MemoryEntry

        original = MemoryEntry(
            id="mem_test123",
            content="测试内容",
            topic="",
            tags=[],
            summary="",
        )

        updated = MemoryEntry(
            id="mem_test123",
            content="测试内容",
            topic="测试主题",
            tags=["测试"],
            summary="测试摘要",
        )

        result = ProcessResult(
            memory_id="mem_test123",
            success=True,
            analysis=AnalysisResult(
                tags=["测试"],
                topic="测试主题",
                summary="测试摘要",
                confidence=0.8,
                method="rule",
            ),
            original_entry=original,
            updated_entry=updated,
        )

        d = result.to_dict()
        assert d["success"] is True
        assert d["memory_id"] == "mem_test123"
        assert d["analysis"]["tags"] == ["测试"]
        assert d["updated"]["topic"] == "测试主题"


class TestProcessorEngine:
    """测试加工引擎"""

    @pytest.fixture
    def mock_store(self):
        """创建模拟存储"""
        store = AsyncMock()
        store.update = AsyncMock(return_value=True)
        store.get_by_id = AsyncMock(return_value=None)
        store.list_memories = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return ProcessorConfig(
            enabled=True,
            fallback_to_rules=True,
            tag_pool=DEFAULT_TAG_POOL,
        )

    @pytest.fixture
    def engine(self, mock_store, config):
        """创建测试引擎"""
        return ProcessorEngine(
            vector_store=mock_store,
            config=config,
            llm_client=None,
        )

    @pytest.mark.asyncio
    async def test_process_memory(self, engine, mock_store):
        """测试单条记忆加工"""
        from models import MemoryEntry

        entry = MemoryEntry(
            id="mem_test",
            content="这是一个关于项目代码的工作任务",
            topic="",
            tags=[],
            summary="",
        )

        result = await engine.process_memory(entry)

        assert result.success is True
        assert result.analysis is not None
        assert len(result.analysis.tags) > 0 or result.analysis.topic != ""
        mock_store.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_by_id_not_found(self, engine, mock_store):
        """测试不存在的记忆"""
        mock_store.get_by_id = AsyncMock(return_value=None)

        result = await engine.process_by_id("mem_nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_reprocess_unprocessed(self, engine, mock_store):
        """测试批量重加工"""
        from models import MemoryEntry

        entries = [
            MemoryEntry(id=f"mem_{i}", content=f"测试内容 {i}", topic="", tags=[], summary="")
            for i in range(3)
        ]
        mock_store.list_memories = AsyncMock(return_value=entries)

        results = await engine.reprocess_unprocessed(limit=3)

        assert len(results) == 3
        assert all(r.success for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

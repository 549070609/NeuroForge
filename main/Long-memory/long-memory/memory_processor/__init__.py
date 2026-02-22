"""
记忆加工插件

在记忆存入后自动整理：
- 标签 (tags): 从预定义标签池选择
- 主题 (topic): 简短描述
- 摘要 (summary): 1-2 句话概括
"""

from .config import ProcessorConfig, DEFAULT_TAG_POOL
from .llm_analyzer import LLMAnalyzer, AnalysisResult
from .processor_engine import ProcessorEngine, ProcessResult

__all__ = [
    "ProcessorConfig",
    "DEFAULT_TAG_POOL",
    "LLMAnalyzer",
    "AnalysisResult",
    "ProcessorEngine",
    "ProcessResult",
]

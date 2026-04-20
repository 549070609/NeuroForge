"""
上下文使用情况追踪

用于监控和报告上下文使用情况的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CompactionStrategyType(StrEnum):
    """压缩策略类型"""

    DEDUPLICATE = "deduplicate"  # 去除重复内容
    TRUNCATE = "truncate"  # 截断旧消息
    SUMMARIZE = "summarize"  # 生成摘要
    HYBRID = "hybrid"  # 混合策略


@dataclass
class ContextUsage:
    """上下文使用情况"""

    total_tokens: int = 0
    max_tokens: int = 200000
    usage_percentage: float = 0.0
    message_count: int = 0
    loaded_skills: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 分项统计
    user_messages_tokens: int = 0
    assistant_messages_tokens: int = 0
    tool_results_tokens: int = 0

    def __post_init__(self):
        """初始化后计算使用率"""
        if self.max_tokens > 0:
            self.usage_percentage = (self.total_tokens / self.max_tokens) * 100

    @property
    def is_high_usage(self) -> bool:
        """是否高使用率（超过80%）"""
        return self.usage_percentage >= 80.0

    @property
    def is_critical_usage(self) -> bool:
        """是否危险使用率（超过95%）"""
        return self.usage_percentage >= 95.0

    @property
    def available_tokens(self) -> int:
        """剩余可用 tokens"""
        return max(0, self.max_tokens - self.total_tokens)

    @property
    def utilization_level(self) -> str:
        """获取使用级别描述"""
        if self.usage_percentage < 50:
            return "low"
        elif self.usage_percentage < 80:
            return "medium"
        elif self.usage_percentage < 95:
            return "high"
        else:
            return "critical"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "usage_percentage": round(self.usage_percentage, 2),
            "message_count": self.message_count,
            "loaded_skills": self.loaded_skills,
            "timestamp": self.timestamp,
            "user_messages_tokens": self.user_messages_tokens,
            "assistant_messages_tokens": self.assistant_messages_tokens,
            "tool_results_tokens": self.tool_results_tokens,
            "is_high_usage": self.is_high_usage,
            "is_critical_usage": self.is_critical_usage,
            "available_tokens": self.available_tokens,
            "utilization_level": self.utilization_level,
        }

    def format_report(self) -> str:
        """格式化使用报告"""
        return f"""Context Usage Report:
- Total Tokens: {self.total_tokens:,} / {self.max_tokens:,} ({self.usage_percentage:.1f}%)
- Available Tokens: {self.available_tokens:,}
- Messages: {self.message_count}
- Loaded Skills: {self.loaded_skills}
- Utilization Level: {self.utilization_level.upper()}
  - User Messages: {self.user_messages_tokens:,} tokens
  - Assistant Messages: {self.assistant_messages_tokens:,} tokens
  - Tool Results: {self.tool_results_tokens:,} tokens
"""

    @classmethod
    def create_empty(cls, max_tokens: int = 200000) -> "ContextUsage":
        """创建空的使用情况"""
        return cls(
            total_tokens=0,
            max_tokens=max_tokens,
            usage_percentage=0.0,
            message_count=0,
            loaded_skills=0,
        )

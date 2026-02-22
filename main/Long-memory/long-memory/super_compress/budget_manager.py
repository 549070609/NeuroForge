"""
Token 预算管理器

计算和管理上下文 token 预算
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TokenBudget:
    """Token 预算信息"""

    total_tokens: int
    used_tokens: int
    available_tokens: int
    message_count: int
    compression_ratio: float = 0.0  # 当前压缩比例


class TokenBudgetManager:
    """
    Token 预算管理器

    支持:
    - Token 计数估算
    - 压缩阈值判断
    - 预算分配
    """

    # 各模型的上下文限制
    CONTEXT_LIMITS = {
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-3-5-sonnet": 200000,
        "claude-3-5-haiku": 200000,
        "claude-sonnet-4-6": 200000,
        "claude-opus-4-6": 200000,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "default": 128000,
    }

    def __init__(
        self,
        model: str = "default",
        compress_threshold: float = 0.8,
        reserve_tokens: int = 8000,
    ):
        """
        初始化预算管理器

        Args:
            model: 模型名称
            compress_threshold: 压缩阈值 (0-1)
            reserve_tokens: 保留给输出的 token 数
        """
        self.model = model
        self.compress_threshold = compress_threshold
        self.reserve_tokens = reserve_tokens
        self.context_limit = self._get_context_limit(model)

    def _get_context_limit(self, model: str) -> int:
        """获取模型的上下文限制"""
        # 尝试精确匹配
        if model in self.CONTEXT_LIMITS:
            return self.CONTEXT_LIMITS[model]

        # 模糊匹配
        model_lower = model.lower()
        for key, limit in self.CONTEXT_LIMITS.items():
            if key in model_lower:
                return limit

        return self.CONTEXT_LIMITS["default"]

    def calculate(self, messages: list[dict[str, Any]]) -> TokenBudget:
        """
        计算当前 token 预算

        Args:
            messages: 消息列表

        Returns:
            Token 预算信息
        """
        used_tokens = self._estimate_tokens(messages)
        available_tokens = self.context_limit - used_tokens - self.reserve_tokens

        return TokenBudget(
            total_tokens=self.context_limit,
            used_tokens=used_tokens,
            available_tokens=max(0, available_tokens),
            message_count=len(messages),
            compression_ratio=used_tokens / self.context_limit if self.context_limit > 0 else 0,
        )

    def should_compress(
        self,
        messages: list[dict[str, Any]],
        threshold: Optional[float] = None,
    ) -> bool:
        """
        判断是否需要压缩

        Args:
            messages: 消息列表
            threshold: 可选的阈值覆盖

        Returns:
            是否需要压缩
        """
        budget = self.calculate(messages)
        threshold = threshold or self.compress_threshold
        return budget.compression_ratio >= threshold

    def get_compress_ratio(self, messages: list[dict[str, Any]]) -> float:
        """
        获取当前压缩比例

        Args:
            messages: 消息列表

        Returns:
            压缩比例 (0-1)
        """
        budget = self.calculate(messages)
        return budget.compression_ratio

    def estimate_compress_savings(
        self,
        message_count: int,
        target_ratio: float = 0.3,
    ) -> int:
        """
        估算压缩后可节省的 token 数

        Args:
            message_count: 要压缩的消息数量
            target_ratio: 目标压缩比例

        Returns:
            预计节省的 token 数
        """
        # 假设每条消息平均 200 tokens
        avg_tokens_per_message = 200
        original_tokens = message_count * avg_tokens_per_message
        compressed_tokens = int(original_tokens * target_ratio)
        return original_tokens - compressed_tokens

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        估算消息列表的 token 数

        Args:
            messages: 消息列表

        Returns:
            估算的 token 数
        """
        total = 0

        for msg in messages:
            # 基础消息结构开销
            total += 4  # 每条消息的基础开销

            # 角色字段
            role = msg.get("role", "")
            total += len(role) // 4 + 1

            # 内容
            content = msg.get("content", "")
            if isinstance(content, str):
                # 简单估算: 英文约 4 字符 = 1 token, 中文约 2 字符 = 1 token
                # 取折中: 3 字符 = 1 token
                total += len(content) // 3 + 1
            elif isinstance(content, list):
                # 多模态内容
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            total += len(text) // 3 + 1
                        elif block.get("type") == "image":
                            # 图片估算为 85-1105 tokens
                            total += 500
                        else:
                            total += 50

            # 工具调用
            tool_use = msg.get("tool_use") or msg.get("tool_calls")
            if tool_use:
                if isinstance(tool_use, list):
                    total += len(tool_use) * 50  # 每个工具调用约 50 tokens
                else:
                    total += 50

        return total

    def get_budget_status(self, messages: list[dict[str, Any]]) -> str:
        """
        获取预算状态描述

        Args:
            messages: 消息列表

        Returns:
            状态描述字符串
        """
        budget = self.calculate(messages)

        status_lines = [
            f"## Token 预算状态",
            f"",
            f"- **模型**: {self.model}",
            f"- **上下文限制**: {self.context_limit:,} tokens",
            f"- **已使用**: {budget.used_tokens:,} tokens ({budget.compression_ratio:.1%})",
            f"- **可用**: {budget.available_tokens:,} tokens",
            f"- **保留**: {self.reserve_tokens:,} tokens",
            f"- **消息数量**: {budget.message_count}",
            f"- **压缩阈值**: {self.compress_threshold:.0%}",
            f"- **需要压缩**: {'是' if self.should_compress(messages) else '否'}",
        ]

        return "\n".join(status_lines)

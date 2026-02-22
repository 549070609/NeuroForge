"""
摘要生成器

生成对话摘要，支持多种策略
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)


class SummaryStrategy(str, Enum):
    """摘要策略"""

    EXTRACT = "extract"  # 规则提取
    LLM = "llm"  # LLM 生成
    SMART = "smart"  # 智能选择


@dataclass
class SummaryResult:
    """摘要结果"""

    content: str
    strategy: SummaryStrategy
    original_tokens: int
    summary_tokens: int
    compression_ratio: float
    key_points: list[str]


class SummaryGenerator:
    """
    摘要生成器

    支持:
    - 规则提取 (最快)
    - LLM 生成 (最智能)
    - 智能选择 (平衡)
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        default_strategy: SummaryStrategy = SummaryStrategy.SMART,
        max_summary_tokens: int = 2000,
    ):
        """
        初始化摘要生成器

        Args:
            llm_client: LLM 客户端 (用于 LLM 策略)
            default_strategy: 默认策略
            max_summary_tokens: 摘要最大 token 数
        """
        self.llm_client = llm_client
        self.default_strategy = default_strategy
        self.max_summary_tokens = max_summary_tokens

    async def generate(
        self,
        messages: list[dict[str, Any]],
        strategy: Optional[SummaryStrategy] = None,
        context: Optional[str] = None,
    ) -> SummaryResult:
        """
        生成摘要

        Args:
            messages: 消息列表
            strategy: 策略 (None 使用默认)
            context: 额外上下文

        Returns:
            摘要结果
        """
        strategy = strategy or self.default_strategy

        if strategy == SummaryStrategy.EXTRACT:
            return await self._extract_summary(messages, context)
        elif strategy == SummaryStrategy.LLM:
            return await self._llm_summary(messages, context)
        else:  # SMART
            return await self._smart_summary(messages, context)

    async def _extract_summary(
        self,
        messages: list[dict[str, Any]],
        context: Optional[str] = None,
    ) -> SummaryResult:
        """
        规则提取摘要

        提取关键信息:
        - 用户的主要请求
        - 助手的关键决策
        - 工具调用和结果
        - 重要结论
        """
        original_tokens = self._estimate_tokens(messages)

        key_points = []
        user_requests = []
        assistant_decisions = []
        tool_calls = []
        conclusions = []

        for msg in messages:
            role = msg.get("role", "")
            content = self._get_text_content(msg)

            if role == "user":
                # 提取用户请求
                request = self._extract_main_point(content)
                if request:
                    user_requests.append(request)

            elif role == "assistant":
                # 提取决策和结论
                decision = self._extract_decision(content)
                if decision:
                    assistant_decisions.append(decision)

                # 提取结论
                conclusion = self._extract_conclusion(content)
                if conclusion:
                    conclusions.append(conclusion)

            # 提取工具调用
            tool_info = self._extract_tool_info(msg)
            if tool_info:
                tool_calls.append(tool_info)

        # 构建摘要
        summary_parts = []

        if context:
            summary_parts.append(f"**上下文**: {context}")

        if user_requests:
            summary_parts.append("**用户请求**:")
            for i, req in enumerate(user_requests[-5:], 1):  # 最多 5 条
                summary_parts.append(f"  {i}. {req}")

        if assistant_decisions:
            summary_parts.append("**关键决策**:")
            for i, dec in enumerate(assistant_decisions[-5:], 1):
                summary_parts.append(f"  {i}. {dec}")

        if tool_calls:
            summary_parts.append("**工具调用**:")
            for tc in tool_calls[-10:]:  # 最多 10 条
                summary_parts.append(f"  - {tc}")

        if conclusions:
            summary_parts.append("**结论**:")
            for i, conc in enumerate(conclusions[-3:], 1):
                summary_parts.append(f"  {i}. {conc}")

        # 组合关键点
        key_points = (
            user_requests[-3:]
            + assistant_decisions[-3:]
            + tool_calls[-5:]
        )

        content = "\n".join(summary_parts)
        summary_tokens = self._estimate_tokens([{"role": "user", "content": content}])

        return SummaryResult(
            content=content,
            strategy=SummaryStrategy.EXTRACT,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            compression_ratio=summary_tokens / original_tokens if original_tokens > 0 else 0,
            key_points=key_points,
        )

    async def _llm_summary(
        self,
        messages: list[dict[str, Any]],
        context: Optional[str] = None,
    ) -> SummaryResult:
        """
        LLM 生成摘要

        使用 LLM 生成高质量摘要
        """
        if self.llm_client is None:
            # 回退到规则提取
            logger.warning("No LLM client, falling back to extract strategy")
            return await self._extract_summary(messages, context)

        original_tokens = self._estimate_tokens(messages)

        # 构建对话历史
        conversation = self._format_conversation(messages)

        # 构建摘要提示
        prompt = f"""请总结以下对话的关键信息，包括:
1. 用户的主要请求和目标
2. 助手做出的关键决策
3. 重要的工具调用和结果
4. 最终的结论或状态

保持摘要简洁，突出重点。

{f'额外上下文: {context}' if context else ''}

## 对话历史

{conversation}

## 摘要

请生成简洁的摘要:"""

        try:
            # 调用 LLM
            response = await self._call_llm(prompt)
            summary_content = response.strip()

        except Exception as e:
            logger.error(f"LLM summary failed: {e}")
            # 回退到规则提取
            return await self._extract_summary(messages, context)

        # 提取关键点
        key_points = self._extract_key_points_from_summary(summary_content)

        summary_tokens = self._estimate_tokens([{"role": "user", "content": summary_content}])

        return SummaryResult(
            content=summary_content,
            strategy=SummaryStrategy.LLM,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            compression_ratio=summary_tokens / original_tokens if original_tokens > 0 else 0,
            key_points=key_points,
        )

    async def _smart_summary(
        self,
        messages: list[dict[str, Any]],
        context: Optional[str] = None,
    ) -> SummaryResult:
        """
        智能摘要

        根据消息数量和复杂度选择策略
        """
        msg_count = len(messages)

        # 少量消息: 直接提取
        if msg_count <= 10:
            return await self._extract_summary(messages, context)

        # 中等数量: 如果有 LLM，使用 LLM
        if msg_count <= 50 and self.llm_client:
            return await self._llm_summary(messages, context)

        # 大量消息: 提取关键部分
        # 只处理最近的消息
        recent_messages = messages[-30:]
        return await self._extract_summary(recent_messages, context)

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if hasattr(self.llm_client, "complete"):
            return await self.llm_client.complete(prompt)
        elif hasattr(self.llm_client, "chat"):
            response = await self.llm_client.chat([{"role": "user", "content": prompt}])
            return response
        else:
            raise ValueError("Invalid LLM client")

    def _get_text_content(self, msg: dict[str, Any]) -> str:
        """获取消息的文本内容"""
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return "\n".join(texts)
        return ""

    def _extract_main_point(self, text: str) -> Optional[str]:
        """提取主要内容点"""
        # 简单实现: 取第一句或前 100 字符
        sentences = text.split(". ")
        first = sentences[0] if sentences else text
        if len(first) > 150:
            return first[:150] + "..."
        return first if len(first) > 10 else None

    def _extract_decision(self, text: str) -> Optional[str]:
        """提取决策"""
        keywords = ["决定", "选择", "将", "需要", "decided", "chose", "will", "need to"]
        text_lower = text.lower()

        for kw in keywords:
            if kw in text_lower:
                # 找到包含关键词的句子
                sentences = text.split(". ")
                for sent in sentences:
                    if kw in sent.lower():
                        if len(sent) > 100:
                            return sent[:100] + "..."
                        return sent

        return None

    def _extract_conclusion(self, text: str) -> Optional[str]:
        """提取结论"""
        keywords = ["完成", "成功", "结果", "conclusion", "done", "success", "result"]
        text_lower = text.lower()

        for kw in keywords:
            if kw in text_lower:
                sentences = text.split(". ")
                for sent in sentences:
                    if kw in sent.lower() and len(sent) > 20:
                        return sent[:150] if len(sent) > 150 else sent

        return None

    def _extract_tool_info(self, msg: dict[str, Any]) -> Optional[str]:
        """提取工具调用信息"""
        tool_use = msg.get("tool_use") or msg.get("tool_calls")

        if tool_use:
            if isinstance(tool_use, list) and tool_use:
                name = tool_use[0].get("name", "unknown")
                return f"调用 {name}"
            elif isinstance(tool_use, dict):
                name = tool_use.get("name", "unknown")
                return f"调用 {name}"

        return None

    def _format_conversation(self, messages: list[dict[str, Any]]) -> str:
        """格式化对话历史"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = self._get_text_content(msg)
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"[{role}]: {content}")

        return "\n\n".join(lines)

    def _extract_key_points_from_summary(self, summary: str) -> list[str]:
        """从摘要中提取关键点"""
        # 简单实现: 按句子分割
        sentences = summary.split(". ")
        return [s.strip() for s in sentences[:5] if len(s.strip()) > 10]

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算 token 数"""
        total = 0
        for msg in messages:
            content = self._get_text_content(msg)
            # 简单估算: 3 字符 = 1 token
            total += len(content) // 3 + 4
        return total

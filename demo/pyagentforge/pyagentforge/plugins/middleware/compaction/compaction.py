"""
上下文压缩模块

当对话历史过长时，使用 LLM 或 Agent 生成摘要来压缩上下文
支持多种压缩策略和动态配置
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, Field

from pyagentforge.kernel.message import Message, TextBlock, ToolUseBlock
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.kernel.base_provider import BaseProvider
    from pyagentforge.kernel.engine import AgentEngine

logger = get_logger(__name__)


class CompactionStrategy(str, Enum):
    """压缩策略"""
    SIMPLE = "simple"  # 简单 LLM 摘要
    AGENT = "agent"    # Agent 智能压缩


class CompactionSettings(BaseModel):
    """压缩配置"""

    enabled: bool = True
    strategy: CompactionStrategy = CompactionStrategy.SIMPLE
    reserve_tokens: int = 8000  # 预留给新消息的 tokens
    keep_recent_tokens: int = 4000  # 保留最近消息的 tokens
    trigger_threshold: float = 0.8  # 触发压缩的阈值 (上下文使用率)
    max_context_tokens: int = 200000  # 最大上下文 tokens

    # Agent 压缩配置
    agent_summary_max_tokens: int = 2000  # Agent 摘要最大 tokens
    agent_analyze_recent: int = 5  # Agent 分析最近 N 条消息决定压缩策略

    class Config:
        use_enum_values = True


class DynamicCompactionConfig:
    """
    动态压缩配置

    支持运行时动态调整压缩参数，包括：
    - 自适应阈值：根据使用模式自动调整
    - 外部回调：允许外部系统控制压缩行为
    """

    def __init__(
        self,
        base_settings: CompactionSettings | None = None,
        on_threshold_change: Callable[[float], None] | None = None,
    ):
        self._settings = base_settings or CompactionSettings()
        self._on_threshold_change = on_threshold_change
        self._adaptive_enabled = False
        self._compaction_history: list[dict] = []

    @property
    def settings(self) -> CompactionSettings:
        return self._settings

    def update_threshold(self, new_threshold: float) -> None:
        """动态更新压缩阈值"""
        if 0.0 <= new_threshold <= 1.0:
            old = self._settings.trigger_threshold
            self._settings.trigger_threshold = new_threshold
            if self._on_threshold_change:
                self._on_threshold_change(new_threshold)
            logger.info(f"Compaction threshold updated: {old:.2f} -> {new_threshold:.2f}")

    def update_max_context_tokens(self, new_max: int) -> None:
        """动态更新最大上下文 tokens"""
        self._settings.max_context_tokens = new_max
        logger.info(f"Max context tokens updated: {new_max}")

    def update_strategy(self, strategy: CompactionStrategy) -> None:
        """动态更新压缩策略"""
        self._settings.strategy = strategy
        logger.info(f"Compaction strategy updated: {strategy.value}")

    def enable_adaptive(self, enabled: bool = True) -> None:
        """启用/禁用自适应压缩"""
        self._adaptive_enabled = enabled

    def record_compaction(self, result: "CompactionResult") -> None:
        """记录压缩历史，用于自适应调整"""
        self._compaction_history.append({
            "tokens_saved": result.tokens_saved,
            "messages_removed": result.removed_messages,
            "compression_ratio": result.tokens_saved / max(result.original_messages, 1),
        })

        if self._adaptive_enabled and len(self._compaction_history) >= 3:
            self._adjust_adaptive()

    def _adjust_adaptive(self) -> None:
        """根据历史记录自适应调整阈值"""
        recent = self._compaction_history[-3:]
        avg_ratio = sum(h["compression_ratio"] for h in recent) / len(recent)

        # 如果压缩率低，提高阈值（减少压缩频率）
        # 如果压缩率高，降低阈值（更积极压缩）
        if avg_ratio < 0.2:
            new_threshold = min(0.95, self._settings.trigger_threshold + 0.05)
        elif avg_ratio > 0.5:
            new_threshold = max(0.5, self._settings.trigger_threshold - 0.05)
        else:
            new_threshold = self._settings.trigger_threshold

        if new_threshold != self._settings.trigger_threshold:
            self.update_threshold(new_threshold)


@dataclass
class CompactionResult:
    """压缩结果"""

    original_messages: int
    compacted_messages: int
    removed_messages: int
    summary: str
    tokens_saved: int


@dataclass
class MessageSegment:
    """消息分段"""

    start_index: int
    end_index: int
    estimated_tokens: int
    messages: list[Message] = field(default_factory=list)


class Compactor:
    """上下文压缩器"""

    # 压缩提示词模板
    COMPACTION_PROMPT = """请对以下对话历史生成一个简洁但完整的摘要。

要求：
1. 保留所有重要的决策和结论
2. 保留工具调用的关键信息（工具名称、目的、结果）
3. 保留用户的明确要求
4. 丢弃闲聊和冗余内容
5. 使用中文或英文（与原文保持一致）

对话历史：
{conversation}

请生成摘要（不要添加任何额外说明）："""

    def __init__(
        self,
        provider: "BaseProvider",
        settings: CompactionSettings | None = None,
        max_context_tokens: int = 200000,
    ):
        """
        初始化压缩器

        Args:
            provider: LLM 提供商（用于生成摘要）
            settings: 压缩配置
            max_context_tokens: 最大上下文 tokens
        """
        self.provider = provider
        self.settings = settings or CompactionSettings()
        self.max_context_tokens = max_context_tokens

    def estimate_tokens(self, messages: list[Message]) -> int:
        """
        估算消息列表的 token 数量

        使用 chars/4 启发式估算
        """
        total = 0
        for msg in messages:
            if isinstance(msg.content, str):
                total += len(msg.content) // 4
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        total += len(block.text) // 4
                    elif isinstance(block, ToolUseBlock):
                        # 工具调用估算
                        total += len(block.name) // 4
                        total += len(str(block.input)) // 4
        return total

    def should_compact(
        self,
        messages: list[Message],
        current_tokens: int | None = None,
    ) -> bool:
        """
        判断是否需要压缩

        Args:
            messages: 消息列表
            current_tokens: 当前 token 数（如果已知）

        Returns:
            是否需要压缩
        """
        if not self.settings.enabled:
            return False

        if current_tokens is None:
            current_tokens = self.estimate_tokens(messages)

        threshold = int(self.max_context_tokens * self.settings.trigger_threshold)
        return current_tokens > threshold

    def find_cut_point(
        self,
        messages: list[Message],
    ) -> int:
        """
        找到压缩切分点

        策略：从前往后扫描，找到可以压缩的最早消息位置，
        同时保留最近的消息不被压缩

        Args:
            messages: 消息列表

        Returns:
            切分点索引（该索引之前的消息将被压缩）
        """
        keep_tokens = self.settings.keep_recent_tokens

        # 从后往前计算保留的消息
        tokens_so_far = 0
        keep_from_index = len(messages)

        for i in range(len(messages) - 1, -1, -1):
            msg_tokens = self._estimate_single_message(messages[i])
            if tokens_so_far + msg_tokens > keep_tokens:
                keep_from_index = i + 1
                break
            tokens_so_far += msg_tokens

        # 确保至少保留一些消息
        return max(1, min(keep_from_index - 1, len(messages) - 2))

    def _estimate_single_message(self, message: Message) -> int:
        """估算单条消息的 tokens"""
        if isinstance(message.content, str):
            return len(message.content) // 4
        elif isinstance(message.content, list):
            total = 0
            for block in message.content:
                if isinstance(block, TextBlock):
                    total += len(block.text) // 4
                elif isinstance(block, ToolUseBlock):
                    total += len(block.name) // 4
                    total += len(str(block.input)) // 4
            return total
        return 0

    def prepare_segments(
        self,
        messages: list[Message],
        cut_point: int,
    ) -> tuple[MessageSegment, MessageSegment]:
        """
        准备压缩分段

        Args:
            messages: 消息列表
            cut_point: 切分点

        Returns:
            (待压缩段, 保留段)
        """
        to_compact = messages[:cut_point]
        to_keep = messages[cut_point:]

        return (
            MessageSegment(
                start_index=0,
                end_index=cut_point,
                estimated_tokens=self.estimate_tokens(to_compact),
                messages=to_compact,
            ),
            MessageSegment(
                start_index=cut_point,
                end_index=len(messages),
                estimated_tokens=self.estimate_tokens(to_keep),
                messages=to_keep,
            ),
        )

    async def generate_summary(
        self,
        messages: list[Message],
    ) -> str:
        """
        使用 LLM 生成对话摘要

        Args:
            messages: 待压缩的消息列表

        Returns:
            摘要文本
        """
        # 格式化对话历史
        conversation_text = self._format_messages_for_summary(messages)
        prompt = self.COMPACTION_PROMPT.format(conversation=conversation_text)

        # 调用 LLM 生成摘要
        response = await self.provider.create_message(
            system="你是一个专业的对话摘要助手，擅长提取和总结对话中的关键信息。",
            messages=[{"role": "user", "content": prompt}],
            tools=[],
            max_tokens=2000,
            temperature=0.3,
        )

        return response.text

    def _format_messages_for_summary(self, messages: list[Message]) -> str:
        """格式化消息用于生成摘要"""
        lines = []
        for i, msg in enumerate(messages):
            role = "用户" if msg.role == "user" else "助手"
            content_str = self._extract_text_content(msg)
            # 截断过长的内容
            if len(content_str) > 500:
                content_str = content_str[:500] + "..."
            lines.append(f"[{i+1}] {role}: {content_str}")
        return "\n".join(lines)

    def _extract_text_content(self, message: Message) -> str:
        """提取消息的文本内容"""
        if isinstance(message.content, str):
            return message.content
        elif isinstance(message.content, list):
            parts = []
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    parts.append(f"[调用工具: {block.name}]")
            return " ".join(parts)
        return ""

    async def compact(
        self,
        messages: list[Message],
    ) -> CompactionResult:
        """
        执行压缩

        Args:
            messages: 消息列表

        Returns:
            压缩结果
        """
        original_count = len(messages)
        original_tokens = self.estimate_tokens(messages)

        # 找到切分点
        cut_point = self.find_cut_point(messages)

        if cut_point <= 1:
            # 没有足够的内容可以压缩
            return CompactionResult(
                original_messages=original_count,
                compacted_messages=original_count,
                removed_messages=0,
                summary="",
                tokens_saved=0,
            )

        # 准备分段
        to_compact_segment, to_keep_segment = self.prepare_segments(
            messages, cut_point
        )

        # 生成摘要
        summary = await self.generate_summary(to_compact_segment.messages)

        # 创建摘要消息
        summary_message = Message(
            role="user",
            content=f"[以下是对话历史的摘要]\n{summary}",
        )

        # 组合新消息列表
        new_messages = [summary_message] + to_keep_segment.messages

        # 计算节省的 tokens
        new_tokens = self.estimate_tokens(new_messages)
        tokens_saved = original_tokens - new_tokens

        logger.info(
            "Context compacted",
            extra_data={
                "original_messages": original_count,
                "new_messages": len(new_messages),
                "tokens_saved": tokens_saved,
            },
        )

        return CompactionResult(
            original_messages=original_count,
            compacted_messages=len(new_messages),
            removed_messages=cut_point,
            summary=summary,
            tokens_saved=tokens_saved,
        )

    def build_compacted_messages(
        self,
        messages: list[Message],
        result: CompactionResult,
    ) -> list[Message]:
        """
        根据压缩结果构建新的消息列表

        Args:
            messages: 原始消息列表
            result: 压缩结果

        Returns:
            新的消息列表
        """
        if result.removed_messages == 0:
            return messages

        # 创建摘要消息
        summary_message = Message(
            role="user",
            content=f"[以下是对话历史的摘要]\n{result.summary}",
        )

        # 保留后面的消息
        remaining = messages[result.removed_messages:]

        return [summary_message] + remaining


class AgentCompactor(Compactor):
    """
    Agent 智能压缩器

    使用 Agent 进行更智能的上下文压缩：
    1. 分析对话结构，识别重要内容
    2. 保留关键决策和工具调用链
    3. 生成结构化摘要
    4. 支持按主题分段压缩
    """

    AGENT_COMPACTION_PROMPT = """你是一个上下文压缩专家。请分析以下对话历史并生成一个结构化的摘要。

你的任务：
1. 识别对话中的关键主题和决策点
2. 保留所有重要的工具调用及其结果
3. 标记未完成的任务或待处理事项
4. 提取用户的明确需求和偏好

输出格式（使用 Markdown）：

## 主要主题
- 主题1: 简要描述
- 主题2: 简要描述

## 关键决策
- 决策1: 内容
- 决策2: 内容

## 工具调用摘要
| 工具名 | 目的 | 结果 |
|--------|------|------|
| xxx | xxx | xxx |

## 待处理事项
- [ ] 事项1
- [ ] 事项2

## 用户需求
- 需求1
- 需求2

对话历史：
{conversation}
"""

    def __init__(
        self,
        provider: "BaseProvider",
        settings: CompactionSettings | None = None,
        max_context_tokens: int = 200000,
        agent_engine: "AgentEngine | None" = None,
    ):
        """
        初始化 Agent 压缩器

        Args:
            provider: LLM 提供商
            settings: 压缩配置
            max_context_tokens: 最大上下文 tokens
            agent_engine: 可选的 Agent 引擎（用于更复杂的压缩任务）
        """
        super().__init__(provider, settings, max_context_tokens)
        self.agent_engine = agent_engine
        self._analysis_cache: dict = {}

    async def analyze_conversation(
        self,
        messages: list[Message],
    ) -> dict[str, Any]:
        """
        分析对话结构，识别重要内容

        Returns:
            分析结果，包含主题、决策、工具调用等
        """
        # 分析最近的几条消息，判断是否需要特殊处理
        recent_count = self.settings.agent_analyze_recent
        recent_messages = messages[-recent_count:] if len(messages) > recent_count else messages

        analysis = {
            "total_messages": len(messages),
            "has_tool_calls": False,
            "has_code_blocks": False,
            "topics": [],
            "priority_indices": [],  # 需要优先保留的消息索引
        }

        for msg in messages:
            if isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        analysis["has_tool_calls"] = True
                    elif isinstance(block, TextBlock):
                        if "```" in block.text:
                            analysis["has_code_blocks"] = True

        return analysis

    async def generate_structured_summary(
        self,
        messages: list[Message],
    ) -> str:
        """
        生成结构化的对话摘要

        使用 Agent 进行智能分析，生成更有价值的摘要
        """
        # 先分析对话
        analysis = await self.analyze_conversation(messages)

        # 格式化对话历史
        conversation_text = self._format_messages_for_summary(messages)

        # 如果有 Agent 引擎，使用它进行更智能的压缩
        if self.agent_engine:
            return await self._generate_with_agent(conversation_text, analysis)

        # 否则使用增强的 LLM 调用
        prompt = self.AGENT_COMPACTION_PROMPT.format(conversation=conversation_text)

        response = await self.provider.create_message(
            system="你是一个专业的上下文压缩专家，擅长提取对话中的关键信息并生成结构化摘要。",
            messages=[{"role": "user", "content": prompt}],
            tools=[],
            max_tokens=self.settings.agent_summary_max_tokens,
            temperature=0.3,
        )

        return response.text

    async def _generate_with_agent(
        self,
        conversation_text: str,
        analysis: dict[str, Any],
    ) -> str:
        """使用 Agent 引擎生成摘要"""
        # 构建任务提示
        task_prompt = f"""请分析以下对话历史并生成一个压缩摘要。

对话分析：
- 总消息数: {analysis['total_messages']}
- 包含工具调用: {analysis['has_tool_calls']}
- 包含代码块: {analysis['has_code_blocks']}

对话历史：
{conversation_text}

请生成一个结构化的摘要，保留所有重要信息。"""

        # 使用 Agent 执行
        result = await self.agent_engine.run(task_prompt)
        return result

    async def compact(
        self,
        messages: list[Message],
    ) -> CompactionResult:
        """
        执行 Agent 智能压缩

        相比普通压缩，Agent 压缩会：
        1. 先分析对话结构
        2. 智能识别需要保留的内容
        3. 生成结构化摘要
        """
        original_count = len(messages)
        original_tokens = self.estimate_tokens(messages)

        # 找到切分点
        cut_point = self.find_cut_point(messages)

        if cut_point <= 1:
            return CompactionResult(
                original_messages=original_count,
                compacted_messages=original_count,
                removed_messages=0,
                summary="",
                tokens_saved=0,
            )

        # 准备分段
        to_compact_segment, to_keep_segment = self.prepare_segments(
            messages, cut_point
        )

        # 使用 Agent 生成结构化摘要
        summary = await self.generate_structured_summary(to_compact_segment.messages)

        # 创建摘要消息
        summary_message = Message(
            role="user",
            content=f"[以下是对话历史的智能摘要]\n\n{summary}",
        )

        # 组合新消息列表
        new_messages = [summary_message] + to_keep_segment.messages

        # 计算节省的 tokens
        new_tokens = self.estimate_tokens(new_messages)
        tokens_saved = original_tokens - new_tokens

        logger.info(
            "Agent-based context compaction completed",
            extra_data={
                "strategy": "agent",
                "original_messages": original_count,
                "new_messages": len(new_messages),
                "tokens_saved": tokens_saved,
            },
        )

        return CompactionResult(
            original_messages=original_count,
            compacted_messages=len(new_messages),
            removed_messages=cut_point,
            summary=summary,
            tokens_saved=tokens_saved,
        )


def create_compactor(
    provider: "BaseProvider",
    settings: CompactionSettings | None = None,
    max_context_tokens: int = 200000,
    agent_engine: "AgentEngine | None" = None,
) -> Compactor:
    """
    工厂函数：根据配置创建合适的压缩器

    Args:
        provider: LLM 提供商
        settings: 压缩配置
        max_context_tokens: 最大上下文 tokens
        agent_engine: 可选的 Agent 引擎

    Returns:
        压缩器实例
    """
    settings = settings or CompactionSettings()

    if settings.strategy == CompactionStrategy.AGENT:
        return AgentCompactor(
            provider=provider,
            settings=settings,
            max_context_tokens=max_context_tokens,
            agent_engine=agent_engine,
        )

    return Compactor(
        provider=provider,
        settings=settings,
        max_context_tokens=max_context_tokens,
    )

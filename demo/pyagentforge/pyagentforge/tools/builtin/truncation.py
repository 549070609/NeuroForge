"""
Truncation 工具

智能截断长文本
"""

import re
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TruncationTool(BaseTool):
    """Truncation 工具 - 智能截断"""

    name = "truncation"
    description = """智能截断长文本。

截断策略:
- middle: 保留开头和结尾，截断中间
- end: 保留开头，截断结尾
- smart: 智能识别重要内容保留

适用于:
- 截断过长的工具输出
- 压缩上下文
- 保留关键信息
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要截断的内容",
            },
            "max_length": {
                "type": "integer",
                "description": "最大长度",
                "default": 10000,
            },
            "strategy": {
                "type": "string",
                "enum": ["middle", "end", "smart"],
                "description": "截断策略",
                "default": "smart",
            },
            "preserve_lines": {
                "type": "boolean",
                "description": "是否尝试保持完整行",
                "default": True,
            },
        },
        "required": ["content"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        content: str,
        max_length: int = 10000,
        strategy: str = "smart",
        preserve_lines: bool = True,
    ) -> str:
        """截断内容"""
        if len(content) <= max_length:
            return content

        logger.info(
            "Truncating content",
            extra_data={
                "original_length": len(content),
                "max_length": max_length,
                "strategy": strategy,
            },
        )

        if strategy == "middle":
            return self._truncate_middle(content, max_length, preserve_lines)
        elif strategy == "end":
            return self._truncate_end(content, max_length, preserve_lines)
        elif strategy == "smart":
            return self._truncate_smart(content, max_length, preserve_lines)
        else:
            return self._truncate_end(content, max_length, preserve_lines)

    def _truncate_middle(
        self,
        content: str,
        max_length: int,
        preserve_lines: bool,
    ) -> str:
        """截断中间"""
        if preserve_lines:
            lines = content.split("\n")
            if len(lines) <= 2:
                return content[:max_length]

            # 保留前后各一半
            keep_lines = (max_length // 80) // 2  # 假设平均每行 80 字符
            keep_lines = max(keep_lines, 5)

            head = "\n".join(lines[:keep_lines])
            tail = "\n".join(lines[-keep_lines:])
            omitted = len(lines) - 2 * keep_lines

            return f"{head}\n\n... ({omitted} lines omitted) ...\n\n{tail}"
        else:
            half = max_length // 2
            return f"{content[:half]}\n\n... (content truncated) ...\n\n{content[-half:]}"

    def _truncate_end(
        self,
        content: str,
        max_length: int,
        preserve_lines: bool,
    ) -> str:
        """截断结尾"""
        if preserve_lines:
            lines = content.split("\n")
            result_lines = []
            current_length = 0

            for line in lines:
                if current_length + len(line) + 1 > max_length - 50:
                    break
                result_lines.append(line)
                current_length += len(line) + 1

            omitted = len(lines) - len(result_lines)
            return "\n".join(result_lines) + f"\n\n... ({omitted} more lines truncated)"
        else:
            return content[:max_length] + "\n\n... (content truncated)"

    def _truncate_smart(
        self,
        content: str,
        max_length: int,
        preserve_lines: bool,
    ) -> str:
        """智能截断 - 保留重要内容"""
        lines = content.split("\n")

        # 评分每行的重要性
        scored_lines = []
        for i, line in enumerate(lines):
            score = self._score_line(line, i, len(lines))
            scored_lines.append((i, line, score))

        # 按重要性排序
        scored_lines.sort(key=lambda x: x[2], reverse=True)

        # 选择要保留的行
        selected_indices = set()
        current_length = 0

        for idx, line, score in scored_lines:
            if current_length + len(line) > max_length - 100:
                break
            selected_indices.add(idx)
            current_length += len(line) + 1

        # 按原始顺序重建
        result_lines = []
        last_idx = -1

        for idx in sorted(selected_indices):
            if idx > last_idx + 1:
                result_lines.append(f"... ({idx - last_idx - 1} lines skipped) ...")
            result_lines.append(lines[idx])
            last_idx = idx

        if last_idx < len(lines) - 1:
            result_lines.append(f"... ({len(lines) - last_idx - 1} more lines) ...")

        return "\n".join(result_lines)

    def _score_line(self, line: str, index: int, total: int) -> float:
        """计算行的重要性分数"""
        score = 0.0

        # 开头和结尾的行更重要
        if index < 10:
            score += 10 - index
        elif index > total - 10:
            score += 10 - (total - index)

        # 包含关键词的行更重要
        important_keywords = [
            "error",
            "exception",
            "def ",
            "class ",
            "function ",
            "import ",
            "return",
            "async ",
            "await ",
            "TODO",
            "FIXME",
            "NOTE",
            "###",
            "##",
        ]
        for kw in important_keywords:
            if kw.lower() in line.lower():
                score += 5

        # 非空行更重要
        if line.strip():
            score += 2

        # 包含代码的行
        if re.search(r"[\{\}\[\]\(\):=]", line):
            score += 1

        return score


class ContextCompactTool(BaseTool):
    """ContextCompact 工具 - 上下文压缩"""

    name = "compact"
    description = """压缩消息历史。

当上下文过长时:
- 保留重要消息
- 压缩旧消息
- 生成摘要

压缩策略:
- light: 轻度压缩，保留最近消息
- deep: 深度压缩，只保留摘要
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "description": "消息列表",
                "items": {
                    "type": "object",
                },
            },
            "keep_recent": {
                "type": "integer",
                "description": "保留最近 N 条消息",
                "default": 10,
            },
            "strategy": {
                "type": "string",
                "enum": ["light", "deep"],
                "description": "压缩策略",
                "default": "light",
            },
        },
        "required": ["messages"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        messages: list[dict[str, Any]],
        keep_recent: int = 10,
        strategy: str = "light",
    ) -> str:
        """压缩消息"""
        if len(messages) <= keep_recent:
            return "No compression needed"

        recent = messages[-keep_recent:]
        old = messages[:-keep_recent]

        if strategy == "light":
            # 轻度压缩: 生成旧消息摘要
            summary = self._summarize_messages(old)
            return f"[Summary of {len(old)} earlier messages]\n{summary}\n\n[Recent messages preserved: {len(recent)}]"

        else:
            # 深度压缩: 只保留关键信息
            summary = self._summarize_messages(old)
            return f"[Compressed {len(old)} messages]\n{summary}"

    def _summarize_messages(self, messages: list[dict]) -> str:
        """生成消息摘要"""
        topics = set()
        tools_used = set()

        for msg in messages:
            content = str(msg.get("content", ""))

            # 提取工具使用
            if "tool_use" in str(msg):
                import re

                tools = re.findall(r'"name":\s*"(\w+)"', content)
                tools_used.update(tools)

            # 提取关键主题 (简单实现)
            words = content.lower().split()
            for word in words:
                if len(word) > 5 and word.isalpha():
                    topics.add(word)

        summary_parts = [f"Messages: {len(messages)}"]

        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(sorted(tools_used)[:10])}")

        return "\n".join(summary_parts)

"""
上下文管理器

管理 Agent 对话历史和上下文
"""

import json
import logging
from typing import Any

from pyagentforge.kernel.message import Message, TextBlock, ToolUseBlock

logger = logging.getLogger(__name__)


class ContextManager:
    """上下文管理器 - 管理 Agent 对话历史"""

    def __init__(
        self,
        max_messages: int = 100,
        system_prompt: str | None = None,
    ):
        """
        初始化上下文管理器

        Args:
            max_messages: 最大消息数量，超过会触发截断
            system_prompt: 系统提示词
        """
        self.max_messages = max_messages
        self.system_prompt = system_prompt
        self.messages: list[Message] = []
        self._loaded_skills: set[str] = set()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append(Message.user_message(content))
        logger.debug(f"Added user message, length={len(content)}")

    def add_assistant_message(
        self,
        content: list[TextBlock | ToolUseBlock],
    ) -> None:
        """添加助手消息"""
        self.messages.append(Message(role="assistant", content=content))
        logger.debug(f"Added assistant message, blocks={len(content)}")

    def add_assistant_text(self, text: str) -> None:
        """添加助手文本消息"""
        self.messages.append(Message.assistant_text(text))

    def add_tool_result(
        self,
        tool_use_id: str,
        result: str,
        is_error: bool = False,
    ) -> None:
        """添加工具结果"""
        self.messages.append(Message.tool_result(tool_use_id, result, is_error))
        logger.debug(
            f"Added tool result: id={tool_use_id}, is_error={is_error}, len={len(result)}"
        )

    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """获取用于 API 调用的消息列表"""
        return [msg.to_api_format() for msg in self.messages]

    def truncate(self, keep_last: int | None = None) -> int:
        """
        截断消息历史

        Args:
            keep_last: 保留最近 N 条消息

        Returns:
            截断的消息数量
        """
        keep = keep_last or self.max_messages
        if len(self.messages) <= keep:
            return 0

        removed = len(self.messages) - keep
        self.messages = self.messages[-keep:]
        logger.info(f"Truncated messages: removed={removed}, remaining={len(self.messages)}")
        return removed

    def clear(self) -> None:
        """清空消息历史"""
        self.messages.clear()
        self._loaded_skills.clear()
        logger.debug("Cleared message history")

    def mark_skill_loaded(self, skill_name: str) -> None:
        """标记技能已加载"""
        self._loaded_skills.add(skill_name)

    def is_skill_loaded(self, skill_name: str) -> bool:
        """检查技能是否已加载"""
        return skill_name in self._loaded_skills

    def get_loaded_skills(self) -> set[str]:
        """获取已加载的技能列表"""
        return self._loaded_skills.copy()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "messages": [msg.model_dump() for msg in self.messages],
            "loaded_skills": list(self._loaded_skills),
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextManager":
        """从字典反序列化"""
        ctx = cls()
        ctx.system_prompt = data.get("system_prompt")
        ctx._loaded_skills = set(data.get("loaded_skills", []))

        for msg_data in data.get("messages", []):
            ctx.messages.append(Message(**msg_data))

        return ctx

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ContextManager":
        """从 JSON 反序列化"""
        return cls.from_dict(json.loads(json_str))

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ContextManager(messages={len(self.messages)}, skills={len(self._loaded_skills)})"

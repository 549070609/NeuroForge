"""
Session Key 体系 - 统一会话标识

格式: {channel}:{conversation_id}[:{sub_key}]

Examples:
    - "telegram:-100123456"           # Telegram 群组
    - "discord:123456789"             # Discord 频道
    - "webchat:session-abc123"        # WebChat 会话
    - "agent:main:subagent:task-123"  # 子代理会话
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SessionKey:
    """
    统一会话标识

    跨通道的会话唯一标识符，支持多级子键。

    Attributes:
        channel: 通道类型 (telegram, discord, webchat, agent 等)
        conversation_id: 会话 ID (群组 ID、频道 ID、会话 ID 等)
        sub_key: 可选子键 (子代理标识、任务 ID 等)

    Examples:
        >>> key = SessionKey.parse("telegram:-100123456")
        >>> key.channel
        'telegram'
        >>> key.conversation_id
        '-100123456'

        >>> sub_key = SessionKey("agent", "main", "subagent:task-123")
        >>> sub_key.is_subagent
        True
        >>> str(sub_key)
        'agent:main:subagent:task-123'
    """

    channel: str
    conversation_id: str
    sub_key: Optional[str] = None

    @classmethod
    def parse(cls, key: str) -> "SessionKey":
        """
        解析 Session Key 字符串

        Args:
            key: 格式为 "{channel}:{conversation_id}[:{sub_key}]" 的字符串

        Returns:
            SessionKey 实例

        Raises:
            ValueError: 格式无效 (少于 2 个部分或包含空值)

        Examples:
            >>> SessionKey.parse("telegram:-100123456")
            SessionKey(channel='telegram', conversation_id='-100123456', sub_key=None)

            >>> SessionKey.parse("agent:main:subagent:task-123")
            SessionKey(channel='agent', conversation_id='main', sub_key='subagent:task-123')
        """
        parts = key.split(":")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid session key format: '{key}'. "
                f"Expected format: {{channel}}:{{conversation_id}}[:{{sub_key}}]"
            )

        channel = parts[0]
        conversation_id = parts[1]

        # 空值检查 (v3.0 修复)
        if not channel or not conversation_id:
            raise ValueError(
                f"Invalid session key: '{key}'. "
                f"Channel and conversation_id cannot be empty."
            )

        sub_key = ":".join(parts[2:]) if len(parts) > 2 else None

        return cls(channel, conversation_id, sub_key)

    def __str__(self) -> str:
        """
        转换为字符串格式

        Returns:
            格式化的 Session Key 字符串

        Examples:
            >>> str(SessionKey("telegram", "123"))
            'telegram:123'
            >>> str(SessionKey("agent", "main", "sub"))
            'agent:main:sub'
        """
        if self.sub_key:
            return f"{self.channel}:{self.conversation_id}:{self.sub_key}"
        return f"{self.channel}:{self.conversation_id}"

    def with_sub_key(self, sub_key: str) -> "SessionKey":
        """
        创建带子键的新 SessionKey

        保留当前 channel 和 conversation_id，添加或替换子键。

        Args:
            sub_key: 新的子键

        Returns:
            新的 SessionKey 实例

        Examples:
            >>> parent = SessionKey("telegram", "123")
            >>> child = parent.with_sub_key("task-456")
            >>> str(child)
            'telegram:123:task-456'
        """
        return SessionKey(self.channel, self.conversation_id, sub_key)

    @property
    def is_subagent(self) -> bool:
        """
        检查是否为子代理会话

        子代理会话的 channel 为 "agent" 且存在 sub_key。

        Returns:
            是否为子代理会话

        Examples:
            >>> SessionKey("agent", "main", "sub").is_subagent
            True
            >>> SessionKey("agent", "main").is_subagent
            False
            >>> SessionKey("telegram", "123").is_subagent
            False
        """
        return self.channel == "agent" and self.sub_key is not None

    @property
    def parent_key(self) -> Optional["SessionKey"]:
        """
        获取父会话的 SessionKey

        如果当前会话有子键，返回去掉子键的父会话；
        否则返回 None。

        Returns:
            父会话的 SessionKey 或 None

        Examples:
            >>> child = SessionKey("agent", "main", "sub")
            >>> str(child.parent_key)
            'agent:main'
            >>> SessionKey("telegram", "123").parent_key is None
            True
        """
        if self.sub_key is None:
            return None
        return SessionKey(self.channel, self.conversation_id)

    def __repr__(self) -> str:
        """详细字符串表示"""
        return (
            f"SessionKey(channel={self.channel!r}, "
            f"conversation_id={self.conversation_id!r}, "
            f"sub_key={self.sub_key!r})"
        )

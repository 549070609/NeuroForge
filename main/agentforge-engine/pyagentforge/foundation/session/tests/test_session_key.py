"""
SessionKey 单元测试
"""

import pytest
from pyagentforge.foundation.session.session_key import SessionKey


class TestSessionKeyParse:
    """测试 SessionKey.parse() 方法"""

    def test_parse_simple_key(self):
        """解析简单 key (无子键)"""
        key = SessionKey.parse("telegram:-100123456")
        assert key.channel == "telegram"
        assert key.conversation_id == "-100123456"
        assert key.sub_key is None

    def test_parse_key_with_subkey(self):
        """解析带子键的 key"""
        key = SessionKey.parse("agent:main:subagent:task-123")
        assert key.channel == "agent"
        assert key.conversation_id == "main"
        assert key.sub_key == "subagent:task-123"

    def test_parse_webchat_key(self):
        """解析 WebChat key"""
        key = SessionKey.parse("webchat:session-abc123")
        assert key.channel == "webchat"
        assert key.conversation_id == "session-abc123"

    def test_parse_discord_key(self):
        """解析 Discord key"""
        key = SessionKey.parse("discord:123456789")
        assert key.channel == "discord"
        assert key.conversation_id == "123456789"

    def test_parse_invalid_key_no_colon(self):
        """解析无效 key (无冒号)"""
        with pytest.raises(ValueError) as exc_info:
            SessionKey.parse("invalid")
        assert "Invalid session key format" in str(exc_info.value)

    def test_parse_invalid_key_empty(self):
        """解析空字符串"""
        with pytest.raises(ValueError):
            SessionKey.parse("")

    def test_parse_key_with_colon_in_subkey(self):
        """子键中包含冒号"""
        key = SessionKey.parse("agent:main:level1:level2:level3")
        assert key.sub_key == "level1:level2:level3"


class TestSessionKeyStr:
    """测试 __str__ 方法"""

    def test_str_without_subkey(self):
        """无子键的字符串表示"""
        key = SessionKey("telegram", "123")
        assert str(key) == "telegram:123"

    def test_str_with_subkey(self):
        """有子键的字符串表示"""
        key = SessionKey("agent", "main", "subagent:task-123")
        assert str(key) == "agent:main:subagent:task-123"


class TestSessionKeyWithSubKey:
    """测试 with_sub_key 方法"""

    def test_add_subkey_to_simple_key(self):
        """给简单 key 添加子键"""
        parent = SessionKey("telegram", "123")
        child = parent.with_sub_key("task-456")
        assert str(child) == "telegram:123:task-456"
        assert child.channel == parent.channel
        assert child.conversation_id == parent.conversation_id

    def test_replace_subkey(self):
        """替换现有子键"""
        original = SessionKey("agent", "main", "old")
        new = original.with_sub_key("new")
        assert new.sub_key == "new"
        assert original.sub_key == "old"  # frozen, 原始不变


class TestSessionKeyIsSubagent:
    """测试 is_subagent 属性"""

    def test_is_subagent_true(self):
        """子代理会话"""
        key = SessionKey("agent", "main", "subagent:task-123")
        assert key.is_subagent is True

    def test_is_subagent_false_no_subkey(self):
        """无子键的 agent 会话"""
        key = SessionKey("agent", "main")
        assert key.is_subagent is False

    def test_is_subagent_false_other_channel(self):
        """非 agent 通道"""
        key = SessionKey("telegram", "123", "some-subkey")
        assert key.is_subagent is False


class TestSessionKeyParentKey:
    """测试 parent_key 属性"""

    def test_parent_key_with_subkey(self):
        """有子键时获取父 key"""
        child = SessionKey("agent", "main", "subagent")
        parent = child.parent_key
        assert parent is not None
        assert str(parent) == "agent:main"

    def test_parent_key_without_subkey(self):
        """无子键时返回 None"""
        key = SessionKey("telegram", "123")
        assert key.parent_key is None


class TestSessionKeyFrozen:
    """测试 frozen dataclass 特性"""

    def test_frozen_immutable(self):
        """SessionKey 是不可变的"""
        key = SessionKey("telegram", "123")
        with pytest.raises(AttributeError):
            key.channel = "discord"  # type: ignore


class TestSessionKeyEquality:
    """测试相等性"""

    def test_equal_keys(self):
        """相同参数的 key 相等"""
        key1 = SessionKey("telegram", "123", "sub")
        key2 = SessionKey("telegram", "123", "sub")
        assert key1 == key2

    def test_different_channels(self):
        """不同通道的 key 不相等"""
        key1 = SessionKey("telegram", "123")
        key2 = SessionKey("discord", "123")
        assert key1 != key2

    def test_different_subkeys(self):
        """不同子键的 key 不相等"""
        key1 = SessionKey("agent", "main", "sub1")
        key2 = SessionKey("agent", "main", "sub2")
        assert key1 != key2


class TestSessionKeyHash:
    """测试哈希值 (用于 dict/set)"""

    def test_hashable(self):
        """SessionKey 可以作为 dict key"""
        key1 = SessionKey("telegram", "123")
        key2 = SessionKey("telegram", "123")
        d = {key1: "value"}
        assert d[key2] == "value"

    def test_set_membership(self):
        """SessionKey 可以放入 set"""
        key1 = SessionKey("telegram", "123")
        key2 = SessionKey("telegram", "123")
        s = {key1}
        assert key2 in s

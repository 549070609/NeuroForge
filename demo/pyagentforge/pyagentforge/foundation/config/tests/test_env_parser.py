"""
Environment Variable Parser 单元测试
"""

import os
import pytest
from pyagentforge.foundation.config.env_parser import (
    resolve_env_vars,
    resolve_config,
    has_env_vars,
    get_referenced_vars,
)


class TestResolveEnvVars:
    """测试 resolve_env_vars 函数"""

    def test_resolve_existing_var(self, monkeypatch):
        """解析存在的环境变量"""
        monkeypatch.setenv("TEST_VAR", "hello")
        result = resolve_env_vars("${TEST_VAR}")
        assert result == "hello"

    def test_resolve_with_default_undefined_var(self, monkeypatch):
        """未定义变量使用默认值"""
        monkeypatch.delenv("UNDEFINED_VAR", raising=False)
        result = resolve_env_vars("${UNDEFINED_VAR:-default_value}")
        assert result == "default_value"

    def test_resolve_with_default_defined_var(self, monkeypatch):
        """已定义变量忽略默认值"""
        monkeypatch.setenv("TEST_VAR", "actual_value")
        result = resolve_env_vars("${TEST_VAR:-default_ignored}")
        assert result == "actual_value"

    def test_resolve_missing_var_raises_error(self, monkeypatch):
        """未定义变量无默认值抛出异常"""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(ValueError) as exc_info:
            resolve_env_vars("${MISSING_VAR}")
        assert "Environment variable not found" in str(exc_info.value)
        assert "MISSING_VAR" in str(exc_info.value)

    def test_resolve_embedded_in_string(self, monkeypatch):
        """变量嵌入在字符串中"""
        monkeypatch.setenv("HOST", "example.com")
        result = resolve_env_vars("https://${HOST}/api")
        assert result == "https://example.com/api"

    def test_resolve_multiple_vars(self, monkeypatch):
        """多个环境变量"""
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        result = resolve_env_vars("${HOST}:${PORT}")
        assert result == "localhost:8080"

    def test_resolve_empty_default(self, monkeypatch):
        """空默认值"""
        monkeypatch.delenv("UNDEFINED", raising=False)
        result = resolve_env_vars("${UNDEFINED:-}")
        assert result == ""

    def test_resolve_default_with_special_chars(self, monkeypatch):
        """默认值包含特殊字符"""
        monkeypatch.delenv("PATH_VAR", raising=False)
        result = resolve_env_vars("${PATH_VAR:-/usr/local/bin}")
        assert result == "/usr/local/bin"

    def test_resolve_no_env_vars(self):
        """没有环境变量的字符串"""
        result = resolve_env_vars("plain text without variables")
        assert result == "plain text without variables"


class TestResolveConfig:
    """测试 resolve_config 函数"""

    def test_resolve_simple_config(self, monkeypatch):
        """简单配置解析"""
        monkeypatch.setenv("API_KEY", "secret123")
        config = {"api_key": "${API_KEY}"}
        result = resolve_config(config)
        assert result["api_key"] == "secret123"

    def test_resolve_nested_config(self, monkeypatch):
        """嵌套配置解析"""
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.delenv("PORT", raising=False)
        config = {
            "server": {
                "host": "${HOST}",
                "port": "${PORT:-8080}"
            }
        }
        result = resolve_config(config)
        assert result["server"]["host"] == "localhost"
        assert result["server"]["port"] == "8080"

    def test_resolve_config_with_list(self, monkeypatch):
        """包含列表的配置"""
        monkeypatch.delenv("FEATURE", raising=False)
        config = {
            "features": ["${FEATURE:-enabled}", "static_value"]
        }
        result = resolve_config(config)
        assert result["features"][0] == "enabled"
        assert result["features"][1] == "static_value"

    def test_resolve_config_preserves_non_strings(self):
        """保留非字符串值"""
        config = {
            "count": 42,
            "enabled": True,
            "ratio": 3.14,
            "none_value": None
        }
        result = resolve_config(config)
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["ratio"] == 3.14
        assert result["none_value"] is None

    def test_resolve_deeply_nested_config(self, monkeypatch):
        """深度嵌套配置"""
        monkeypatch.setenv("VALUE", "resolved")
        config = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "${VALUE}"
                    }
                }
            }
        }
        result = resolve_config(config)
        assert result["level1"]["level2"]["level3"]["value"] == "resolved"

    def test_resolve_config_does_not_modify_original(self, monkeypatch):
        """不修改原始配置"""
        monkeypatch.setenv("VAR", "value")
        original = {"key": "${VAR}"}
        result = resolve_config(original)
        assert original["key"] == "${VAR}"
        assert result["key"] == "value"


class TestHasEnvVars:
    """测试 has_env_vars 函数"""

    def test_has_env_vars_true(self):
        """包含环境变量"""
        assert has_env_vars("${API_KEY}") is True

    def test_has_env_vars_false(self):
        """不包含环境变量"""
        assert has_env_vars("plain text") is False

    def test_has_env_vars_with_default(self):
        """带默认值的环境变量"""
        assert has_env_vars("${VAR:-default}") is True

    def test_has_env_vars_multiple(self):
        """多个环境变量"""
        assert has_env_vars("${A} and ${B:-d}") is True


class TestGetReferencedVars:
    """测试 get_referenced_vars 函数"""

    def test_single_var(self):
        """单个变量"""
        vars = get_referenced_vars("${API_KEY}")
        assert vars == ["API_KEY"]

    def test_multiple_vars(self):
        """多个变量"""
        vars = get_referenced_vars("${HOST}:${PORT:-8080}")
        assert vars == ["HOST", "PORT"]

    def test_no_vars(self):
        """无变量"""
        vars = get_referenced_vars("plain text")
        assert vars == []

    def test_repeated_var(self):
        """重复变量"""
        vars = get_referenced_vars("${VAR} and ${VAR}")
        assert vars == ["VAR", "VAR"]


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_string(self):
        """空字符串"""
        assert resolve_env_vars("") == ""

    def test_dollar_sign_not_var(self):
        """美元符号但不是变量"""
        assert resolve_env_vars("$NOT_A_VAR") == "$NOT_A_VAR"

    def test_incomplete_syntax(self):
        """不完整语法"""
        assert resolve_env_vars("${INCOMPLETE") == "${INCOMPLETE"

    def test_nested_braces_in_default(self, monkeypatch):
        """默认值中的嵌套大括号"""
        monkeypatch.delenv("VAR", raising=False)
        # 注意: 这个语法可能不被支持，取决于实现
        # ${VAR:-{nested}} 在当前实现中应该可以工作
        result = resolve_env_vars("${VAR:-{nested}}")
        assert result == "{nested}"

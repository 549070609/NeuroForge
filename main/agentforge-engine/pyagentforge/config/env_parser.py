"""
Environment Variable Parser - 环境变量解析器

支持在配置文件中引用环境变量，避免敏感信息硬编码。

支持格式:
    - ${VAR_NAME}           # 必须存在，否则报错
    - ${VAR_NAME:-default}  # 可选，带默认值

Examples:
    >>> import os
    >>> os.environ['API_KEY'] = 'secret123'
    >>> resolve_env_vars("key=${API_KEY}")
    'key=secret123'

    >>> resolve_env_vars("port=${PORT:-8080}")
    'port=8080'
"""

import os
import re
from typing import Any

# 匹配 ${VAR} 或 ${VAR:-default} 的正则模式
_ENV_VAR_PATTERN = r'\$\{([^}:]+)(?::-([^}]*))?\}'


def resolve_env_vars(value: str) -> str:
    """
    解析字符串中的环境变量

    Args:
        value: 包含环境变量引用的字符串

    Returns:
        解析后的字符串

    Raises:
        ValueError: 环境变量不存在且无默认值

    Examples:
        >>> import os
        >>> os.environ['TEST_VAR'] = 'hello'
        >>> resolve_env_vars("${TEST_VAR}")
        'hello'

        >>> resolve_env_vars("${UNDEFINED:-default_value}")
        'default_value'

        >>> resolve_env_vars("prefix_${TEST_VAR}_suffix")
        'prefix_hello_suffix'
    """
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)

        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        raise ValueError(
            f"Environment variable not found: '{var_name}' "
            f"(no default value provided)"
        )

    return re.sub(_ENV_VAR_PATTERN, replace, value)


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    递归解析配置中的环境变量

    遍历配置字典，解析所有字符串值中的环境变量引用。
    支持嵌套字典和列表。

    Args:
        config: 配置字典

    Returns:
        解析后的配置字典

    Examples:
        >>> import os
        >>> os.environ['HOST'] = 'localhost'
        >>> config = {
        ...     "server": {
        ...         "host": "${HOST}",
        ...         "port": "${PORT:-8080}"
        ...     },
        ...     "features": ["${FEATURE:-enabled}"]
        ... }
        >>> result = resolve_config(config)
        >>> result["server"]["host"]
        'localhost'
        >>> result["server"]["port"]
        '8080'
    """
    result: dict[str, Any] = {}

    for key, value in config.items():
        if isinstance(value, str):
            result[key] = resolve_env_vars(value)
        elif isinstance(value, dict):
            result[key] = resolve_config(value)
        elif isinstance(value, list):
            result[key] = [
                resolve_env_vars(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value

    return result


def has_env_vars(value: str) -> bool:
    """
    检查字符串是否包含环境变量引用

    Args:
        value: 要检查的字符串

    Returns:
        是否包含环境变量引用

    Examples:
        >>> has_env_vars("${API_KEY}")
        True
        >>> has_env_vars("no env vars here")
        False
    """
    return bool(re.search(_ENV_VAR_PATTERN, value))


def get_referenced_vars(value: str) -> list[str]:
    """
    获取字符串中引用的所有环境变量名

    Args:
        value: 要解析的字符串

    Returns:
        环境变量名列表

    Examples:
        >>> get_referenced_vars("${API_KEY} and ${SECRET:-default}")
        ['API_KEY', 'SECRET']
    """
    matches = re.findall(_ENV_VAR_PATTERN, value)
    return [match[0] for match in matches]

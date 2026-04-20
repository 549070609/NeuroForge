"""
宸ュ叿鏉冮檺鎺у埗

绠＄悊宸ュ叿鐨勮闂潈闄愶紝鏀寔鍙傛暟绾ф潈闄愭帶鍒?
"""

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PermissionResult(Enum):
    """权限检查结果"""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class ParameterPermissionRule(BaseModel):
    """参数级权限规则"""

    parameter_name: str  # 参数名 (如 file_path, command)
    patterns: dict[str, PermissionResult] = Field(default_factory=dict)  # 模式 -> 结果
    default: PermissionResult = PermissionResult.ASK  # 默认结果

    def check(self, value: Any) -> PermissionResult:
        """
        检查参数值

        Args:
            value: 参数值

        Returns:
            鏉冮檺缁撴灉
        """
        if not isinstance(value, str):
            value = str(value)

        # 鎸夋ā寮忓尮閰?(绮剧‘鍖归厤浼樺厛)
        for pattern, result in sorted(
            self.patterns.items(),
            key=lambda x: -len(x[0].replace("*", "")),  # 鏇村叿浣撶殑妯紡浼樺厛
        ):
            if self._match_pattern(value, pattern):
                return result

        return self.default

    def _match_pattern(self, value: str, pattern: str) -> bool:
        """"""
        #
        if "*" in pattern or "?" in pattern or "[" in pattern:
            return fnmatch(value, pattern)
        # 绮剧‘鍖归厤
        return value == pattern


class ParameterPermissionConfig(BaseModel):
    """参数级权限配置"""

    # 鍚勫伐鍏风殑鍙傛暟瑙勫垯
    tools: dict[str, dict[str, ParameterPermissionRule]] = Field(default_factory=dict)

    # 绀轰緥閰嶇疆:
    # tools:
    #   write:
    #     file_path:
    #       patterns:
    #         "*.env": deny
    #         "*.md": allow
    #         "src/**": allow
    #       default: ask
    #   edit:
    #     file_path:
    #       patterns:
    #         "*.env": deny
    #       default: ask
    #   bash:
    #     command:
    #       patterns:
    #         "git*": allow
    #         "rm*": deny
    #         "npm*": ask
    #       default: deny


class PermissionConfig(BaseModel):
    """鏉冮檺閰嶇疆"""

    # 宸ュ叿绾ф潈闄?
    allowed: list[str] = Field(default_factory=lambda: ["*"])
    denied: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)

    # 鍛戒护鐧藉悕鍗?(鐢ㄤ簬 bash 宸ュ叿)
    command_whitelist: list[str] = Field(default_factory=list)
    command_blacklist: list[str] = Field(default_factory=list)

    #
    allowed_paths: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)

    # 缃戠粶闄愬埗
    allowed_hosts: list[str] = Field(default_factory=list)
    denied_hosts: list[str] = Field(default_factory=list)

    #
    parameter_rules: ParameterPermissionConfig = Field(
        default_factory=ParameterPermissionConfig
    )


class PermissionChecker:
    """权限检查器"""

    def __init__(self, config: PermissionConfig) -> None:
        self.config = config

    def check(self, tool_name: str, tool_input: dict[str, Any]) -> PermissionResult:
        """
        检查工具权限

        Args:
            tool_name: 宸ュ叿鍚嶇О
            tool_input: 宸ュ叿杈撳叆

        Returns:
            权限检查结果
        """
        #
        param_result = self._check_parameter_permissions(tool_name, tool_input)
        if param_result != PermissionResult.ALLOW:
            # 鍙傛暟绾ф潈闄愬彲鑳借繑鍥?DENY 鎴?ASK
            # 浣嗕笉瑕嗙洊宸ュ叿绾х殑 ALLOW
            if param_result == PermissionResult.DENY:
                return PermissionResult.DENY

        # 2. 检查拒绝列表
        if self._matches_pattern(tool_name, self.config.denied):
            return PermissionResult.DENY

        # 3. 妫鏌ラ渶瑕佺‘璁ょ殑鍒楄〃
        if self._matches_pattern(tool_name, self.config.ask):
            return PermissionResult.ASK

        #
        if param_result == PermissionResult.ASK:
            return PermissionResult.ASK

        # 5. 检查允许列表
        if self._matches_pattern(tool_name, self.config.allowed):
            return PermissionResult.ALLOW

        #
        return PermissionResult.DENY

    def _check_parameter_permissions(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> PermissionResult:
        """
        检查参数级权限

        Args:
            tool_name: 宸ュ叿鍚嶇О
            tool_input: 宸ュ叿杈撳叆

        Returns:
            鏉冮檺缁撴灉
        """
        # 鑾峰彇璇ュ伐鍏风殑鍙傛暟瑙勫垯
        tool_rules = self.config.parameter_rules.tools.get(tool_name)
        if not tool_rules:
            return PermissionResult.ALLOW

        #
        for param_name, rule in tool_rules.items():
            if param_name not in tool_input:
                continue

            value = tool_input[param_name]
            result = rule.check(value)

            if result == PermissionResult.DENY:
                logger.info(
                    "Parameter permission denied",
                    extra_data={
                        "tool": tool_name,
                        "parameter": param_name,
                        "value": value,
                    },
                )
                return PermissionResult.DENY

            if result == PermissionResult.ASK:
                logger.info(
                    "Parameter permission ask",
                    extra_data={
                        "tool": tool_name,
                        "parameter": param_name,
                        "value": value,
                    },
                )
                #
                #

        # 濡傛灉鏈変换浣曞弬鏁伴渶瑕佺‘璁わ紝杩斿洖 ASK
        for param_name, rule in tool_rules.items():
            if param_name in tool_input and rule.check(tool_input[param_name]) == PermissionResult.ASK:
                return PermissionResult.ASK

        return PermissionResult.ALLOW

    def check_command(self, command: str) -> PermissionResult:
        """
        检查命令权限

        Args:
            command: Shell 鍛戒护

        Returns:
            权限检查结果
        """
        #
        tool_rules = self.config.parameter_rules.tools.get("bash")
        if tool_rules and "command" in tool_rules:
            result = tool_rules["command"].check(command)
            if result != PermissionResult.ALLOW:
                return result

        # 鎻愬彇鍛戒护鍚嶇О
        cmd_name = command.split()[0] if command else ""

        # 检查黑名单
        if self._matches_pattern(cmd_name, self.config.command_blacklist):
            return PermissionResult.DENY

        #
        if self.config.command_whitelist and not self._matches_pattern(
            cmd_name, self.config.command_whitelist
        ):
            return PermissionResult.DENY

        return PermissionResult.ALLOW

    def check_path(self, path: str) -> PermissionResult:
        """
        检查路径权限

        Args:
            path: 鏂囦欢璺緞

        Returns:
            权限检查结果
        """
        # 鏍囧噯鍖栬矾寰?
        try:
            normalized = str(Path(path).resolve())
        except Exception:
            normalized = path

        #
        for denied_path in self.config.denied_paths:
            try:
                denied_normalized = str(Path(denied_path).resolve())
                if normalized.startswith(denied_normalized):
                    return PermissionResult.DENY
            except Exception:
                if normalized.startswith(denied_path):
                    return PermissionResult.DENY

        #
        if self.config.allowed_paths:
            allowed = False
            for allowed_path in self.config.allowed_paths:
                try:
                    allowed_normalized = str(Path(allowed_path).resolve())
                    if normalized.startswith(allowed_normalized):
                        allowed = True
                        break
                except Exception:
                    if normalized.startswith(allowed_path):
                        allowed = True
                        break
            if not allowed:
                return PermissionResult.DENY

        return PermissionResult.ALLOW

    def check_host(self, host: str) -> PermissionResult:
        """
        检查主机权限

        Args:
            host: 涓绘満鍚?

        Returns:
            权限检查结果
        """
        # 检查拒绝的主机
        if self._matches_pattern(host, self.config.denied_hosts):
            return PermissionResult.DENY

        #
        if self.config.allowed_hosts and not self._matches_pattern(host, self.config.allowed_hosts):
            return PermissionResult.DENY

        return PermissionResult.ALLOW

    def _matches_pattern(self, value: str, patterns: list[str]) -> bool:
        """
        检查值是否匹配任意模式

        鏀寔閫氶厤绗?* 鍖归厤
        """
        if "*" in patterns:
            return True

        for pattern in patterns:
            if pattern.endswith("*"):
                # 鍓嶇紑鍖归厤
                if value.startswith(pattern[:-1]):
                    return True
            elif pattern.startswith("*"):
                # 鍚庣紑鍖归厤
                if value.endswith(pattern[1:]):
                    return True
            elif value == pattern:
                # 绮剧‘鍖归厤
                return True

        return False


def create_permission_config_from_dict(config: dict[str, Any]) -> PermissionConfig:
    """
    从字典创建权限配置

    Args:
        config: 配置字典

    Returns:
        PermissionConfig 瀹炰緥
    """
    param_config = ParameterPermissionConfig()

    # 瑙ｆ瀽鍙傛暟绾ф潈闄?
    for tool_name, tool_config in config.get("parameter_rules", {}).items():
        param_rules = {}
        for param_name, param_config_dict in tool_config.items():
            patterns = {}
            for pattern, result_str in param_config_dict.get("patterns", {}).items():
                patterns[pattern] = PermissionResult(result_str)

            param_rules[param_name] = ParameterPermissionRule(
                parameter_name=param_name,
                patterns=patterns,
                default=PermissionResult(
                    param_config_dict.get("default", "ask")
                ),
            )
        param_config.tools[tool_name] = param_rules

    return PermissionConfig(
        allowed=config.get("allowed", ["*"]),
        denied=config.get("denied", []),
        ask=config.get("ask", []),
        command_whitelist=config.get("command_whitelist", []),
        command_blacklist=config.get("command_blacklist", []),
        allowed_paths=config.get("allowed_paths", []),
        denied_paths=config.get("denied_paths", []),
        allowed_hosts=config.get("allowed_hosts", []),
        denied_hosts=config.get("denied_hosts", []),
        parameter_rules=param_config,
    )


#
EXAMPLE_PARAMETER_PERMISSIONS = {
    "parameter_rules": {
        "write": {
            "file_path": {
                "patterns": {
                    "*.env": "deny",
                    "*.pem": "deny",
                    "*.key": "deny",
                    "*.md": "allow",
                    "*.txt": "allow",
                    "dist/*": "allow",
                },
                "default": "ask",
            }
        },
        "edit": {
            "file_path": {
                "patterns": {
                    "*.env": "deny",
                    "*.pem": "deny",
                    "src/**": "allow",
                },
                "default": "ask",
            }
        },
        "read": {
            "file_path": {
                "patterns": {
                    "*.env": "deny",
                    ".git/*": "deny",
                    "~/.ssh/*": "deny",
                },
                "default": "allow",
            }
        },
        "bash": {
            "command": {
                "patterns": {
                    "git status*": "allow",
                    "git diff*": "allow",
                    "git log*": "allow",
                    "git add*": "ask",
                    "git commit*": "ask",
                    "git push*": "ask",
                    "rm*": "deny",
                    "rm -rf /": "deny",
                    "npm*": "ask",
                    "bun*": "ask",
                    "ls*": "allow",
                    "cat*": "allow",
                    "pwd": "allow",
                },
                "default": "deny",
            }
        },
        "webfetch": {
            "url": {
                "patterns": {
                    "*.internal.*": "deny",
                    "localhost*": "deny",
                    "127.*": "deny",
                },
                "default": "ask",
            }
        },
    }
}


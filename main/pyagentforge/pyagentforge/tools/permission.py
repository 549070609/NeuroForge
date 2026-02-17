"""
工具权限控制

管理工具的访问权限，支持参数级权限控制
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
            权限结果
        """
        if not isinstance(value, str):
            value = str(value)

        # 按模式匹配 (精确匹配优先)
        for pattern, result in sorted(
            self.patterns.items(),
            key=lambda x: -len(x[0].replace("*", "")),  # 更具体的模式优先
        ):
            if self._match_pattern(value, pattern):
                return result

        return self.default

    def _match_pattern(self, value: str, pattern: str) -> bool:
        """匹配模式"""
        # 支持 glob 模式
        if "*" in pattern or "?" in pattern or "[" in pattern:
            return fnmatch(value, pattern)
        # 精确匹配
        return value == pattern


class ParameterPermissionConfig(BaseModel):
    """参数级权限配置"""

    # 各工具的参数规则
    tools: dict[str, dict[str, ParameterPermissionRule]] = Field(default_factory=dict)

    # 示例配置:
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
    """权限配置"""

    # 工具级权限
    allowed: list[str] = Field(default_factory=lambda: ["*"])
    denied: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)

    # 命令白名单 (用于 bash 工具)
    command_whitelist: list[str] = Field(default_factory=list)
    command_blacklist: list[str] = Field(default_factory=list)

    # 路径限制
    allowed_paths: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)

    # 网络限制
    allowed_hosts: list[str] = Field(default_factory=list)
    denied_hosts: list[str] = Field(default_factory=list)

    # 参数级权限 (新增)
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
            tool_name: 工具名称
            tool_input: 工具输入

        Returns:
            权限检查结果
        """
        # 1. 先检查参数级权限 (最高优先级)
        param_result = self._check_parameter_permissions(tool_name, tool_input)
        if param_result != PermissionResult.ALLOW:
            # 参数级权限可能返回 DENY 或 ASK
            # 但不覆盖工具级的 ALLOW
            if param_result == PermissionResult.DENY:
                return PermissionResult.DENY

        # 2. 检查拒绝列表
        if self._matches_pattern(tool_name, self.config.denied):
            return PermissionResult.DENY

        # 3. 检查需要确认的列表
        if self._matches_pattern(tool_name, self.config.ask):
            return PermissionResult.ASK

        # 4. 如果参数级权限要求确认，且工具级允许
        if param_result == PermissionResult.ASK:
            return PermissionResult.ASK

        # 5. 检查允许列表
        if self._matches_pattern(tool_name, self.config.allowed):
            return PermissionResult.ALLOW

        # 6. 默认拒绝
        return PermissionResult.DENY

    def _check_parameter_permissions(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> PermissionResult:
        """
        检查参数级权限

        Args:
            tool_name: 工具名称
            tool_input: 工具输入

        Returns:
            权限结果
        """
        # 获取该工具的参数规则
        tool_rules = self.config.parameter_rules.tools.get(tool_name)
        if not tool_rules:
            return PermissionResult.ALLOW

        # 检查每个参数
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
                # 继续检查其他参数，但记住需要确认
                # 如果没有其他参数被拒绝，返回 ASK

        # 如果有任何参数需要确认，返回 ASK
        for param_name, rule in tool_rules.items():
            if param_name in tool_input and rule.check(tool_input[param_name]) == PermissionResult.ASK:
                return PermissionResult.ASK

        return PermissionResult.ALLOW

    def check_command(self, command: str) -> PermissionResult:
        """
        检查命令权限

        Args:
            command: Shell 命令

        Returns:
            权限检查结果
        """
        # 先检查参数级规则
        tool_rules = self.config.parameter_rules.tools.get("bash")
        if tool_rules and "command" in tool_rules:
            result = tool_rules["command"].check(command)
            if result != PermissionResult.ALLOW:
                return result

        # 提取命令名称
        cmd_name = command.split()[0] if command else ""

        # 检查黑名单
        if self._matches_pattern(cmd_name, self.config.command_blacklist):
            return PermissionResult.DENY

        # 如果有白名单，检查是否在白名单中
        if self.config.command_whitelist:
            if not self._matches_pattern(cmd_name, self.config.command_whitelist):
                return PermissionResult.DENY

        return PermissionResult.ALLOW

    def check_path(self, path: str) -> PermissionResult:
        """
        检查路径权限

        Args:
            path: 文件路径

        Returns:
            权限检查结果
        """
        # 标准化路径
        try:
            normalized = str(Path(path).resolve())
        except Exception:
            normalized = path

        # 检查拒绝的路径
        for denied_path in self.config.denied_paths:
            try:
                denied_normalized = str(Path(denied_path).resolve())
                if normalized.startswith(denied_normalized):
                    return PermissionResult.DENY
            except Exception:
                if normalized.startswith(denied_path):
                    return PermissionResult.DENY

        # 如果有允许的路径限制，检查是否在允许范围内
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
            host: 主机名

        Returns:
            权限检查结果
        """
        # 检查拒绝的主机
        if self._matches_pattern(host, self.config.denied_hosts):
            return PermissionResult.DENY

        # 如果有允许的主机限制，检查是否在允许范围内
        if self.config.allowed_hosts:
            if not self._matches_pattern(host, self.config.allowed_hosts):
                return PermissionResult.DENY

        return PermissionResult.ALLOW

    def _matches_pattern(self, value: str, patterns: list[str]) -> bool:
        """
        检查值是否匹配任意模式

        支持通配符 * 匹配
        """
        if "*" in patterns:
            return True

        for pattern in patterns:
            if pattern.endswith("*"):
                # 前缀匹配
                if value.startswith(pattern[:-1]):
                    return True
            elif pattern.startswith("*"):
                # 后缀匹配
                if value.endswith(pattern[1:]):
                    return True
            elif value == pattern:
                # 精确匹配
                return True

        return False


def create_permission_config_from_dict(config: dict[str, Any]) -> PermissionConfig:
    """
    从字典创建权限配置

    Args:
        config: 配置字典

    Returns:
        PermissionConfig 实例
    """
    param_config = ParameterPermissionConfig()

    # 解析参数级权限
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


# 预定义的参数级权限配置示例
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

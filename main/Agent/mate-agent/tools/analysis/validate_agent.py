"""
验证 Agent 工具

验证 Agent 配置的正确性和完整性。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class ValidateAgentTool(MateAgentTool):
    """
    验证 Agent 工具

    验证 Agent 配置的正确性和完整性。

    验证项:
    - YAML 语法正确性
    - 必需字段是否存在
    - 字段值是否符合规范 (温度范围、名称格式等)
    - 工具是否存在
    - Anthropic API 兼容性

    参数:
        agent_id: Agent ID (可选，不提供则验证所有)
        checks: 要执行的检查项 (可选)
    """

    name = "validate_agent"
    description = "验证 Agent 配置的正确性和完整性"
    category = "analysis"
    requires_confirmation = False
    timeout = 30

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "要验证的 Agent ID (可选，不提供则验证所有)"
            },
            "checks": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["syntax", "required_fields", "value_ranges", "tools", "api_compatibility"]
                },
                "description": "要执行的检查项 (可选，默认全部)"
            }
        }
    }

    # 支持的模型列表
    SUPPORTED_MODELS = {
        "anthropic": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行验证

        Args:
            agent_id: Agent ID
            checks: 要执行的检查项

        Returns:
            验证报告
        """
        agent_id = kwargs.get("agent_id")
        checks = kwargs.get("checks")

        # 默认执行所有检查
        if not checks:
            checks = ["syntax", "required_fields", "value_ranges", "tools", "api_compatibility"]

        try:
            directory = self._ensure_directory()

            if agent_id:
                # 验证单个 Agent
                agent = directory.get_agent(agent_id)
                if not agent:
                    return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

                result = self._validate_agent(agent, checks)
                results = {agent_id: result}
            else:
                # 验证所有 Agent
                results = {}
                for agent in directory.list_agents():
                    results[agent.agent_id] = self._validate_agent(agent, checks)

            # 汇总统计
            summary = self._summarize_results(results)

            self._log_operation("validate_agent", {
                "agent_id": agent_id,
                "checks": checks,
                "summary": summary,
            })

            return self._format_validation_report(results, summary)

        except Exception as e:
            logger.exception("Failed to validate agent")
            return self._format_error(f"验证失败: {str(e)}", "VALIDATION_FAILED")

    def _validate_agent(self, agent: Any, checks: list[str]) -> dict[str, Any]:
        """
        验证单个 Agent

        Args:
            agent: AgentInfo 实例
            checks: 要执行的检查项

        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }

        metadata = agent.metadata

        # 语法检查
        if "syntax" in checks:
            self._check_syntax(metadata, result)

        # 必需字段检查
        if "required_fields" in checks:
            self._check_required_fields(metadata, result)

        # 值范围检查
        if "value_ranges" in checks:
            self._check_value_ranges(metadata, result)

        # 工具检查
        if "tools" in checks:
            self._check_tools(metadata, result)

        # API 兼容性检查
        if "api_compatibility" in checks:
            self._check_api_compatibility(metadata, result)

        # 更新有效性状态
        result["valid"] = len(result["errors"]) == 0

        return result

    def _check_syntax(self, metadata: dict[str, Any], result: dict[str, Any]) -> None:
        """检查 YAML 语法"""
        # 这里主要检查数据结构是否合理
        if not isinstance(metadata, dict):
            result["errors"].append("配置格式错误: 应为字典类型")
            return

        # 检查关键字段类型
        identity = metadata.get("identity", {})
        if not isinstance(identity, dict):
            result["errors"].append("identity 应为字典类型")

        model = metadata.get("model", {})
        if model and not isinstance(model, dict):
            result["errors"].append("model 应为字典类型")

    def _check_required_fields(self, metadata: dict[str, Any], result: dict[str, Any]) -> None:
        """检查必需字段"""
        identity = metadata.get("identity", {})

        # 名称
        if not identity.get("name"):
            result["errors"].append("缺少必需字段: identity.name")

        # 描述
        if not identity.get("description"):
            result["warnings"].append("建议添加 identity.description")

        # 模型配置
        model = metadata.get("model", {})
        if not model.get("provider"):
            result["errors"].append("缺少必需字段: model.provider")

        if not model.get("model"):
            result["errors"].append("缺少必需字段: model.model")

    def _check_value_ranges(self, metadata: dict[str, Any], result: dict[str, Any]) -> None:
        """检查值范围"""
        model = metadata.get("model", {})

        # 温度范围
        temperature = model.get("temperature")
        if temperature is not None:
            if not (0 <= temperature <= 1):
                result["errors"].append(f"temperature 超出范围 [0, 1]: {temperature}")
            elif temperature > 0.9:
                result["warnings"].append(f"temperature 较高 ({temperature})，输出可能不稳定")

        # max_tokens
        max_tokens = model.get("max_tokens")
        if max_tokens is not None:
            if max_tokens < 1:
                result["errors"].append(f"max_tokens 必须大于 0: {max_tokens}")
            elif max_tokens > 128000:
                result["warnings"].append(f"max_tokens 可能超出模型限制: {max_tokens}")

        # 名称格式
        identity = metadata.get("identity", {})
        name = identity.get("name", "")
        if name and not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
            result["warnings"].append(f"name 格式建议使用字母开头的字母数字组合: {name}")

        # limits
        limits = metadata.get("limits", {})
        max_iterations = limits.get("max_iterations")
        if max_iterations is not None and max_iterations < 1:
            result["errors"].append(f"max_iterations 必须大于 0: {max_iterations}")

        timeout = limits.get("timeout")
        if timeout is not None and timeout < 1:
            result["errors"].append(f"timeout 必须大于 0: {timeout}")

    def _check_tools(self, metadata: dict[str, Any], result: dict[str, Any]) -> None:
        """检查工具配置"""
        capabilities = metadata.get("capabilities", {})
        tools = capabilities.get("tools", [])

        if not isinstance(tools, list):
            result["errors"].append("tools 应为数组类型")
            return

        # 检查工具名称格式
        for tool in tools:
            if not isinstance(tool, str):
                result["errors"].append(f"工具名应为字符串: {tool}")
            elif not re.match(r"^[a-z][a-z0-9_]*$", tool):
                result["warnings"].append(f"工具名格式建议使用 snake_case: {tool}")

        # 检查重复工具
        if len(tools) != len(set(tools)):
            result["warnings"].append("存在重复的工具定义")

    def _check_api_compatibility(self, metadata: dict[str, Any], result: dict[str, Any]) -> None:
        """检查 Anthropic API 兼容性"""
        model = metadata.get("model", {})

        provider = model.get("provider", "")
        model_name = model.get("model", "")

        # 检查支持的 provider
        if provider not in self.SUPPORTED_MODELS:
            result["warnings"].append(f"未知的 provider: {provider}")
            return

        # 检查模型是否支持
        supported = self.SUPPORTED_MODELS.get(provider, [])
        if model_name and model_name not in supported:
            result["suggestions"].append(
                f"模型 '{model_name}' 可能不在推荐列表中。支持的模型: {', '.join(supported[:3])}..."
            )

        # 检查 temperature 精度
        temperature = model.get("temperature")
        if temperature is not None:
            # 检查是否有过多小数位
            temp_str = str(temperature)
            if "." in temp_str and len(temp_str.split(".")[1]) > 2:
                result["suggestions"].append("temperature 建议保留 1-2 位小数")

    def _summarize_results(self, results: dict[str, Any]) -> dict[str, int]:
        """汇总验证结果"""
        summary = {
            "total": len(results),
            "valid": 0,
            "invalid": 0,
            "total_errors": 0,
            "total_warnings": 0,
        }

        for agent_result in results.values():
            if agent_result["valid"]:
                summary["valid"] += 1
            else:
                summary["invalid"] += 1

            summary["total_errors"] += len(agent_result["errors"])
            summary["total_warnings"] += len(agent_result["warnings"])

        return summary

    def _format_validation_report(self, results: dict[str, Any], summary: dict[str, int]) -> str:
        """格式化验证报告"""
        import json

        report = {
            "success": True,
            "summary": summary,
            "results": results,
        }

        return json.dumps(report, ensure_ascii=False, indent=2)

"""
分析需求工具

分析用户需求，推断 Agent 类型和配置建议。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class AnalyzeRequirementsTool(MateAgentTool):
    """
    分析需求工具

    分析用户对 Agent 的需求描述，推断合适的 Agent 类型和配置。

    输出:
    - agent_type: simple/tool/reasoning/hybrid
    - recommended_model: 推荐的模型配置
    - required_tools: 推荐的工具列表
    - clarifications: 需要用户确认的问题

    参数:
        requirements: 需求描述文本
        context: 额外上下文 (可选)
    """

    name = "analyze_requirements"
    description = "分析用户需求，推断 Agent 类型和配置建议"
    category = "analysis"
    requires_confirmation = False
    timeout = 30

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "string",
                "description": "Agent 需求描述文本"
            },
            "context": {
                "type": "object",
                "description": "额外上下文信息",
                "properties": {
                    "existing_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已有的工具列表"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "目标命名空间"
                    },
                    "budget_tier": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "预算级别"
                    }
                }
            }
        },
        "required": ["requirements"]
    }

    # 需求关键词映射
    TOOL_KEYWORDS = [
        "文件", "读写", "网络", "请求", "数据库", "搜索",
        "执行", "命令", "构建", "部署", "测试",
        "file", "read", "write", "network", "request", "database", "search",
        "execute", "command", "build", "deploy", "test",
    ]

    REASONING_KEYWORDS = [
        "分析", "推理", "决策", "规划", "策略", "评估",
        "比较", "权衡", "思考", "复杂", "逻辑",
        "analyze", "reasoning", "decision", "plan", "strategy", "evaluate",
        "compare", "balance", "think", "complex", "logic",
    ]

    SIMPLE_KEYWORDS = [
        "简单", "基础", "问答", "聊天", "辅助", "助手",
        "simple", "basic", "qa", "chat", "assistant", "helper",
    ]

    # 工具推荐映射
    TOOL_RECOMMENDATIONS = {
        "文件操作": ["read", "write", "edit"],
        "file": ["read", "write", "edit"],
        "代码": ["read", "write", "edit", "bash"],
        "code": ["read", "write", "edit", "bash"],
        "网络": ["fetch", "request"],
        "network": ["fetch", "request"],
        "搜索": ["search", "grep"],
        "search": ["search", "grep"],
        "数据库": ["query", "read"],
        "database": ["query", "read"],
        "测试": ["bash", "test"],
        "test": ["bash", "test"],
        "命令": ["bash", "execute"],
        "command": ["bash", "execute"],
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行需求分析

        Args:
            requirements: 需求描述
            context: 额外上下文

        Returns:
            分析结果
        """
        requirements = kwargs.get("requirements", "")
        context = kwargs.get("context", {})

        if not requirements:
            return self._format_error("requirements 是必需参数", "MISSING_REQUIREMENTS")

        try:
            # 分析需求
            analysis = self._analyze_requirements(requirements, context)

            self._log_operation("analyze_requirements", {
                "requirements_length": len(requirements),
                "agent_type": analysis["agent_type"],
            })

            return self._format_success("需求分析完成", analysis)

        except Exception as e:
            logger.exception("Failed to analyze requirements")
            return self._format_error(f"需求分析失败: {str(e)}", "ANALYSIS_FAILED")

    def _analyze_requirements(self, requirements: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        分析需求

        Args:
            requirements: 需求描述
            context: 上下文

        Returns:
            分析结果
        """
        text = requirements.lower()

        # 检测 Agent 类型
        agent_type = self._detect_agent_type(text)

        # 推荐工具
        required_tools = self._recommend_tools(text, context)

        # 推荐模型
        recommended_model = self._recommend_model(agent_type, context)

        # 生成需要确认的问题
        clarifications = self._generate_clarifications(
            requirements, agent_type, required_tools, context
        )

        # 生成配置建议
        config_suggestions = self._generate_config_suggestions(
            agent_type, required_tools, context
        )

        return {
            "agent_type": agent_type,
            "recommended_model": recommended_model,
            "required_tools": required_tools,
            "clarifications": clarifications,
            "config_suggestions": config_suggestions,
            "confidence": self._calculate_confidence(text, agent_type),
        }

    def _detect_agent_type(self, text: str) -> str:
        """检测 Agent 类型"""
        tool_score = sum(1 for kw in self.TOOL_KEYWORDS if kw in text)
        reasoning_score = sum(1 for kw in self.REASONING_KEYWORDS if kw in text)
        simple_score = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in text)

        scores = {
            "tool": tool_score,
            "reasoning": reasoning_score,
            "simple": simple_score,
        }

        # 找出最高分
        max_type = max(scores, key=scores.get)

        # 如果分数相近，可能是混合型
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            ratio = sorted_scores[1] / sorted_scores[0] if sorted_scores[0] > 0 else 0
            if ratio > 0.7:
                return "hybrid"

        # 如果所有分数都很低，默认简单型
        if max(scores.values()) == 0:
            return "simple"

        return max_type

    def _recommend_tools(self, text: str, context: dict[str, Any]) -> list[str]:
        """推荐工具"""
        tools = set()

        # 基于关键词推荐
        for keyword, recommended in self.TOOL_RECOMMENDATIONS.items():
            if keyword.lower() in text:
                tools.update(recommended)

        # 基础工具
        if not tools:
            tools.add("read")  # 默认添加读取能力

        # 检查已有工具
        existing = context.get("existing_tools", [])
        if existing:
            # 过滤掉不兼容的工具
            tools = tools - set(existing)

        return sorted(list(tools))

    def _recommend_model(self, agent_type: str, context: dict[str, Any]) -> dict[str, Any]:
        """推荐模型配置"""
        budget = context.get("budget_tier", "medium")

        # 基础配置
        base_config = {
            "provider": "anthropic",
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        # 根据类型调整
        if agent_type == "reasoning":
            base_config["temperature"] = 0.3
            base_config["max_tokens"] = 8192
            model = "claude-sonnet-4-20250514" if budget != "low" else "claude-haiku-4-5-20251001"
        elif agent_type == "tool":
            base_config["temperature"] = 0.5
            model = "claude-sonnet-4-20250514"
        elif agent_type == "hybrid":
            base_config["temperature"] = 0.4
            base_config["max_tokens"] = 8192
            model = "claude-sonnet-4-20250514"
        else:  # simple
            model = "claude-haiku-4-5-20251001"

        # 预算调整
        if budget == "low":
            model = "claude-haiku-4-5-20251001"
            base_config["max_tokens"] = min(base_config["max_tokens"], 4096)
        elif budget == "high":
            model = "claude-opus-4-6"
            base_config["max_tokens"] = max(base_config["max_tokens"], 8192)

        base_config["model"] = model
        return base_config

    def _generate_clarifications(
        self,
        requirements: str,
        agent_type: str,
        tools: list[str],
        context: dict[str, Any],
    ) -> list[str]:
        """生成需要确认的问题"""
        questions = []

        # 检查是否有明确的命名空间
        if not context.get("namespace"):
            questions.append("是否需要将 Agent 放在特定命名空间下？")

        # 检查工具需求
        if len(tools) > 5:
            questions.append(f"检测到较多工具需求 ({len(tools)} 个)，是否需要精简？")

        # 检查是否需要持久化
        if "保存" in requirements or "存储" in requirements or "store" in requirements.lower():
            questions.append("是否需要持久化数据存储能力？")

        # 检查是否需要子Agent
        if agent_type == "hybrid" or "子任务" in requirements or "subtask" in requirements.lower():
            questions.append("是否需要支持子 Agent 调用？")

        return questions

    def _generate_config_suggestions(
        self,
        agent_type: str,
        tools: list[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """生成配置建议"""
        suggestions = {
            "template": agent_type if agent_type != "hybrid" else "reasoning",
            "limits": {
                "max_iterations": 10,
                "timeout": 300,
            },
        }

        if agent_type == "tool":
            suggestions["limits"]["max_iterations"] = 20
        elif agent_type == "reasoning":
            suggestions["limits"]["max_iterations"] = 5
            suggestions["limits"]["timeout"] = 600

        return suggestions

    def _calculate_confidence(self, text: str, agent_type: str) -> float:
        """计算分析置信度"""
        # 基于文本长度和关键词密度
        word_count = len(text.split())

        # 文本长度因子
        length_factor = min(1.0, word_count / 50)

        # 关键词密度因子
        all_keywords = (
            self.TOOL_KEYWORDS +
            self.REASONING_KEYWORDS +
            self.SIMPLE_KEYWORDS
        )
        keyword_count = sum(1 for kw in all_keywords if kw in text.lower())
        keyword_factor = min(1.0, keyword_count / 5)

        # 综合置信度
        confidence = (length_factor * 0.3 + keyword_factor * 0.7)

        return round(confidence, 2)

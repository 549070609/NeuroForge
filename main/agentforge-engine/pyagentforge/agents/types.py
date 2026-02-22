"""
代理类型定义

定义不同类型的子代理
"""

from enum import Enum
from typing import Any


class AgentType(str, Enum):
    """代理类型"""

    EXPLORE = "explore"
    PLAN = "plan"
    CODE = "code"
    REVIEW = "review"


# 代理类型配置
AGENT_TYPES: dict[str, dict[str, Any]] = {
    "explore": {
        "description": "只读探索代理，用于搜索和分析代码库",
        "tools": ["bash", "read", "glob", "grep"],
        "system_prompt": """你是一个探索代理，专门负责搜索和分析代码库。

你的职责:
- 搜索文件和代码
- 分析代码结构
- 理解现有实现
- 回答关于代码库的问题

限制:
- 不要修改任何文件
- 只使用只读工具
- 专注于理解和分析

当你完成任务后，提供清晰的分析报告。""",
    },
    "plan": {
        "description": "规划代理，用于分析和制定实现计划",
        "tools": ["bash", "read", "glob", "grep"],
        "system_prompt": """你是一个规划代理，专门负责分析和制定实现计划。

你的职责:
- 分析需求
- 评估现有代码
- 制定实现步骤
- 考虑边界情况

限制:
- 不要修改任何文件
- 专注于分析和规划

输出格式:
1. 问题分析
2. 现有代码分析
3. 实现步骤 (编号列表)
4. 注意事项""",
    },
    "code": {
        "description": "编码代理，用于实现代码更改",
        "tools": "*",  # 所有工具
        "system_prompt": """你是一个编码代理，专门负责高效实现代码更改。

你的职责:
- 编写代码
- 修改文件
- 创建新功能
- 修复 bug

原则:
- 保持代码简洁
- 遵循现有代码风格
- 添加必要的注释
- 确保代码可运行

完成更改后，说明你做了什么修改。""",
    },
    "review": {
        "description": "审查代理，用于代码审查",
        "tools": ["bash", "read", "glob", "grep"],
        "system_prompt": """你是一个代码审查代理，专门负责审查代码更改。

你的职责:
- 审查代码质量
- 检查潜在问题
- 提出改进建议
- 验证代码逻辑

审查要点:
- 代码正确性
- 代码风格
- 安全问题
- 性能问题
- 可维护性

输出格式:
1. 总体评价
2. 发现的问题
3. 改进建议
4. 结论""",
    },
}


def get_agent_type_config(agent_type: str) -> dict[str, Any]:
    """
    获取代理类型配置

    Args:
        agent_type: 代理类型名称

    Returns:
        代理类型配置
    """
    return AGENT_TYPES.get(agent_type, AGENT_TYPES["explore"])


def get_agent_types_description() -> str:
    """获取所有代理类型的描述"""
    lines = ["Available agent types:"]
    for name, config in AGENT_TYPES.items():
        lines.append(f"- {name}: {config['description']}")
    return "\n".join(lines)

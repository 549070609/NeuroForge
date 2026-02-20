"""
Agent Metadata System

Defines agent types with rich metadata for intelligent delegation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal


class AgentCategory(str, Enum):
    """Agent category"""

    EXPLORATION = "exploration"  # Read-only code exploration
    PLANNING = "planning"  # Task planning and analysis
    CODING = "coding"  # Code implementation
    REVIEW = "review"  # Code review
    RESEARCH = "research"  # External documentation
    REASONING = "reasoning"  # Deep analysis


class AgentCost(str, Enum):
    """Agent cost tier"""

    FREE = "free"  # No API calls
    CHEAP = "cheap"  # Small/fast model
    MODERATE = "moderate"  # Standard model
    EXPENSIVE = "expensive"  # Large/slow model


@dataclass
class DelegationTrigger:
    """
    v4.0: Delegation Trigger

    Defines when and why to delegate to this agent.
    """

    domain: str  # 工作领域 (如 "Frontend UI/UX")
    trigger: str  # 何时委托 (如 "Visual changes only...")

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary"""
        return {
            "domain": self.domain,
            "trigger": self.trigger,
        }


@dataclass
class AgentMetadata:
    """
    Agent Metadata

    Rich metadata for agent selection and delegation.
    """

    name: str
    description: str
    category: AgentCategory
    cost: AgentCost = AgentCost.MODERATE
    tools: list[str] = field(default_factory=lambda: ["*"])  # * = all tools
    system_prompt: str = ""
    use_when: list[str] = field(default_factory=list)  # When to use this agent
    avoid_when: list[str] = field(default_factory=list)  # When to avoid
    key_trigger: str = ""  # Regex pattern for auto-selection
    model_preference: str = ""  # Preferred model
    max_tokens: int = 4096
    temperature: float = 1.0

    # Execution settings
    is_readonly: bool = False  # Can only read, not write
    supports_background: bool = True  # Can run in background
    max_concurrent: int = 3  # Max concurrent instances

    # v4.0: 增强字段
    triggers: list[DelegationTrigger] = field(default_factory=list)
    dedicated_section: str | None = None  # 专用上下文区域
    prompt_alias: str | None = None  # 提示别名
    is_unstable_agent: bool = False  # 是否不稳定（需要后台转换）
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    text_verbosity: Literal["low", "medium", "high"] = "medium"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "cost": self.cost.value,
            "tools": self.tools,
            "use_when": self.use_when,
            "avoid_when": self.avoid_when,
            "key_trigger": self.key_trigger,
            "model_preference": self.model_preference,
            "is_readonly": self.is_readonly,
            "supports_background": self.supports_background,
            "max_concurrent": self.max_concurrent,
            # v4.0: 新增字段
            "triggers": [t.to_dict() for t in self.triggers],
            "dedicated_section": self.dedicated_section,
            "prompt_alias": self.prompt_alias,
            "is_unstable_agent": self.is_unstable_agent,
            "reasoning_effort": self.reasoning_effort,
            "text_verbosity": self.text_verbosity,
        }


# Built-in Agent Definitions
BUILTIN_AGENTS: dict[str, AgentMetadata] = {
    "explore": AgentMetadata(
        name="explore",
        description="Contextual grep agent for searching and analyzing codebases",
        category=AgentCategory.EXPLORATION,
        cost=AgentCost.FREE,
        tools=["bash", "read", "glob", "grep"],
        system_prompt="""你是一个探索代理，专门负责搜索和分析代码库。

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
        use_when=[
            "Need to understand existing code",
            "Searching for specific patterns",
            "Analyzing codebase structure",
            "Finding files or definitions",
        ],
        avoid_when=[
            "Writing new code",
            "Modifying existing files",
            "Making decisions",
        ],
        key_trigger=r"\b(search|find|explore|grep|analyze|understand)\b",
        is_readonly=True,
        supports_background=True,
        max_concurrent=5,
    ),
    "plan": AgentMetadata(
        name="plan",
        description="Task planning agent for analyzing requirements and creating implementation plans",
        category=AgentCategory.PLANNING,
        cost=AgentCost.CHEAP,
        tools=["bash", "read", "glob", "grep"],
        system_prompt="""你是一个规划代理，专门负责分析和制定实现计划。

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
        use_when=[
            "Planning new features",
            "Breaking down complex tasks",
            "Analyzing requirements",
            "Creating implementation roadmap",
        ],
        avoid_when=[
            "Executing implementation",
            "Writing code directly",
        ],
        key_trigger=r"\b(plan|design|architect|analyze|breakdown)\b",
        is_readonly=True,
        supports_background=False,
        max_concurrent=1,
    ),
    "code": AgentMetadata(
        name="code",
        description="Full implementation agent for writing and modifying code",
        category=AgentCategory.CODING,
        cost=AgentCost.EXPENSIVE,
        tools=["*"],  # All tools
        system_prompt="""你是一个编码代理，专门负责高效实现代码更改。

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
        use_when=[
            "Implementing new features",
            "Writing code",
            "Fixing bugs",
            "Refactoring code",
        ],
        avoid_when=[
            "Just exploring codebase",
            "Planning only",
        ],
        key_trigger=r"\b(implement|write|create|fix|code|develop)\b",
        is_readonly=False,
        supports_background=True,
        max_concurrent=2,
    ),
    "review": AgentMetadata(
        name="review",
        description="Code review agent for analyzing code quality",
        category=AgentCategory.REVIEW,
        cost=AgentCost.CHEAP,
        tools=["bash", "read", "glob", "grep"],
        system_prompt="""你是一个代码审查代理，专门负责审查代码更改。

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
        use_when=[
            "Reviewing code changes",
            "Checking code quality",
            "Finding potential issues",
        ],
        avoid_when=[
            "Writing code",
            "Making changes",
        ],
        key_trigger=r"\b(review|check|audit|verify)\b",
        is_readonly=True,
        supports_background=True,
        max_concurrent=3,
    ),
    "librarian": AgentMetadata(
        name="librarian",
        description="External documentation agent for fetching and summarizing documentation",
        category=AgentCategory.RESEARCH,
        cost=AgentCost.FREE,
        tools=["webfetch", "read"],
        system_prompt="""你是一个文档代理，专门负责获取和总结外部文档。

你的职责:
- 获取外部文档
- 总结关键信息
- 提供相关代码示例
- 回答技术问题

输出格式:
1. 文档摘要
2. 关键要点
3. 代码示例（如有）
4. 相关链接""",
        use_when=[
            "Fetching external documentation",
            "Looking up API references",
            "Researching libraries",
        ],
        avoid_when=[
            "Modifying code",
            "Making implementation decisions",
        ],
        key_trigger=r"\b(docs|documentation|api|library|reference)\b",
        is_readonly=True,
        supports_background=True,
        max_concurrent=5,
    ),
    "oracle": AgentMetadata(
        name="oracle",
        description="Architecture advisor for deep reasoning and design decisions",
        category=AgentCategory.REASONING,
        cost=AgentCost.EXPENSIVE,
        tools=["bash", "read", "glob", "grep"],
        system_prompt="""你是一个架构顾问代理，专门负责深度分析和设计决策。

你的职责:
- 分析架构设计
- 提供设计建议
- 评估技术选型
- 解决复杂问题

输出格式:
1. 问题分析
2. 设计考虑
3. 推荐方案
4. 实施建议
5. 潜在风险""",
        use_when=[
            "Making architectural decisions",
            "Deep analysis required",
            "Complex design problems",
            "Technical guidance needed",
        ],
        avoid_when=[
            "Simple code changes",
            "Routine tasks",
        ],
        key_trigger=r"\b(architecture|design|consult|advice|reasoning)\b",
        is_readonly=True,
        supports_background=False,
        max_concurrent=1,
    ),
}


def get_agent_metadata(agent_name: str) -> AgentMetadata | None:
    """
    Get agent metadata by name

    Args:
        agent_name: Agent name

    Returns:
        AgentMetadata or None
    """
    return BUILTIN_AGENTS.get(agent_name)


def get_agents_by_category(category: AgentCategory) -> list[AgentMetadata]:
    """
    Get all agents in a category

    Args:
        category: Agent category

    Returns:
        List of agent metadata
    """
    return [agent for agent in BUILTIN_AGENTS.values() if agent.category == category]


def get_agents_by_cost(cost: AgentCost) -> list[AgentMetadata]:
    """
    Get all agents by cost tier

    Args:
        cost: Cost tier

    Returns:
        List of agent metadata
    """
    return [agent for agent in BUILTIN_AGENTS.values() if agent.cost == cost]


def get_readonly_agents() -> list[AgentMetadata]:
    """Get all read-only agents"""
    return [agent for agent in BUILTIN_AGENTS.values() if agent.is_readonly]


def get_background_capable_agents() -> list[AgentMetadata]:
    """Get all agents that can run in background"""
    return [agent for agent in BUILTIN_AGENTS.values() if agent.supports_background]


def get_agent_selection_table() -> str:
    """
    Generate a table of agents for display

    Returns:
        Formatted table string
    """
    lines = [
        "| Agent | Category | Cost | Description |",
        "|-------|----------|------|-------------|",
    ]

    for name, agent in BUILTIN_AGENTS.items():
        lines.append(
            f"| {name} | {agent.category.value} | {agent.cost.value} | {agent.description[:50]}... |"
        )

    return "\n".join(lines)

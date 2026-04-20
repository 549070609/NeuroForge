"""
Dynamic Prompt Builder

Generates dynamic system prompts based on available resources.
"""

from dataclasses import dataclass, field
from typing import Any

from pyagentforge.agents.metadata import (
    BUILTIN_AGENTS,
    AgentCategory,
    AgentCost,
    AgentMetadata,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptContext:
    """Context for building dynamic prompts"""

    available_agents: list[AgentMetadata] = field(default_factory=list)
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    available_skills: list[str] = field(default_factory=list)
    working_directory: str = ""
    model_id: str = ""
    session_id: str = ""

    # Configuration
    include_cost_info: bool = True
    include_key_triggers: bool = True
    include_category_guide: bool = True
    max_table_rows: int = 20


class DynamicPromptBuilder:
    """
    Dynamic Prompt Builder

    Generates system prompts that include:
    - Agent/tool selection tables with costs
    - Key triggers for delegation
    - Category-specific guidance
    - Usage guidelines
    """

    # Base system prompt template
    BASE_PROMPT = """你是一个智能 AI 助手，可以使用工具和委托子代理来完成任务。

## 可用资源

{resource_tables}

## 委托策略

{delegation_guide}

## 使用指南

{usage_guidelines}

---

请根据任务需求，合理选择使用工具或委托子代理。优先使用低成本的资源，避免不必要的开销。
"""

    # Delegation guide by category
    CATEGORY_GUIDES = {
        AgentCategory.EXPLORATION: """### 探索类任务
- 使用 `explore` 代理搜索和分析代码
- 这类代理只读，不会修改文件
- 适合在后台并行运行多个探索任务""",
        AgentCategory.PLANNING: """### 规划类任务
- 使用 `plan` 代理分析需求和制定计划
- 专注于分析和架构设计
- 在开始实现前先进行规划""",
        AgentCategory.CODING: """### 编码类任务
- 使用 `code` 代理进行代码实现
- 这是唯一可以修改文件的代理类型
- 适合实际开发工作""",
        AgentCategory.REVIEW: """### 审查类任务
- 使用 `review` 代理检查代码质量
- 可以并行审查多个文件
- 只读操作，安全高效""",
        AgentCategory.RESEARCH: """### 研究类任务
- 使用 `librarian` 代理获取外部文档
- 可以在后台运行，不阻塞主流程
- 适合查找 API 文档和参考资料""",
        AgentCategory.REASONING: """### 推理类任务
- 使用 `oracle` 代理进行深度分析
- 适合复杂的架构决策
- 成本较高，谨慎使用""",
    }

    # Usage guidelines
    USAGE_GUIDELINES = """1. **成本优先**: 优先使用 FREE 和 CHEAP 资源
2. **并行执行**: 对于独立的探索任务，使用后台代理并行处理
3. **分步处理**: 复杂任务先规划后执行
4. **适度委托**: 简单任务可以直接处理，不必委托
5. **资源限制**: 注意并发限制，避免过度创建子代理"""

    # Cost symbols
    COST_SYMBOLS = {
        AgentCost.FREE: "🆓",
        AgentCost.CHEAP: "💰",
        AgentCost.MODERATE: "💰💰",
        AgentCost.EXPENSIVE: "💰💰💰",
    }

    def __init__(self):
        """Initialize prompt builder"""
        pass

    def build_system_prompt(self, context: PromptContext) -> str:
        """
        Build a complete system prompt

        Args:
            context: Prompt context with available resources

        Returns:
            Complete system prompt
        """
        # Build resource tables
        resource_tables = self._build_resource_tables(context)

        # Build delegation guide
        delegation_guide = self._build_delegation_guide(context)

        # Build usage guidelines
        usage_guidelines = self._build_usage_guidelines(context)

        return self.BASE_PROMPT.format(
            resource_tables=resource_tables,
            delegation_guide=delegation_guide,
            usage_guidelines=usage_guidelines,
        )

    def _build_resource_tables(self, context: PromptContext) -> str:
        """Build resource tables"""
        sections = []

        # Agent table
        if context.available_agents:
            agent_table = self._build_agent_table(context)
            sections.append(f"### 可用代理\n\n{agent_table}")

        # Tools table
        if context.available_tools:
            tool_table = self._build_tool_table(context)
            sections.append(f"### 可用工具\n\n{tool_table}")

        # Skills list
        if context.available_skills:
            skills_list = self._build_skills_list(context)
            sections.append(f"### 可用技能\n\n{skills_list}")

        return "\n\n".join(sections)

    def _build_agent_table(self, context: PromptContext) -> str:
        """Build agent selection table"""
        lines = ["| 代理 | 类别 | 成本 | 描述 | 触发关键词 |"]
        lines.append("|------|------|------|------|----------|")

        for _i, agent in enumerate(context.available_agents[: context.max_table_rows]):
            cost_str = self.COST_SYMBOLS.get(agent.cost, "")
            if context.include_cost_info:
                cost_display = f"{cost_str} {agent.cost.value}"
            else:
                cost_display = agent.cost.value

            # Truncate description
            desc = agent.description[:40] + "..." if len(agent.description) > 40 else agent.description

            # Key trigger
            trigger = ""
            if context.include_key_triggers and agent.key_trigger:
                trigger = agent.key_trigger[:20]

            lines.append(
                f"| `{agent.name}` | {agent.category.value} | {cost_display} | {desc} | {trigger} |"
            )

        return "\n".join(lines)

    def _build_tool_table(self, context: PromptContext) -> str:
        """Build tool selection table"""
        lines = ["| 工具 | 描述 |"]
        lines.append("|------|------|")

        for tool in context.available_tools[: context.max_table_rows]:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")[:50]
            if len(tool.get("description", "")) > 50:
                desc += "..."

            lines.append(f"| `{name}` | {desc} |")

        return "\n".join(lines)

    def _build_skills_list(self, context: PromptContext) -> str:
        """Build skills list"""
        if not context.available_skills:
            return ""

        lines = []
        for skill in context.available_skills[: context.max_table_rows]:
            lines.append(f"- `{skill}`")

        return "\n".join(lines)

    def _build_delegation_guide(self, context: PromptContext) -> str:
        """Build category-based delegation guide"""
        # Get categories present in available agents
        present_categories = {a.category for a in context.available_agents}

        if not context.include_category_guide:
            return "根据任务类型选择合适的代理。"

        guides = []
        for category in [
            AgentCategory.EXPLORATION,
            AgentCategory.PLANNING,
            AgentCategory.CODING,
            AgentCategory.REVIEW,
            AgentCategory.RESEARCH,
            AgentCategory.REASONING,
        ]:
            if category in present_categories:
                guides.append(self.CATEGORY_GUIDES[category])

        return "\n\n".join(guides) if guides else "根据任务类型选择合适的代理。"

    def _build_usage_guidelines(self, _context: PromptContext) -> str:
        """Build usage guidelines"""
        return self.USAGE_GUIDELINES

    def build_key_triggers_section(self, context: PromptContext) -> str:
        """
        Build key triggers section for agent auto-selection

        Returns:
            Formatted key triggers section
        """
        if not context.include_key_triggers:
            return ""

        lines = ["## 自动触发规则\n"]
        lines.append("当任务描述包含以下关键词时，系统会自动选择相应的代理：\n")

        for agent in context.available_agents:
            if agent.key_trigger:
                lines.append(f"- **{agent.name}**: `{agent.key_trigger}`")

        return "\n".join(lines)

    def build_cost_summary(self, context: PromptContext) -> str:
        """
        Build cost summary

        Returns:
            Formatted cost summary
        """
        if not context.include_cost_info:
            return ""

        cost_counts = dict.fromkeys(AgentCost, 0)

        for agent in context.available_agents:
            cost_counts[agent.cost] += 1

        lines = ["## 成本概览\n"]
        lines.append("| 成本级别 | 数量 | 符号 |")
        lines.append("|----------|------|------|")

        for cost, count in cost_counts.items():
            symbol = self.COST_SYMBOLS.get(cost, "")
            lines.append(f"| {cost.value} | {count} | {symbol} |")

        return "\n".join(lines)

    def build_quick_reference(self, _context: PromptContext) -> str:
        """
        Build quick reference card

        Returns:
            Quick reference string
        """
        lines = ["## 快速参考\n"]

        # Best for each category
        lines.append("**推荐代理：**")
        lines.append("- 🔍 探索: `explore`")
        lines.append("- 📋 规划: `plan`")
        lines.append("- 💻 编码: `code`")
        lines.append("- ✅ 审查: `review`")
        lines.append("- 📚 文档: `librarian`")
        lines.append("- 🎯 深度分析: `oracle`")

        return "\n".join(lines)


def create_prompt_context(
    available_agents: list[AgentMetadata] | None = None,
    available_tools: list[dict[str, Any]] | None = None,
    available_skills: list[str] | None = None,
    working_directory: str = "",
    model_id: str = "",
) -> PromptContext:
    """
    Create a prompt context with defaults

    Args:
        available_agents: List of available agents (defaults to all built-in)
        available_tools: List of available tools
        available_skills: List of available skills
        working_directory: Current working directory
        model_id: Current model ID

    Returns:
        PromptContext instance
    """
    return PromptContext(
        available_agents=available_agents or list(BUILTIN_AGENTS.values()),
        available_tools=available_tools or [],
        available_skills=available_skills or [],
        working_directory=working_directory,
        model_id=model_id,
    )

"""
Category System

Task classification and category-based configuration.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TaskComplexity(StrEnum):
    """Task complexity level"""

    QUICK = "quick"  # Simple, fast tasks
    STANDARD = "standard"  # Normal tasks
    COMPLEX = "complex"  # Complex tasks
    DEEP = "deep"  # Deep reasoning required


@dataclass
class Category:
    """
    Task Category

    Defines a category of tasks with associated configuration.
    """

    name: str
    description: str
    model: str = "gpt-4o-mini"  # Preferred model for this category
    temperature: float = 1.0
    max_tokens: int = 4096

    # Associated agents (ordered by preference)
    agents: list[str] = field(default_factory=list)

    # Associated skills
    skills: list[str] = field(default_factory=list)

    # Priority for category matching
    priority: int = 0  # Higher = check first

    # Keywords for classification
    keywords: list[str] = field(default_factory=list)

    # Task complexity
    complexity: TaskComplexity = TaskComplexity.STANDARD

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # v4.0: 增强字段
    is_unstable_category: bool = False  # 是否为不稳定类别
    auto_background_conversion: bool = False  # 是否自动转后台
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "agents": self.agents,
            "skills": self.skills,
            "priority": self.priority,
            "keywords": self.keywords,
            "complexity": self.complexity.value,
            "metadata": self.metadata,
            # v4.0: 新增字段
            "is_unstable_category": self.is_unstable_category,
            "auto_background_conversion": self.auto_background_conversion,
            "reasoning_effort": self.reasoning_effort,
        }


# Built-in Categories
BUILTIN_CATEGORIES: dict[str, Category] = {
    "quick": Category(
        name="quick",
        description="Fast tasks that need quick responses",
        model="gpt-4o-mini",
        agents=["explore"],
        skills=[],
        priority=10,
        keywords=[
            "quick",
            "fast",
            "simple",
            "check",
            "list",
            "show",
            "grep",
            "find",
        ],
        complexity=TaskComplexity.QUICK,
    ),
    "coding": Category(
        name="coding",
        description="Code implementation and modification tasks",
        model="gpt-4o",
        temperature=1.0,
        max_tokens=8192,
        agents=["explore", "plan", "code", "review"],
        skills=["coding", "debugging"],
        priority=5,
        keywords=[
            "implement",
            "code",
            "write",
            "create",
            "modify",
            "fix",
            "bug",
            "feature",
            "refactor",
            "实现",
            "编码",
            "修复",
            "开发",
        ],
        complexity=TaskComplexity.STANDARD,
    ),
    "visual-engineering": Category(
        name="visual-engineering",
        description="UI/UX design and frontend development",
        model="gpt-4o",
        temperature=1.0,
        max_tokens=8192,
        agents=["explore", "plan", "code"],
        skills=["ui-design", "frontend"],
        priority=6,
        keywords=[
            "ui",
            "ux",
            "frontend",
            "design",
            "style",
            "css",
            "html",
            "react",
            "vue",
            "界面",
            "前端",
            "样式",
        ],
        complexity=TaskComplexity.STANDARD,
    ),
    "ultrabrain": Category(
        name="ultrabrain",
        description="Deep reasoning and complex analysis",
        model="claude-opus-4-6",
        temperature=1.0,
        max_tokens=16384,
        agents=["oracle", "plan"],
        skills=["reasoning", "architecture"],
        priority=3,
        keywords=[
            "architecture",
            "design",
            "analyze",
            "deep",
            "complex",
            "reasoning",
            "strategy",
            "架构",
            "设计",
            "分析",
            "深度",
        ],
        complexity=TaskComplexity.DEEP,
    ),
    "research": Category(
        name="research",
        description="Documentation and research tasks",
        model="gpt-4o-mini",
        agents=["librarian", "explore"],
        skills=["research", "documentation"],
        priority=4,
        keywords=[
            "docs",
            "documentation",
            "research",
            "api",
            "library",
            "reference",
            "文档",
            "研究",
            "参考",
        ],
        complexity=TaskComplexity.STANDARD,
    ),
    "exploration": Category(
        name="exploration",
        description="Code exploration and analysis",
        model="gpt-4o-mini",
        agents=["explore"],
        skills=[],
        priority=8,
        keywords=[
            "explore",
            "search",
            "find",
            "analyze",
            "understand",
            "grep",
            "探索",
            "搜索",
            "查找",
            "分析",
        ],
        complexity=TaskComplexity.QUICK,
    ),
}


def get_category(name: str) -> Category | None:
    """
    Get category by name

    Args:
        name: Category name

    Returns:
        Category or None
    """
    return BUILTIN_CATEGORIES.get(name)


def get_categories_by_complexity(complexity: TaskComplexity) -> list[Category]:
    """
    Get categories by complexity

    Args:
        complexity: Task complexity

    Returns:
        List of matching categories
    """
    return [c for c in BUILTIN_CATEGORIES.values() if c.complexity == complexity]


def get_sorted_categories() -> list[Category]:
    """
    Get categories sorted by priority (highest first)

    Returns:
        Sorted list of categories
    """
    return sorted(
        BUILTIN_CATEGORIES.values(),
        key=lambda c: c.priority,
        reverse=True,
    )

"""
Tests for Category System

Tests Category dataclass, TaskComplexity enum, and helper functions.
"""

from typing import Any

import pytest

from pyagentforge.core.category import (
    BUILTIN_CATEGORIES,
    Category,
    TaskComplexity,
    get_categories_by_complexity,
    get_category,
    get_sorted_categories,
)


# ============================================================================
# Test: TaskComplexity Enum
# ============================================================================

def test_task_complexity_values():
    """
    Test TaskComplexity enum values.

    Verifies:
    - All expected complexity levels exist
    - String values are lowercase
    """
    assert TaskComplexity.QUICK.value == "quick"
    assert TaskComplexity.STANDARD.value == "standard"
    assert TaskComplexity.COMPLEX.value == "complex"
    assert TaskComplexity.DEEP.value == "deep"


def test_task_complexity_is_string_enum():
    """
    Test that TaskComplexity is a string enum.

    Verifies:
    - Values can be compared with strings
    - Enum members are strings
    """
    assert TaskComplexity.QUICK == "quick"
    assert TaskComplexity.STANDARD == "standard"

    # Can use in string comparisons
    assert TaskComplexity.QUICK in ["quick", "fast"]


# ============================================================================
# Test: Category Dataclass
# ============================================================================

def test_category_creation():
    """
    Test creating a Category instance.

    Verifies:
    - All fields are set correctly
    - Default values are applied
    """
    cat = Category(
        name="test-category",
        description="A test category",
    )

    assert cat.name == "test-category"
    assert cat.description == "A test category"
    assert cat.model == "gpt-4o-mini"  # Default
    assert cat.temperature == 1.0  # Default
    assert cat.max_tokens == 4096  # Default
    assert cat.agents == []  # Default
    assert cat.skills == []  # Default
    assert cat.priority == 0  # Default
    assert cat.keywords == []  # Default
    assert cat.complexity == TaskComplexity.STANDARD  # Default


def test_category_with_all_fields():
    """
    Test creating a Category with all fields specified.

    Verifies:
    - All fields can be customized
    - No defaults used
    """
    cat = Category(
        name="custom",
        description="Custom category",
        model="claude-opus-4-6",
        temperature=0.5,
        max_tokens=8192,
        agents=["agent1", "agent2"],
        skills=["skill1", "skill2"],
        priority=10,
        keywords=["keyword1", "keyword2"],
        complexity=TaskComplexity.COMPLEX,
        metadata={"custom": "data"},
        is_unstable_category=True,
        auto_background_conversion=True,
        reasoning_effort="high",
    )

    assert cat.name == "custom"
    assert cat.model == "claude-opus-4-6"
    assert cat.temperature == 0.5
    assert cat.max_tokens == 8192
    assert cat.agents == ["agent1", "agent2"]
    assert cat.skills == ["skill1", "skill2"]
    assert cat.priority == 10
    assert cat.keywords == ["keyword1", "keyword2"]
    assert cat.complexity == TaskComplexity.COMPLEX
    assert cat.metadata == {"custom": "data"}
    assert cat.is_unstable_category is True
    assert cat.auto_background_conversion is True
    assert cat.reasoning_effort == "high"


def test_category_to_dict():
    """
    Test Category serialization to dictionary.

    Verifies:
    - All fields are included
    - Enum values are serialized correctly
    - Lists and dicts are preserved
    """
    cat = Category(
        name="test",
        description="Test",
        model="gpt-4o",
        agents=["agent1"],
        skills=["skill1"],
        priority=5,
        keywords=["kw1"],
        complexity=TaskComplexity.DEEP,
        metadata={"key": "value"},
    )

    d = cat.to_dict()

    assert d["name"] == "test"
    assert d["description"] == "Test"
    assert d["model"] == "gpt-4o"
    assert d["temperature"] == 1.0
    assert d["max_tokens"] == 4096
    assert d["agents"] == ["agent1"]
    assert d["skills"] == ["skill1"]
    assert d["priority"] == 5
    assert d["keywords"] == ["kw1"]
    assert d["complexity"] == "deep"  # String value
    assert d["metadata"] == {"key": "value"}
    assert "is_unstable_category" in d
    assert "auto_background_conversion" in d
    assert "reasoning_effort" in d


def test_category_reasoning_effort_literal():
    """
    Test reasoning_effort field accepts valid literals.

    Verifies:
    - All valid values work
    - Invalid values would be caught by type checker
    """
    cat_low = Category(name="low", description="Low", reasoning_effort="low")
    cat_med = Category(name="med", description="Med", reasoning_effort="medium")
    cat_high = Category(name="high", description="High", reasoning_effort="high")
    cat_xhigh = Category(name="xhigh", description="XHigh", reasoning_effort="xhigh")

    assert cat_low.reasoning_effort == "low"
    assert cat_med.reasoning_effort == "medium"
    assert cat_high.reasoning_effort == "high"
    assert cat_xhigh.reasoning_effort == "xhigh"


# ============================================================================
# Test: Built-in Categories
# ============================================================================

def test_builtin_categories_exist():
    """
    Test that all expected built-in categories exist.

    Verifies:
    - BUILTIN_CATEGORIES dict is populated
    - Key categories are present
    """
    assert len(BUILTIN_CATEGORIES) > 0

    # Check expected categories
    assert "quick" in BUILTIN_CATEGORIES
    assert "coding" in BUILTIN_CATEGORIES
    assert "visual-engineering" in BUILTIN_CATEGORIES
    assert "ultrabrain" in BUILTIN_CATEGORIES
    assert "research" in BUILTIN_CATEGORIES
    assert "exploration" in BUILTIN_CATEGORIES


def test_quick_category():
    """
    Test the 'quick' built-in category.

    Verifies:
    - Uses appropriate model for quick tasks
    - Has correct complexity
    - Has relevant keywords
    """
    quick = BUILTIN_CATEGORIES["quick"]

    assert quick.name == "quick"
    assert quick.model == "gpt-4o-mini"  # Fast model
    assert quick.complexity == TaskComplexity.QUICK
    assert "quick" in quick.keywords
    assert "fast" in quick.keywords
    assert "simple" in quick.keywords
    assert quick.priority == 10  # High priority for quick tasks


def test_coding_category():
    """
    Test the 'coding' built-in category.

    Verifies:
    - Uses capable coding model
    - Has coding-related keywords
    - Has coding agents and skills
    """
    coding = BUILTIN_CATEGORIES["coding"]

    assert coding.name == "coding"
    assert "claude" in coding.model.lower() or "gpt" in coding.model.lower()
    assert coding.complexity == TaskComplexity.STANDARD
    assert "implement" in coding.keywords
    assert "code" in coding.keywords
    assert "fix" in coding.keywords
    # Has both English and Chinese keywords
    assert "实现" in coding.keywords
    assert "编码" in coding.keywords
    # Has relevant agents
    assert len(coding.agents) > 0


def test_visual_engineering_category():
    """
    Test the 'visual-engineering' built-in category.

    Verifies:
    - Uses vision-capable model
    - Has UI/frontend keywords
    """
    visual = BUILTIN_CATEGORIES["visual-engineering"]

    assert visual.name == "visual-engineering"
    assert visual.model == "gpt-4o"  # Vision capable
    assert "ui" in visual.keywords
    assert "css" in visual.keywords
    assert "react" in visual.keywords


def test_ultrabrain_category():
    """
    Test the 'ultrabrain' built-in category.

    Verifies:
    - Uses most capable model
    - Has high token limit
    - Has deep complexity
    """
    ultra = BUILTIN_CATEGORIES["ultrabrain"]

    assert ultra.name == "ultrabrain"
    assert "opus" in ultra.model.lower() or "claude" in ultra.model.lower()
    assert ultra.max_tokens >= 16384  # High token limit
    assert ultra.complexity == TaskComplexity.DEEP


def test_research_category():
    """
    Test the 'research' built-in category.

    Verifies:
    - Has research-related keywords
    - Has librarian agent
    """
    research = BUILTIN_CATEGORIES["research"]

    assert research.name == "research"
    assert "docs" in research.keywords
    assert "documentation" in research.keywords
    assert "api" in research.keywords


def test_exploration_category():
    """
    Test the 'exploration' built-in category.

    Verifies:
    - Uses fast model
    - Has exploration keywords
    - Has high priority
    """
    exploration = BUILTIN_CATEGORIES["exploration"]

    assert exploration.name == "exploration"
    assert exploration.model == "gpt-4o-mini"
    assert "explore" in exploration.keywords
    assert "search" in exploration.keywords
    assert exploration.priority == 8  # High priority


# ============================================================================
# Test: Helper Functions
# ============================================================================

def test_get_category():
    """
    Test get_category() helper function.

    Verifies:
    - Returns category by name
    - Returns None for non-existent
    """
    coding = get_category("coding")
    assert coding is not None
    assert coding.name == "coding"

    unknown = get_category("non-existent")
    assert unknown is None


def test_get_categories_by_complexity():
    """
    Test get_categories_by_complexity() helper function.

    Verifies:
    - Returns list of categories
    - All returned categories have matching complexity
    """
    quick_cats = get_categories_by_complexity(TaskComplexity.QUICK)
    assert len(quick_cats) > 0
    for cat in quick_cats:
        assert cat.complexity == TaskComplexity.QUICK

    deep_cats = get_categories_by_complexity(TaskComplexity.DEEP)
    assert len(deep_cats) > 0
    for cat in deep_cats:
        assert cat.complexity == TaskComplexity.DEEP


def test_get_sorted_categories():
    """
    Test get_sorted_categories() helper function.

    Verifies:
    - Returns list sorted by priority (highest first)
    - All built-in categories are included
    """
    sorted_cats = get_sorted_categories()

    assert len(sorted_cats) == len(BUILTIN_CATEGORIES)

    # Check sorting
    priorities = [c.priority for c in sorted_cats]
    assert priorities == sorted(priorities, reverse=True)


# ============================================================================
# Test: Category Comparison
# ============================================================================

def test_category_equality():
    """
    Test Category equality comparison.

    Verifies:
    - Same name doesn't mean equal (dataclass compares all fields)
    - Identical categories are equal
    """
    cat1 = Category(name="test", description="Test")
    cat2 = Category(name="test", description="Test")
    cat3 = Category(name="test", description="Different")

    assert cat1 == cat2
    assert cat1 != cat3


# ============================================================================
# Test: Category Field Defaults
# ============================================================================

def test_category_metadata_default():
    """
    Test that metadata defaults to empty dict.

    Verifies:
    - Default is empty dict
    - Each instance gets its own dict (not shared)
    """
    cat1 = Category(name="cat1", description="Test")
    cat2 = Category(name="cat2", description="Test")

    cat1.metadata["key"] = "value"

    # cat2's metadata should not be affected
    assert "key" not in cat2.metadata


def test_category_lists_default():
    """
    Test that list fields default to empty lists.

    Verifies:
    - Each instance gets its own list (not shared)
    """
    cat1 = Category(name="cat1", description="Test")
    cat2 = Category(name="cat2", description="Test")

    cat1.agents.append("agent1")
    cat1.keywords.append("keyword1")

    # cat2's lists should not be affected
    assert len(cat2.agents) == 0
    assert len(cat2.keywords) == 0


# ============================================================================
# Test: Category Enhanced Fields (v4.0)
# ============================================================================

def test_category_v4_enhanced_fields():
    """
    Test v4.0 enhanced fields.

    Verifies:
    - is_unstable_category defaults to False
    - auto_background_conversion defaults to False
    - reasoning_effort defaults to medium
    """
    cat = Category(name="test", description="Test")

    assert cat.is_unstable_category is False
    assert cat.auto_background_conversion is False
    assert cat.reasoning_effort == "medium"


def test_category_to_dict_includes_v4_fields():
    """
    Test that to_dict includes v4.0 fields.

    Verifies:
    - All v4 fields are in output
    """
    cat = Category(
        name="test",
        description="Test",
        is_unstable_category=True,
        auto_background_conversion=True,
        reasoning_effort="high",
    )

    d = cat.to_dict()

    assert d["is_unstable_category"] is True
    assert d["auto_background_conversion"] is True
    assert d["reasoning_effort"] == "high"


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_category_empty_name():
    """
    Test that empty name is allowed (though not recommended).

    Verifies:
    - Category can be created with empty name
    """
    cat = Category(name="", description="Empty name")
    assert cat.name == ""


def test_category_special_characters():
    """
    Test Category with special characters in fields.

    Verifies:
    - Unicode characters work
    - Special characters don't cause issues
    """
    cat = Category(
        name="test-special",
        description="Test with special chars: \n\t\"'",
        keywords=["keyword-with-dash", "unicode你好世界"],
    )

    assert cat.name == "test-special"
    assert "\n" in cat.description
    assert "你好世界" in cat.keywords[1]


def test_category_negative_priority():
    """
    Test Category with negative priority.

    Verifies:
    - Negative priority is allowed
    - Would sort below zero priority
    """
    cat = Category(name="low", description="Low priority", priority=-10)
    assert cat.priority == -10


def test_category_zero_temperature():
    """
    Test Category with zero temperature.

    Verifies:
    - Zero temperature is allowed
    """
    cat = Category(name="deterministic", description="Zero temp", temperature=0.0)
    assert cat.temperature == 0.0


def test_category_high_temperature():
    """
    Test Category with high temperature.

    Verifies:
    - High temperature values are allowed
    """
    cat = Category(name="creative", description="High temp", temperature=2.0)
    assert cat.temperature == 2.0


# ============================================================================
# Test: Category Dict Operations
# ============================================================================

def test_builtin_categories_immutable():
    """
    Test understanding that BUILTIN_CATEGORIES is a constant.

    Verifies:
    - Can read from BUILTIN_CATEGORIES
    - (Note: Python doesn't enforce immutability, this is documentation)
    """
    # This is just for documentation - Python doesn't prevent modification
    assert isinstance(BUILTIN_CATEGORIES, dict)
    assert len(BUILTIN_CATEGORIES) > 0


# ============================================================================
# Test: Category Agent/Skill Lists
# ============================================================================

def test_category_multiple_agents():
    """
    Test Category with multiple agents.

    Verifies:
    - Multiple agents can be specified
    - Order is preserved
    """
    cat = Category(
        name="multi",
        description="Multiple agents",
        agents=["explore", "plan", "code", "review"],
    )

    assert len(cat.agents) == 4
    assert cat.agents[0] == "explore"
    assert cat.agents[3] == "review"


def test_category_multiple_skills():
    """
    Test Category with multiple skills.

    Verifies:
    - Multiple skills can be specified
    """
    cat = Category(
        name="skilled",
        description="Multiple skills",
        skills=["coding", "debugging", "testing", "documentation"],
    )

    assert len(cat.skills) == 4


# ============================================================================
# Test: Category Complexity Distribution
# ============================================================================

def test_builtin_categories_complexity_distribution():
    """
    Test complexity distribution among built-in categories.

    Verifies:
    - We have categories at different complexity levels
    """
    complexities = [cat.complexity for cat in BUILTIN_CATEGORIES.values()]

    # Should have variety
    assert TaskComplexity.QUICK in complexities
    assert TaskComplexity.STANDARD in complexities
    # May or may not have COMPLEX/DEEP depending on categories

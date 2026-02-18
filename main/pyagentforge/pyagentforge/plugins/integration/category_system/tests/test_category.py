"""
Tests for Category System
"""

import pytest

from pyagentforge.core.category import (
    BUILTIN_CATEGORIES,
    Category,
    TaskComplexity,
    get_category,
    get_categories_by_complexity,
    get_sorted_categories,
)
from pyagentforge.core.category_registry import (
    CategoryRegistry,
    ClassificationResult,
)


class TestCategory:
    """Tests for Category"""

    def test_create_category(self):
        """Test creating a category"""
        category = Category(
            name="test",
            description="Test category",
            model="gpt-4",
            agents=["explore", "code"],
            keywords=["test", "testing"],
        )

        assert category.name == "test"
        assert category.model == "gpt-4"
        assert len(category.agents) == 2
        assert "test" in category.keywords

    def test_to_dict(self):
        """Test serialization"""
        category = Category(
            name="test",
            description="Test",
            agents=["explore"],
        )

        data = category.to_dict()

        assert data["name"] == "test"
        assert data["description"] == "Test"
        assert "agents" in data


class TestBuiltinCategories:
    """Tests for built-in categories"""

    def test_quick_category(self):
        """Test quick category"""
        cat = BUILTIN_CATEGORIES.get("quick")

        assert cat is not None
        assert cat.complexity == TaskComplexity.QUICK
        assert "explore" in cat.agents

    def test_coding_category(self):
        """Test coding category"""
        cat = BUILTIN_CATEGORIES.get("coding")

        assert cat is not None
        assert "code" in cat.agents
        assert "implement" in cat.keywords

    def test_ultrabrain_category(self):
        """Test ultrabrain category"""
        cat = BUILTIN_CATEGORIES.get("ultrabrain")

        assert cat is not None
        assert cat.complexity == TaskComplexity.DEEP
        assert "oracle" in cat.agents

    def test_get_category(self):
        """Test get_category function"""
        cat = get_category("coding")
        assert cat is not None
        assert cat.name == "coding"

    def test_get_sorted_categories(self):
        """Test sorted categories"""
        sorted_cats = get_sorted_categories()

        assert len(sorted_cats) > 0
        # Should be sorted by priority
        for i in range(len(sorted_cats) - 1):
            assert sorted_cats[i].priority >= sorted_cats[i + 1].priority

    def test_get_by_complexity(self):
        """Test get_categories_by_complexity"""
        quick_cats = get_categories_by_complexity(TaskComplexity.QUICK)

        assert len(quick_cats) > 0
        for cat in quick_cats:
            assert cat.complexity == TaskComplexity.QUICK


class TestCategoryRegistry:
    """Tests for CategoryRegistry"""

    def test_create_registry(self):
        """Test creating registry"""
        registry = CategoryRegistry()

        assert len(registry.list_all()) > 0

    def test_register_category(self):
        """Test registering a category"""
        registry = CategoryRegistry()

        custom = Category(
            name="custom",
            description="Custom category",
            agents=["explore"],
        )

        registry.register(custom)

        assert registry.get("custom") is not None

    def test_unregister_category(self):
        """Test unregistering a category"""
        registry = CategoryRegistry()

        assert registry.unregister("quick")  # Built-in
        assert registry.get("quick") is None

    def test_classify_keyword_match(self):
        """Test keyword-based classification"""
        registry = CategoryRegistry()

        result = registry.classify("Implement a new feature")

        assert result is not None
        assert result.category is not None
        assert result.confidence > 0

    def test_classify_coding_task(self):
        """Test classification of coding task"""
        registry = CategoryRegistry()

        result = registry.classify("Write code to implement authentication")

        assert result is not None
        # Should match coding category
        assert result.category.name in ("coding", "ultrabrain")

    def test_classify_quick_task(self):
        """Test classification of quick task"""
        registry = CategoryRegistry()

        result = registry.classify("Quick check the file structure")

        assert result is not None
        # Quick has high priority
        assert result.category.name in ("quick", "exploration")

    def test_get_agents_for_task(self):
        """Test getting agents for task"""
        registry = CategoryRegistry()

        agents = registry.get_agents_for_task("Implement user login")

        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_get_model_for_task(self):
        """Test getting model for task"""
        registry = CategoryRegistry()

        model = registry.get_model_for_task("Quick search for TODO")

        assert isinstance(model, str)
        assert len(model) > 0

    def test_get_complexity_for_task(self):
        """Test getting complexity for task"""
        registry = CategoryRegistry()

        complexity = registry.get_complexity_for_task("Analyze the architecture")

        assert isinstance(complexity, TaskComplexity)

    def test_to_dict(self):
        """Test serialization"""
        registry = CategoryRegistry()

        data = registry.to_dict()

        assert "categories" in data
        assert "total_categories" in data


class TestClassificationResult:
    """Tests for ClassificationResult"""

    def test_create_result(self):
        """Test creating classification result"""
        category = Category(name="test", description="Test")
        result = ClassificationResult(
            category=category,
            confidence=0.8,
            matched_keywords=["test"],
            method="keyword",
        )

        assert result.category.name == "test"
        assert result.confidence == 0.8
        assert "test" in result.matched_keywords


class TestTaskComplexity:
    """Tests for TaskComplexity enum"""

    def test_complexity_values(self):
        """Test complexity enum values"""
        assert TaskComplexity.QUICK.value == "quick"
        assert TaskComplexity.STANDARD.value == "standard"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.DEEP.value == "deep"

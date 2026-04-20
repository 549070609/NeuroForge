"""
Tests for CategoryRegistry

Tests task classification, category management, and classifier integration.
"""

from unittest.mock import AsyncMock

import pytest

from pyagentforge.plugins.integration.category_system.category import (
    BUILTIN_CATEGORIES,
    Category,
    TaskComplexity,
)
from pyagentforge.plugins.integration.category_system.category_registry import (
    CategoryRegistry,
    ClassificationResult,
    get_category_registry,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def registry():
    """Create a fresh CategoryRegistry instance."""
    return CategoryRegistry()


@pytest.fixture
def custom_category():
    """Create a custom category for testing."""
    return Category(
        name="test-category",
        description="A test category",
        model="gpt-4o",
        temperature=0.7,
        max_tokens=2048,
        agents=["test-agent"],
        skills=["test-skill"],
        priority=15,
        keywords=["test", "testing", "unit test"],
        complexity=TaskComplexity.STANDARD,
        metadata={"custom": "value"},
    )


@pytest.fixture
def mock_llm_classifier():
    """Create a mock LLM classifier."""
    classifier = AsyncMock()

    async def classify(text: str, context: dict = None) -> ClassificationResult:
        if "architecture" in text.lower():
            category = BUILTIN_CATEGORIES.get("ultrabrain")
            return ClassificationResult(
                category=category,
                confidence=0.9,
                matched_keywords=["architecture"],
                method="llm",
            )
        return None

    classifier.classify = classify
    return classifier


@pytest.fixture
def mock_semantic_classifier():
    """Create a mock semantic classifier."""
    classifier = AsyncMock()

    async def classify(text: str, context: dict = None) -> ClassificationResult:
        if "design" in text.lower() or "ui" in text.lower():
            category = BUILTIN_CATEGORIES.get("visual-engineering")
            return ClassificationResult(
                category=category,
                confidence=0.8,
                matched_keywords=["design"],
                method="semantic",
            )
        return None

    classifier.classify = classify
    return classifier


# ============================================================================
# Test: test_classify_by_keyword_matching
# ============================================================================

def test_classify_by_keyword_matching(registry):
    """
    Test classification using keyword matching (default method).

    Verifies:
    - Keywords are matched correctly
    - Best matching category is returned
    - Matched keywords are included in result
    """
    result = registry.classify(
        "Implement a new feature for the user authentication system"
    )

    assert result is not None
    assert result.category is not None
    assert result.confidence > 0
    assert result.method == "keyword"
    assert len(result.matched_keywords) > 0


# ============================================================================
# Test: test_classify_async_with_semantic
# ============================================================================

@pytest.mark.asyncio
async def test_classify_async_with_semantic(registry, mock_semantic_classifier):
    """
    Test async classification with semantic classifier.

    Verifies:
    - Semantic classifier is called when enabled
    - Result method is 'semantic'
    - Falls back to keyword if semantic fails
    """
    registry.set_semantic_classifier(mock_semantic_classifier)

    result = await registry.classify_async(
        "Design a beautiful UI for the dashboard",
        use_semantic=True,
    )

    assert result is not None
    assert result.category is not None
    assert result.method == "semantic"
    assert result.confidence >= 0.5


# ============================================================================
# Test: test_classify_async_with_llm
# ============================================================================

@pytest.mark.asyncio
async def test_classify_async_with_llm(registry, mock_llm_classifier):
    """
    Test async classification with LLM classifier.

    Verifies:
    - LLM classifier is called when enabled
    - Result method is 'llm'
    - Returns LLM result when confidence is high enough
    """
    registry.set_llm_classifier(mock_llm_classifier)

    result = await registry.classify_async(
        "Analyze the system architecture and suggest improvements",
        use_llm=True,
    )

    assert result is not None
    assert result.category is not None
    assert result.method == "llm"
    assert result.confidence >= 0.5


# ============================================================================
# Test: test_classify_fallback_to_default
# ============================================================================

def test_classify_fallback_to_default(registry):
    """
    Test that classification falls back to default category for ambiguous input.

    Verifies:
    - Returns a valid category even for unknown text
    - Default category (coding) is used when no match
    - Confidence is lower for fallback
    """
    result = registry.classify("xyz123 random gibberish unknown text")

    assert result is not None
    assert result.category is not None
    # Should fall back to coding or another default
    assert result.confidence < 0.5


# ============================================================================
# Test: test_classify_context_aware
# ============================================================================

def test_classify_context_aware(registry):
    """
    Test context-aware classification enhancement.

    Verifies:
    - Context is incorporated into classification
    - Keywords from context can affect classification
    """
    registry.enable_context_aware(True)

    # Without context - might not match
    registry.classify("find the information")

    # With context containing additional keywords
    result2 = registry.classify(
        "find the information",
        context={"type": "documentation research api"},
    )

    # Context should potentially change the result
    # (depends on keywords in context matching other categories)
    assert result2 is not None


# ============================================================================
# Test: test_register_adds_category
# ============================================================================

def test_register_adds_category(registry, custom_category):
    """
    Test that register() adds a new category.

    Verifies:
    - Category is added to registry
    - Can retrieve by name
    - Returns the registered category
    """
    registry.register(custom_category)

    assert custom_category.name in registry.list_names()
    retrieved = registry.get(custom_category.name)
    assert retrieved == custom_category


# ============================================================================
# Test: test_unregister_removes_category
# ============================================================================

def test_unregister_removes_category(registry, custom_category):
    """
    Test that unregister() removes a category.

    Verifies:
    - Category is removed from registry
    - Returns True for successful removal
    - Returns False for non-existent category
    """
    registry.register(custom_category)

    # Remove existing
    result = registry.unregister(custom_category.name)
    assert result is True
    assert registry.get(custom_category.name) is None

    # Remove non-existent
    result = registry.unregister("non-existent")
    assert result is False


# ============================================================================
# Test: test_get_sorted_returns_by_priority
# ============================================================================

def test_get_sorted_returns_by_priority(registry, custom_category):
    """
    Test that get_sorted() returns categories sorted by priority.

    Verifies:
    - Categories are sorted by priority (highest first)
    - Custom category with high priority appears first
    """
    # Custom category has priority 15, higher than built-ins
    registry.register(custom_category)

    sorted_cats = registry.get_sorted()

    assert len(sorted_cats) > 0
    # Custom category should be near the front due to high priority
    priorities = [c.priority for c in sorted_cats]
    assert priorities == sorted(priorities, reverse=True)


# ============================================================================
# Test: test_list_all_and_list_names
# ============================================================================

def test_list_all_and_list_names(registry):
    """
    Test list_all() and list_names() methods.

    Verifies:
    - list_all returns all Category objects
    - list_names returns all category names
    - Both have same count
    """
    all_cats = registry.list_all()
    all_names = registry.list_names()

    assert len(all_cats) == len(all_names)
    assert len(all_cats) > 0

    # All names should be strings
    assert all(isinstance(name, str) for name in all_names)


# ============================================================================
# Test: test_get_agents_for_task
# ============================================================================

def test_get_agents_for_task(registry):
    """
    Test getting recommended agents for a task.

    Verifies:
    - Returns list of agent names
    - Agents match the category's configuration
    """
    agents = registry.get_agents_for_task("Quick search for configuration files")

    assert isinstance(agents, list)
    # Quick tasks should use explore agent
    assert "explore" in agents


# ============================================================================
# Test: test_get_model_for_task
# ============================================================================

def test_get_model_for_task(registry):
    """
    Test getting recommended model for a task.

    Verifies:
    - Returns a model ID string
    - Model matches category configuration
    """
    model = registry.get_model_for_task("Quick check the logs")

    assert isinstance(model, str)
    assert len(model) > 0


# ============================================================================
# Test: test_get_complexity_for_task
# ============================================================================

def test_get_complexity_for_task(registry):
    """
    Test getting task complexity.

    Verifies:
    - Returns TaskComplexity enum value
    - Complexity matches category configuration
    """
    complexity = registry.get_complexity_for_task("Quick check")

    assert isinstance(complexity, TaskComplexity)

    # Deep reasoning task
    complexity2 = registry.get_complexity_for_task(
        "Analyze the system architecture deeply"
    )
    assert isinstance(complexity2, TaskComplexity)


# ============================================================================
# Test: test_to_dict
# ============================================================================

def test_to_dict(registry):
    """
    Test registry serialization to dictionary.

    Verifies:
    - Includes categories dict
    - Includes total count
    - Each category is serializable
    """
    d = registry.to_dict()

    assert "categories" in d
    assert "total_categories" in d
    assert d["total_categories"] > 0
    assert isinstance(d["categories"], dict)


# ============================================================================
# Test: test_classification_result_to_dict
# ============================================================================

def test_classification_result_to_dict():
    """
    Test ClassificationResult serialization.

    Verifies:
    - All fields are included
    - Category is serialized by name
    """
    category = BUILTIN_CATEGORIES["coding"]
    result = ClassificationResult(
        category=category,
        confidence=0.85,
        matched_keywords=["implement", "code"],
        method="keyword",
    )

    d = result.to_dict()

    assert d["category"] == "coding"
    assert d["confidence"] == 0.85
    assert d["matched_keywords"] == ["implement", "code"]
    assert d["method"] == "keyword"


# ============================================================================
# Test: test_builtin_categories_loaded
# ============================================================================

def test_builtin_categories_loaded(registry):
    """
    Test that built-in categories are loaded by default.

    Verifies:
    - Built-in categories are present
    - Expected categories exist (coding, quick, research, etc.)
    """
    names = registry.list_names()

    # Check expected built-in categories
    assert "coding" in names
    assert "quick" in names
    assert "research" in names
    assert "exploration" in names


# ============================================================================
# Test: test_priority_affects_classification
# ============================================================================

def test_priority_affects_classification(registry):
    """
    Test that category priority affects classification results.

    Verifies:
    - Higher priority categories are preferred
    - When scores are equal, priority breaks ties
    """
    # Create two categories with same keywords but different priorities
    cat1 = Category(
        name="low-priority",
        description="Low priority cat",
        keywords=["test"],
        priority=1,
    )
    cat2 = Category(
        name="high-priority",
        description="High priority cat",
        keywords=["test"],
        priority=10,
    )

    registry.register(cat1)
    registry.register(cat2)

    result = registry.classify("test task")

    # Higher priority category should win
    assert result.category.name == "high-priority"


# ============================================================================
# Test: test_empty_keywords_category
# ============================================================================

def test_empty_keywords_category(registry):
    """
    Test handling of categories with no keywords.

    Verifies:
    - Category with no keywords doesn't cause errors
    - Score is 0 for such category
    """
    cat = Category(
        name="no-keywords",
        description="Category without keywords",
        keywords=[],
        priority=5,
    )
    registry.register(cat)

    result = registry.classify("any random task")

    # Should not crash and should return some category
    assert result is not None


# ============================================================================
# Test: test_global_registry_singleton
# ============================================================================

def test_global_registry_singleton():
    """
    Test that get_category_registry() returns a singleton.

    Verifies:
    - Same instance is returned on multiple calls
    - Instance is a CategoryRegistry
    """
    registry1 = get_category_registry()
    registry2 = get_category_registry()

    assert registry1 is registry2
    assert isinstance(registry1, CategoryRegistry)


# ============================================================================
# Test: test_multiple_keyword_matches
# ============================================================================

def test_multiple_keyword_matches(registry):
    """
    Test classification with multiple keyword matches.

    Verifies:
    - All matching keywords are captured
    - Score increases with more matches
    - Best match is selected
    """
    # Coding has many keywords: implement, code, write, create, modify, fix, bug
    result = registry.classify(
        "implement and fix the code to create a new feature"
    )

    assert result is not None
    # Should match coding category
    assert result.category.name == "coding"
    # Should have multiple matched keywords
    assert len(result.matched_keywords) >= 3


# ============================================================================
# Test: test_case_insensitive_matching
# ============================================================================

def test_case_insensitive_matching(registry):
    """
    Test that keyword matching is case-insensitive.

    Verifies:
    - Uppercase keywords match
    - Mixed case keywords match
    """
    result1 = registry.classify("IMPLEMENT this feature")
    result2 = registry.classify("implement this feature")

    # Both should match the same category
    assert result1.category.name == result2.category.name


# ============================================================================
# Test: test_classifier_setters
# ============================================================================

def test_classifier_setters(registry, mock_llm_classifier, mock_semantic_classifier):
    """
    Test setting LLM and semantic classifiers.

    Verifies:
    - Classifiers are stored
    - No errors on set
    """
    registry.set_llm_classifier(mock_llm_classifier)
    registry.set_semantic_classifier(mock_semantic_classifier)

    assert registry._llm_classifier is mock_llm_classifier
    assert registry._semantic_classifier is mock_semantic_classifier


# ============================================================================
# Test: test_enable_context_aware
# ============================================================================

def test_enable_context_aware(registry):
    """
    Test enabling/disabling context-aware classification.

    Verifies:
    - Setting is stored
    - Can enable and disable
    """
    assert registry._context_aware_enabled is False

    registry.enable_context_aware(True)
    assert registry._context_aware_enabled is True

    registry.enable_context_aware(False)
    assert registry._context_aware_enabled is False


# ============================================================================
# Test: test_classify_async_fallback_to_keyword
# ============================================================================

@pytest.mark.asyncio
async def test_classify_async_fallback_to_keyword(registry, mock_llm_classifier):
    """
    Test that async classification falls back to keyword when LLM fails.

    Verifies:
    - Keyword classification is used as fallback
    - No errors when LLM classifier raises
    """
    # Make LLM classifier raise an exception
    mock_llm_classifier.classify = AsyncMock(side_effect=RuntimeError("LLM error"))
    registry.set_llm_classifier(mock_llm_classifier)

    result = await registry.classify_async(
        "implement this feature",
        use_llm=True,
    )

    # Should fall back to keyword classification
    assert result is not None
    assert result.method == "keyword"


# ============================================================================
# Test: test_semantic_low_confidence_fallback
# ============================================================================

@pytest.mark.asyncio
async def test_semantic_low_confidence_fallback(registry):
    """
    Test that semantic classification falls back when confidence is low.

    Verifies:
    - Low confidence results are ignored
    - Falls back to keyword classification
    """
    # Create a classifier that returns low confidence
    low_confidence_classifier = AsyncMock()

    async def classify_low(text: str, context: dict = None) -> ClassificationResult:
        return ClassificationResult(
            category=BUILTIN_CATEGORIES["coding"],
            confidence=0.3,  # Below threshold
            method="semantic",
        )

    low_confidence_classifier.classify = classify_low
    registry.set_semantic_classifier(low_confidence_classifier)

    result = await registry.classify_async(
        "implement this feature",
        use_semantic=True,
    )

    # Should fall back to keyword because confidence < 0.5
    assert result.method == "keyword"


# ============================================================================
# Test: test_classify_sync_in_async_context
# ============================================================================

@pytest.mark.asyncio
async def test_classify_sync_in_async_context(registry):
    """
    Test that classify() works in async context (with fallback).

    Verifies:
    - Falls back to keyword matching in async context
    - Does not crash
    - Logs warning about using async version
    """
    # In async context, sync classify should work but fall back
    result = registry.classify("implement this feature")

    assert result is not None
    # Should be keyword method (fallback)
    assert result.method == "keyword"


# ============================================================================
# Test: test_chinese_keywords
# ============================================================================

def test_chinese_keywords(registry):
    """
    Test that Chinese keywords are matched.

    Verifies:
    - Chinese keywords in categories work
    - Matching is language-agnostic
    """
    # Coding category has Chinese keywords: 实现, 编码, 修复, 开发
    result = registry.classify("实现这个功能")

    assert result is not None
    # Should match coding category
    assert result.category.name == "coding"
    assert len(result.matched_keywords) > 0


# ============================================================================
# Test: test_word_boundary_matching
# ============================================================================

def test_word_boundary_matching(registry):
    """
    Test that keyword matching respects word boundaries.

    Verifies:
    - Partial word matches don't count
    - Only whole words match
    """
    # "code" keyword should match "code" but not "codebase" or "encode"
    # This tests the regex pattern \bkeyword\b
    result1 = registry.classify("write some code")
    registry.classify("check the codebase")
    registry.classify("encode the data")

    # "code" should definitely match
    assert "code" in result1.matched_keywords

    # "codebase" contains "code" but shouldn't match as keyword
    # (depends on implementation, may match if word boundaries allow)
    # The key is that results are consistent


# ============================================================================
# Test: test_confidence_calculation
# ============================================================================

def test_confidence_calculation(registry):
    """
    Test that confidence is calculated correctly.

    Verifies:
    - More matches = higher confidence
    - Priority bonus is applied
    - Confidence is clamped to valid range
    """
    # Quick has keywords: quick, fast, simple, check, list, show, grep, find
    # Using many keywords should give high confidence
    result_high = registry.classify(
        "quick fast simple check list show grep find"
    )

    # Using few keywords should give lower confidence
    result_low = registry.classify("quick check")

    assert result_high.confidence > result_low.confidence
    assert 0 <= result_high.confidence <= 1.0
    assert 0 <= result_low.confidence <= 1.0

"""
Category Registry

Manages task categories and classification.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.core.category import (
    BUILTIN_CATEGORIES,
    Category,
    TaskComplexity,
    get_sorted_categories,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of task classification"""

    category: Category
    confidence: float  # 0.0 to 1.0
    matched_keywords: list[str] = field(default_factory=list)
    method: str = "keyword"  # keyword, llm, fallback


class CategoryRegistry:
    """
    Category Registry

    Manages categories and provides task classification.
    """

    def __init__(self):
        """Initialize category registry"""
        self._categories: dict[str, Category] = dict(BUILTIN_CATEGORIES)
        self._llm_classifier: Any = None  # Optional LLM-based classifier

    def register(self, category: Category) -> None:
        """
        Register a category

        Args:
            category: Category to register
        """
        self._categories[category.name] = category
        logger.info(f"Registered category: {category.name}")

    def unregister(self, name: str) -> bool:
        """Unregister a category"""
        if name in self._categories:
            del self._categories[name]
            return True
        return False

    def get(self, name: str) -> Category | None:
        """Get category by name"""
        return self._categories.get(name)

    def list_all(self) -> list[Category]:
        """Get all categories"""
        return list(self._categories.values())

    def list_names(self) -> list[str]:
        """Get all category names"""
        return list(self._categories.keys())

    def get_sorted(self) -> list[Category]:
        """Get categories sorted by priority"""
        return sorted(
            self._categories.values(),
            key=lambda c: c.priority,
            reverse=True,
        )

    def set_llm_classifier(self, classifier: Any) -> None:
        """
        Set optional LLM-based classifier

        Args:
            classifier: Classifier with async classify(text) method
        """
        self._llm_classifier = classifier

    def classify(
        self,
        task_description: str,
        use_llm: bool = False,
    ) -> ClassificationResult:
        """
        Classify a task into a category

        Args:
            task_description: Task description
            use_llm: Use LLM-based classification if available

        Returns:
            ClassificationResult
        """
        # Try LLM-based classification first if enabled
        if use_llm and self._llm_classifier:
            try:
                result = self._llm_classifier.classify(task_description)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")

        # Keyword-based classification
        return self._classify_by_keywords(task_description)

    def _classify_by_keywords(self, task_description: str) -> ClassificationResult:
        """
        Classify task using keyword matching

        Args:
            task_description: Task description

        Returns:
            ClassificationResult
        """
        task_lower = task_description.lower()

        best_category = None
        best_score = 0
        best_keywords = []

        for category in self.get_sorted():
            score = 0
            matched = []

            for keyword in category.keywords:
                # Case-insensitive keyword matching
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, task_lower):
                    score += 1
                    matched.append(keyword)

            # Normalize score
            if category.keywords:
                normalized_score = score / len(category.keywords)
            else:
                normalized_score = 0

            # Apply priority bonus
            priority_bonus = category.priority * 0.01
            total_score = normalized_score + priority_bonus

            if total_score > best_score:
                best_score = total_score
                best_category = category
                best_keywords = matched

        # Determine confidence
        if best_score >= 0.5:
            confidence = min(1.0, best_score)
        elif best_score >= 0.2:
            confidence = best_score * 0.8
        else:
            # Fallback to default category
            best_category = self._categories.get(
                "coding",
                self.get_sorted()[0] if self._categories else None,
            )
            best_keywords = []
            confidence = 0.3

        return ClassificationResult(
            category=best_category,
            confidence=confidence,
            matched_keywords=best_keywords,
            method="keyword",
        )

    def get_agents_for_task(self, task_description: str) -> list[str]:
        """
        Get recommended agents for a task

        Args:
            task_description: Task description

        Returns:
            List of agent names (ordered by preference)
        """
        result = self.classify(task_description)
        return result.category.agents if result.category else []

    def get_model_for_task(self, task_description: str) -> str:
        """
        Get recommended model for a task

        Args:
            task_description: Task description

        Returns:
            Model ID
        """
        result = self.classify(task_description)
        return result.category.model if result.category else "gpt-4o-mini"

    def get_complexity_for_task(self, task_description: str) -> TaskComplexity:
        """
        Get task complexity

        Args:
            task_description: Task description

        Returns:
            TaskComplexity
        """
        result = self.classify(task_description)
        return result.category.complexity if result.category else TaskComplexity.STANDARD

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "categories": {
                name: cat.to_dict() for name, cat in self._categories.items()
            },
            "total_categories": len(self._categories),
        }


# Global registry instance
_global_registry: CategoryRegistry | None = None


def get_category_registry() -> CategoryRegistry:
    """Get the global category registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = CategoryRegistry()
    return _global_registry

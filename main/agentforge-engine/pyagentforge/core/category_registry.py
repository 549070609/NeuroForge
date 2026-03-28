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
    method: str = "keyword"  # keyword, semantic, llm, fallback

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "category": self.category.name if self.category else None,
            "confidence": self.confidence,
            "matched_keywords": self.matched_keywords,
            "method": self.method,
        }


class CategoryRegistry:
    """
    Category Registry

    Manages categories and provides task classification.

    Supports multiple classification methods:
    - Keyword matching (default, fast)
    - Semantic similarity (requires embeddings)
    - LLM classification (intelligent but slower)
    """

    def __init__(self):
        """Initialize category registry"""
        self._categories: dict[str, Category] = dict(BUILTIN_CATEGORIES)
        self._llm_classifier: Any = None  # Optional LLM-based classifier
        self._semantic_classifier: Any = None  # Optional semantic classifier
        self._context_aware_enabled: bool = False  # Context-aware classification

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
            classifier: Classifier with async classify(text, context) method
        """
        self._llm_classifier = classifier
        logger.info("LLM classifier set")

    def set_semantic_classifier(self, classifier: Any) -> None:
        """
        Set optional semantic classifier

        Args:
            classifier: Classifier with async classify(text, context) method
        """
        self._semantic_classifier = classifier
        logger.info("Semantic classifier set")

    def enable_context_aware(self, enabled: bool = True) -> None:
        """
        Enable or disable context-aware classification

        Args:
            enabled: Whether to enable context-aware mode
        """
        self._context_aware_enabled = enabled
        logger.info(f"Context-aware classification: {'enabled' if enabled else 'disabled'}")

    def classify(
        self,
        task_description: str,
        use_llm: bool = False,
        use_semantic: bool = False,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify a task into a category (synchronous version)

        **⚠️ WARNING**: This method has limitations:
        - In async context: Falls back to keyword matching (ignores use_llm/use_semantic)
        - In sync context: Creates new event loop (may cause issues in some environments)

        **Recommendation**: Use `classify_async()` when possible for consistent behavior.

        Args:
            task_description: Task description
            use_llm: Use LLM-based classification if available (only works in sync context)
            use_semantic: Use semantic classification if available (only works in sync context)
            context: Optional context for classification

        Returns:
            ClassificationResult
        """
        import asyncio

        # Try to run async version
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, but this is a sync method
            # WARNING: Falls back to keyword matching, ignoring use_llm/use_semantic
            logger.warning(
                "classify() called in async context - falling back to keyword matching. "
                "Use classify_async() for full functionality."
            )
            return self._classify_by_keywords(task_description, context)
        except RuntimeError:
            # No running loop, we can create one
            # Note: This creates a new event loop each time, which can be inefficient
            logger.debug("Creating new event loop for sync classify()")
            return asyncio.run(self.classify_async(
                task_description,
                use_llm=use_llm,
                use_semantic=use_semantic,
                context=context,
            ))

    async def classify_async(
        self,
        task_description: str,
        use_llm: bool = False,
        use_semantic: bool = False,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify a task into a category (async version)

        Args:
            task_description: Task description
            use_llm: Use LLM-based classification if available
            use_semantic: Use semantic classification if available
            context: Optional context for classification

        Returns:
            ClassificationResult
        """
        # Try semantic classification first if enabled
        if use_semantic and self._semantic_classifier:
            try:
                result = await self._semantic_classifier.classify(task_description, context)
                if result and result.confidence >= 0.5:
                    logger.debug(f"Semantic classification: {result.category.name} ({result.confidence:.2f})")
                    return result
            except Exception as e:
                logger.warning(f"Semantic classification failed: {e}")

        # Try LLM-based classification if enabled
        if use_llm and self._llm_classifier:
            try:
                result = await self._llm_classifier.classify(task_description, context)
                if result:
                    logger.debug(f"LLM classification: {result.category.name} ({result.confidence:.2f})")
                    return result
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")

        # Keyword-based classification (fallback)
        return self._classify_by_keywords(task_description, context)

    def _classify_by_keywords(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify task using keyword matching

        Args:
            task_description: Task description
            context: Optional context (used for context-aware classification)

        Returns:
            ClassificationResult
        """
        task_lower = task_description.lower()

        # Context-aware enhancement: add context to task text
        if self._context_aware_enabled and context:
            context_text = " ".join(str(v) for v in context.values() if v)
            task_lower = f"{task_lower} {context_text.lower()}"

        best_category = None
        best_score = 0
        best_keywords = []

        for category in self.get_sorted():
            score = 0
            matched = []

            for keyword in category.keywords:
                keyword_lower = keyword.lower()
                contains_cjk = any("\u4e00" <= char <= "\u9fff" for char in keyword_lower)
                if contains_cjk:
                    is_match = keyword_lower in task_lower
                else:
                    pattern = r"\b" + re.escape(keyword_lower) + r"\b"
                    is_match = re.search(pattern, task_lower) is not None

                if is_match:
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
        elif best_score >= 0.2 or best_keywords:
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
        return result.category.model if result.category else "default"

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

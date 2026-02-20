"""
Semantic Classifier

Uses embeddings to compute semantic similarity between tasks and categories.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.core.category import Category
from pyagentforge.core.category_registry import ClassificationResult
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SemanticClassifierConfig:
    """Configuration for semantic classifier"""

    similarity_threshold: float = 0.3  # Minimum similarity to consider a match
    cache_embeddings: bool = True  # Cache category embeddings
    max_retries: int = 3  # Max retries for embedding API calls
    fallback_to_keyword: bool = True  # Fallback to keyword matching on failure


class SemanticClassifier:
    """
    Semantic Classifier using embeddings

    Uses OpenAI embeddings (or similar) to compute semantic similarity
    between task descriptions and category keywords/descriptions.
    """

    def __init__(
        self,
        provider: Any,
        categories: list[Category],
        config: SemanticClassifierConfig | None = None,
    ):
        """
        Initialize semantic classifier

        Args:
            provider: LLM provider with embedding support
            categories: List of categories to classify against
            config: Classifier configuration
        """
        self.provider = provider
        self.categories = categories
        self.config = config or SemanticClassifierConfig()

        # Category embeddings cache
        self._category_embeddings: dict[str, list[float]] = {}

        # Initialized flag
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the classifier by pre-computing category embeddings

        This should be called after creation to ensure embeddings are ready.
        """
        if self._initialized:
            return

        if not self.config.cache_embeddings:
            self._initialized = True
            return

        logger.info(f"Initializing semantic classifier with {len(self.categories)} categories")

        for category in self.categories:
            # Combine keywords and description for embedding
            text_parts = [category.description]
            if category.keywords:
                text_parts.extend(category.keywords[:10])  # Limit keywords

            text = " ".join(text_parts)

            try:
                embedding = await self._get_embedding(text)
                if embedding:
                    self._category_embeddings[category.name] = embedding
                    logger.debug(f"Cached embedding for category: {category.name}")
            except Exception as e:
                logger.warning(f"Failed to get embedding for category {category.name}: {e}")

        self._initialized = True
        logger.info(f"Semantic classifier initialized with {len(self._category_embeddings)} embeddings")

    async def classify(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult | None:
        """
        Classify a task using semantic similarity

        Args:
            task_description: The task description to classify
            context: Optional context for classification

        Returns:
            ClassificationResult or None if classification fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get task embedding
            task_embedding = await self._get_embedding(task_description)
            if not task_embedding:
                logger.warning("Failed to get task embedding")
                return None

            # Compute similarities
            similarities: list[tuple[Category, float]] = []

            for category in self.categories:
                # Use cached embedding or compute on-the-fly
                category_embedding = self._category_embeddings.get(category.name)

                if not category_embedding:
                    # Compute on-the-fly if not cached
                    text_parts = [category.description]
                    if category.keywords:
                        text_parts.extend(category.keywords[:10])
                    text = " ".join(text_parts)
                    category_embedding = await self._get_embedding(text)

                if category_embedding:
                    similarity = self._cosine_similarity(task_embedding, category_embedding)

                    # Apply priority bonus (smaller than keyword matching)
                    priority_bonus = category.priority * 0.005
                    total_score = similarity + priority_bonus

                    similarities.append((category, total_score))

            if not similarities:
                return None

            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x[1], reverse=True)

            best_category, best_score = similarities[0]

            # Check threshold
            if best_score < self.config.similarity_threshold:
                logger.debug(
                    f"Best similarity {best_score:.3f} below threshold "
                    f"{self.config.similarity_threshold}"
                )
                return None

            # Compute confidence
            confidence = min(1.0, best_score)

            return ClassificationResult(
                category=best_category,
                confidence=confidence,
                matched_keywords=[],  # Semantic matching doesn't use keywords
                method="semantic",
            )

        except Exception as e:
            logger.error(f"Semantic classification failed: {e}")
            return None

    async def _get_embedding(self, text: str) -> list[float] | None:
        """
        Get embedding for text

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None
        """
        if not text or not text.strip():
            return None

        try:
            # Check if provider has embedding support
            if hasattr(self.provider, "create_embedding"):
                return await self.provider.create_embedding(text)

            # Fallback: try using OpenAI client directly
            if hasattr(self.provider, "_client"):
                client = self.provider._client
                if hasattr(client, "embeddings"):
                    response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=text,
                    )
                    return list(response.data[0].embedding)

            logger.warning("Provider does not support embeddings")
            return None

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """
        Compute cosine similarity between two vectors

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score between 0 and 1
        """
        if len(a) != len(b):
            logger.warning(f"Vector length mismatch: {len(a)} vs {len(b)}")
            return 0.0

        if not a or not b:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    def update_categories(self, categories: list[Category]) -> None:
        """
        Update categories and clear embedding cache

        Args:
            categories: New list of categories
        """
        self.categories = categories
        self._category_embeddings.clear()
        self._initialized = False

        logger.info(f"Updated categories, cleared embedding cache")

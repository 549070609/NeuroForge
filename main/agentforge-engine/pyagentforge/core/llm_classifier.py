"""
LLM Classifier

Uses LLM for intelligent task classification when keyword matching is insufficient.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.core.category import Category
from pyagentforge.core.category_registry import ClassificationResult
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LLMClassifierConfig:
    """Configuration for LLM classifier"""

    model: str = "default"  # Model to use for classification
    max_tokens: int = 500  # Max tokens for response
    temperature: float = 0.3  # Low temperature for consistent results
    timeout: int = 30  # Timeout in seconds
    cache_results: bool = True  # Cache classification results
    fallback_to_keyword: bool = True  # Fallback to keyword on failure


# Classification prompt template
CLASSIFICATION_PROMPT = """You are a task classification system. Your job is to analyze a task and determine the most appropriate category.

## Available Categories

{categories_text}

## Task to Classify

{task_description}

## Context (Optional)

{context_text}

## Instructions

1. Analyze the task description and any provided context
2. Determine which category best matches the task
3. Provide a confidence score between 0.0 and 1.0
4. List any keywords from the task that influenced your decision

## Response Format

Respond with a JSON object with the following fields:
- "category": the name of the selected category (must be one of the available categories)
- "confidence": a number between 0.0 and 1.0
- "keywords": a list of keywords from the task that influenced the decision
- "reasoning": a brief explanation of why this category was chosen

Example response:
```json
{{
  "category": "coding",
  "confidence": 0.85,
  "keywords": ["implement", "feature", "code"],
  "reasoning": "The task mentions implementing a feature which requires coding"
}}
```

Respond only with the JSON object, no additional text."""


class LLMClassifier:
    """
    LLM-based Classifier

    Uses an LLM to perform intelligent classification when keyword matching
    is insufficient. Good for complex or ambiguous tasks.
    """

    def __init__(
        self,
        provider: Any,
        categories: list[Category],
        config: LLMClassifierConfig | None = None,
    ):
        """
        Initialize LLM classifier

        Args:
            provider: LLM provider instance
            categories: List of categories to classify against
            config: Classifier configuration
        """
        self.provider = provider
        self.categories = categories
        self.config = config or LLMClassifierConfig()

        # Build category lookup
        self._category_map: dict[str, Category] = {
            cat.name: cat for cat in categories
        }

        # Classification cache
        self._cache: dict[str, ClassificationResult] = {}

    async def classify(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult | None:
        """
        Classify a task using LLM

        Args:
            task_description: The task description to classify
            context: Optional context for classification

        Returns:
            ClassificationResult or None if classification fails
        """
        # Check cache
        if self.config.cache_results:
            cache_key = self._make_cache_key(task_description, context)
            if cache_key in self._cache:
                logger.debug(f"Using cached classification result")
                return self._cache[cache_key]

        try:
            # Build categories text
            categories_text = self._build_categories_text()

            # Build context text
            context_text = self._build_context_text(context)

            # Build prompt
            prompt = CLASSIFICATION_PROMPT.format(
                categories_text=categories_text,
                task_description=task_description,
                context_text=context_text,
            )

            # Call LLM
            response = await self._call_llm(prompt)

            if not response:
                return None

            # Parse response
            result = self._parse_response(response)

            if result and self.config.cache_results:
                cache_key = self._make_cache_key(task_description, context)
                self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None

    def _build_categories_text(self) -> str:
        """Build formatted text of available categories"""
        lines = []

        for i, category in enumerate(self.categories, 1):
            lines.append(f"{i}. **{category.name}**")
            lines.append(f"   - Description: {category.description}")
            if category.keywords:
                lines.append(f"   - Keywords: {', '.join(category.keywords[:10])}")
            lines.append("")

        return "\n".join(lines)

    def _build_context_text(self, context: dict[str, Any] | None) -> str:
        """Build formatted context text"""
        if not context:
            return "No additional context provided."

        lines = []
        for key, value in context.items():
            if isinstance(value, str):
                lines.append(f"- {key}: {value}")
            elif isinstance(value, (list, dict)):
                lines.append(f"- {key}: {json.dumps(value, indent=2)}")
            else:
                lines.append(f"- {key}: {str(value)}")

        return "\n".join(lines) if lines else "No additional context provided."

    async def _call_llm(self, prompt: str) -> str | None:
        """
        Call LLM with prompt

        Args:
            prompt: The prompt to send

        Returns:
            Response text or None
        """
        try:
            # Check if provider has create_message method
            if hasattr(self.provider, "create_message"):
                from pyagentforge.kernel.message import Message

                messages = [Message(role="user", content=prompt)]

                response = await self.provider.create_message(
                    system="You are a task classification system. Respond only with valid JSON.",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )

                return response.text if hasattr(response, "text") else str(response)

            logger.warning("Provider does not support message creation")
            return None

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _parse_response(self, response: str) -> ClassificationResult | None:
        """
        Parse LLM response into ClassificationResult

        Args:
            response: Raw LLM response

        Returns:
            ClassificationResult or None
        """
        try:
            # Extract JSON from response
            json_str = self._extract_json(response)
            if not json_str:
                logger.warning(f"Could not extract JSON from response: {response[:200]}")
                return None

            data = json.loads(json_str)

            # Get category
            category_name = data.get("category", "")
            category = self._category_map.get(category_name)

            if not category:
                logger.warning(f"Unknown category in response: {category_name}")
                return None

            # Get confidence
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

            # Get keywords
            keywords = data.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []

            # Log reasoning if present
            reasoning = data.get("reasoning", "")
            if reasoning:
                logger.debug(f"Classification reasoning: {reasoning}")

            return ClassificationResult(
                category=category,
                confidence=confidence,
                matched_keywords=keywords,
                method="llm",
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse classification response: {e}")
            return None

    def _extract_json(self, text: str) -> str | None:
        """
        Extract JSON from text that might contain markdown code blocks

        Args:
            text: Text possibly containing JSON

        Returns:
            Extracted JSON string or None
        """
        import re

        # Try to extract from markdown code block
        json_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_block:
            return json_block.group(1).strip()

        # Try to find raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0)

        return None

    def _make_cache_key(self, task_description: str, context: dict[str, Any] | None) -> str:
        """Create cache key from task and context"""
        import hashlib

        content = task_description
        if context:
            content += json.dumps(context, sort_keys=True)

        return hashlib.md5(content.encode()).hexdigest()

    def update_categories(self, categories: list[Category]) -> None:
        """
        Update categories and clear cache

        Args:
            categories: New list of categories
        """
        self.categories = categories
        self._category_map = {cat.name: cat for cat in categories}
        self._cache.clear()

        logger.info(f"Updated categories, cleared cache")

    def clear_cache(self) -> None:
        """Clear classification cache"""
        self._cache.clear()
        logger.info("Cleared classification cache")

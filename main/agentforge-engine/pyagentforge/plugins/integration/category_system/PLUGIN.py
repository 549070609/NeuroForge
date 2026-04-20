"""
Category System Plugin

Task classification and category-based configuration.
"""

from typing import TYPE_CHECKING, Any

from pyagentforge.plugins.integration.category_system.category import Category, TaskComplexity
from pyagentforge.plugins.integration.category_system.category_registry import (
    CategoryRegistry,
    ClassificationResult,
    get_category_registry,
)
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.kernel.context import ContextManager

logger = get_logger(__name__)


class CategorySystemPlugin(Plugin):
    """
    Category System Plugin

    Features:
    - Task classification into categories
    - Category-based model selection
    - Category-based agent selection
    - Extensible classification (keyword + optional LLM)
    """

    metadata = PluginMetadata(
        id="integration.category_system",
        name="Category System",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Task classification and category-based configuration",
        author="PyAgentForge",
        provides=["category_system", "task_classification"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._registry: CategoryRegistry | None = None
        self._enabled: bool = True
        self._use_llm_classification: bool = False

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)
        self._use_llm_classification = config.get("use_llm_classification", False)

        # Get or create registry
        self._registry = get_category_registry()

        # Register custom categories from config
        custom_categories = config.get("categories", [])
        for cat_data in custom_categories:
            try:
                category = Category(
                    name=cat_data["name"],
                    description=cat_data.get("description", ""),
                    model=cat_data.get("model", "default"),
                    agents=cat_data.get("agents", []),
                    skills=cat_data.get("skills", []),
                    priority=cat_data.get("priority", 0),
                    keywords=cat_data.get("keywords", []),
                    complexity=TaskComplexity(cat_data.get("complexity", "standard")),
                )
                self._registry.register(category)
            except Exception as e:
                logger.warning(f"Failed to register custom category: {e}")

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            self,
            self._on_before_llm_call,
        )

        self.context.logger.info(
            "Category system plugin activated",
            extra_data={
                "enabled": self._enabled,
                "categories": len(self._registry.list_all()) if self._registry else 0,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    async def _on_before_llm_call(
        self,
        context: "ContextManager",
        prompt: str = "",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before LLM call - classify task

        Args:
            context: Context manager
            prompt: User prompt

        Returns:
            Classification info
        """
        if not self._enabled or self._registry is None:
            return None

        if not prompt:
            return None

        # Classify the task
        result = self.classify(prompt)

        if result and result.confidence > 0.5:
            logger.info(
                f"Task classified as '{result.category.name}'",
                extra_data={
                    "confidence": result.confidence,
                    "matched_keywords": result.matched_keywords,
                },
            )

            return {
                "category": result.category.name,
                "confidence": result.confidence,
                "recommended_model": result.category.model,
                "recommended_agents": result.category.agents,
                "complexity": result.category.complexity.value,
            }

        return None

    def get_registry(self) -> CategoryRegistry | None:
        """Get the category registry"""
        return self._registry

    def classify(self, task_description: str) -> ClassificationResult | None:
        """
        Classify a task

        Args:
            task_description: Task description

        Returns:
            ClassificationResult or None
        """
        if self._registry is None:
            return None

        return self._registry.classify(
            task_description,
            use_llm=self._use_llm_classification,
        )

    def get_category(self, name: str) -> Category | None:
        """Get category by name"""
        if self._registry is None:
            return None
        return self._registry.get(name)

    def get_model_for_task(self, task_description: str) -> str:
        """Get recommended model for a task"""
        if self._registry is None:
            return "default"
        return self._registry.get_model_for_task(task_description)

    def get_agents_for_task(self, task_description: str) -> list[str]:
        """Get recommended agents for a task"""
        if self._registry is None:
            return []
        return self._registry.get_agents_for_task(task_description)

    def get_complexity(self, task_description: str) -> TaskComplexity:
        """Get task complexity"""
        if self._registry is None:
            return TaskComplexity.STANDARD
        return self._registry.get_complexity_for_task(task_description)

    def list_categories(self) -> list[Category]:
        """List all categories"""
        if self._registry is None:
            return []
        return self._registry.list_all()

    def register_category(self, category: Category) -> None:
        """Register a custom category"""
        if self._registry:
            self._registry.register(category)

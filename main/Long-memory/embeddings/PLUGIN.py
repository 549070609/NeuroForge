"""Local embeddings plugin entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import numpy as np

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType

try:
    from .embeddings_provider import EmbeddingsProvider
except ImportError:
    # Support direct-file imports during standalone plugin loading/tests.
    from embeddings_provider import EmbeddingsProvider


class EmbedTextTool(BaseTool):
    """Generate embeddings for a list of input texts."""

    name = "embed_text"
    description = "Generate sentence embeddings for semantic search and similarity tasks."
    parameters_schema = {
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Text list to embed.",
            },
            "return_vectors": {
                "type": "boolean",
                "description": "Return full vectors instead of summary stats.",
            },
        },
        "required": ["texts"],
    }
    timeout = 120
    risk_level = "low"

    def __init__(self, provider: EmbeddingsProvider) -> None:
        self._provider = provider

    async def execute(self, texts: List[str], return_vectors: bool = False) -> str:
        if not texts:
            return "错误: 文本列表为空"
        if len(texts) > 100:
            return "错误: 单次最多处理 100 条文本"

        try:
            embeddings = await self._provider.embed(texts)
            if return_vectors:
                payload = {
                    "count": len(embeddings),
                    "dimension": len(embeddings[0]) if embeddings else 0,
                    "embeddings": embeddings,
                }
                return json.dumps(payload, ensure_ascii=False, indent=2)

            return (
                f"成功生成 {len(embeddings)} 个嵌入向量\n"
                f"维度: {len(embeddings[0]) if embeddings else 0}\n"
                f"模型: {self._provider.get_model_name()}"
            )
        except Exception as exc:
            return f"嵌入生成失败: {exc}"


class ComputeSimilarityTool(BaseTool):
    """Compute cosine similarity by dot-product on normalized vectors."""

    name = "compute_similarity"
    description = "Compute semantic similarity (0-1) for two text inputs."
    parameters_schema = {
        "type": "object",
        "properties": {
            "text1": {
                "type": "string",
                "description": "First input text.",
            },
            "text2": {
                "type": "string",
                "description": "Second input text.",
            },
        },
        "required": ["text1", "text2"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(self, provider: EmbeddingsProvider) -> None:
        self._provider = provider

    async def execute(self, text1: str, text2: str) -> str:
        try:
            embeddings = await self._provider.embed([text1, text2])
            if len(embeddings) != 2:
                return "错误: 嵌入生成失败"

            vec1 = np.array(embeddings[0], dtype=float)
            vec2 = np.array(embeddings[1], dtype=float)
            similarity = float(np.dot(vec1, vec2))

            if similarity > 0.8:
                level = "高度相似"
            elif similarity > 0.5:
                level = "中等相似"
            elif similarity > 0.2:
                level = "差异较大"
            else:
                level = "几乎不相关"

            return f"相似度: {similarity:.4f}\n解释: {level}"
        except Exception as exc:
            return f"相似度计算失败: {exc}"


class LocalEmbeddingsPlugin(Plugin):
    """Plugin providing local embeddings tools."""

    metadata = PluginMetadata(
        id="tool.local-embeddings",
        name="Local Embeddings",
        version="1.0.0",
        type=PluginType.TOOL,
        description=(
            "Local text embeddings tools backed by all-MiniLM-L6-v2 for "
            "vectorization and semantic similarity."
        ),
        author="Local",
        dependencies=[],
        optional_dependencies=[],
        provides=["embeddings.local", "embeddings.sentence-transformers"],
        priority=10,
    )

    def __init__(self) -> None:
        super().__init__()
        self._provider: Optional[EmbeddingsProvider] = None
        self._tools: List[BaseTool] = []

    async def on_plugin_load(self, context: PluginContext) -> None:
        await super().on_plugin_load(context)

        config = context.config or {}
        model_path = config.get("model_path")
        if not model_path:
            local_model_path = Path(__file__).parent / "models" / "all-MiniLM-L6-v2"
            if local_model_path.exists():
                model_path = str(local_model_path)

        self._provider = EmbeddingsProvider(
            model_path=model_path,
            model_name=config.get("model_name", "all-MiniLM-L6-v2"),
            device=config.get("device", "cpu"),
            max_batch_size=config.get("max_batch_size", 4),
        )

        context.logger.info(
            "Local Embeddings plugin loaded "
            f"(model_path={model_path}, device={config.get('device', 'cpu')})"
        )

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()

        if self._provider is None:
            raise RuntimeError("Embeddings provider is not initialized")

        self._tools = [
            EmbedTextTool(self._provider),
            ComputeSimilarityTool(self._provider),
        ]
        self.context.logger.info("Local Embeddings plugin activated with 2 tools")

    async def on_plugin_deactivate(self) -> None:
        self._tools = []
        await super().on_plugin_deactivate()
        self.context.logger.info("Local Embeddings plugin deactivated")

    def get_tools(self) -> List[BaseTool]:
        return self._tools

    def get_embeddings_provider(self) -> Optional[EmbeddingsProvider]:
        return self._provider


def create_plugin() -> Plugin:
    """Plugin factory."""
    return LocalEmbeddingsPlugin()

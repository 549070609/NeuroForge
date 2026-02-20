"""
Local Embeddings Plugin

pyagentforge 插件入口
"""

from typing import Any, Dict, List
from pathlib import Path

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext
from pyagentforge.kernel.base_tool import BaseTool

from .embeddings_provider import EmbeddingsProvider


class EmbedTextTool(BaseTool):
    """文本嵌入工具"""

    name = "embed_text"
    description = "将文本转换为 384 维向量嵌入，用于语义搜索、相似度计算等"
    parameters_schema = {
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要嵌入的文本列表",
            },
            "return_vectors": {
                "type": "boolean",
                "description": "是否返回完整向量（默认只返回统计信息）",
            },
        },
        "required": ["texts"],
    }
    timeout = 120
    risk_level = "low"

    def __init__(self, provider: EmbeddingsProvider):
        self._provider = provider

    async def execute(self, texts: List[str], return_vectors: bool = False) -> str:
        """
        执行文本嵌入

        Args:
            texts: 要嵌入的文本列表
            return_vectors: 是否返回完整向量

        Returns:
            嵌入结果
        """
        if not texts:
            return "错误: 文本列表为空"

        if len(texts) > 100:
            return "错误: 单次最多处理 100 条文本"

        try:
            embeddings = await self._provider.embed(texts)

            if return_vectors:
                # 返回完整向量（可能很长）
                result = {
                    "count": len(embeddings),
                    "dimension": len(embeddings[0]) if embeddings else 0,
                    "embeddings": embeddings,
                }
                import json

                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                # 只返回统计信息
                return (
                    f"成功生成 {len(embeddings)} 个嵌入向量\n"
                    f"维度: {len(embeddings[0]) if embeddings else 0}\n"
                    f"模型: {self._provider.get_model_name()}"
                )

        except Exception as e:
            return f"嵌入生成失败: {str(e)}"


class ComputeSimilarityTool(BaseTool):
    """文本相似度计算工具"""

    name = "compute_similarity"
    description = "计算两个文本之间的语义相似度（余弦相似度），范围 0-1"
    parameters_schema = {
        "type": "object",
        "properties": {
            "text1": {
                "type": "string",
                "description": "第一个文本",
            },
            "text2": {
                "type": "string",
                "description": "第二个文本",
            },
        },
        "required": ["text1", "text2"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(self, provider: EmbeddingsProvider):
        self._provider = provider

    async def execute(self, text1: str, text2: str) -> str:
        """
        计算两个文本的语义相似度

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            相似度结果
        """
        try:
            import numpy as np

            # 生成嵌入
            embeddings = await self._provider.embed([text1, text2])

            if len(embeddings) != 2:
                return "错误: 嵌入生成失败"

            # 计算余弦相似度（向量已归一化，直接点积即可）
            vec1 = np.array(embeddings[0])
            vec2 = np.array(embeddings[1])
            similarity = float(np.dot(vec1, vec2))

            return (
                f"文本相似度: {similarity:.4f}\n"
                f"解释: {'高度相似' if similarity > 0.8 else '中等相似' if similarity > 0.5 else '差异较大' if similarity > 0.2 else '几乎不相关'}"
            )

        except Exception as e:
            return f"相似度计算失败: {str(e)}"


class LocalEmbeddingsPlugin(Plugin):
    """Local Embeddings 插件"""

    metadata = PluginMetadata(
        id="tool.local-embeddings",
        name="Local Embeddings",
        version="1.0.0",
        type=PluginType.TOOL,
        description="本地文本嵌入工具，基于 all-MiniLM-L6-v2 模型，支持文本向量化和语义相似度计算",
        author="Local",
        dependencies=[],
        optional_dependencies=[],
        provides=["embeddings.local", "embeddings.sentence-transformers"],
        priority=10,
    )

    def __init__(self):
        super().__init__()
        self._provider: EmbeddingsProvider = None
        self._tools: List[BaseTool] = []

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载"""
        await super().on_plugin_load(context)

        # 从配置获取参数
        config = context.config or {}

        # 确定模型路径
        model_path = config.get("model_path")
        if not model_path:
            # 默认使用插件目录下的模型
            plugin_dir = Path(__file__).parent
            local_model_path = plugin_dir / "models" / "all-MiniLM-L6-v2"
            if local_model_path.exists():
                model_path = str(local_model_path)

        # 创建嵌入提供者
        self._provider = EmbeddingsProvider(
            model_path=model_path,
            model_name=config.get("model_name", "all-MiniLM-L6-v2"),
            device=config.get("device", "cpu"),
            max_batch_size=config.get("max_batch_size", 4),
        )

        context.logger.info(
            f"Local Embeddings 插件加载完成 (model_path={model_path}, device={config.get('device', 'cpu')})"
        )

    async def on_plugin_activate(self) -> None:
        """插件激活"""
        await super().on_plugin_activate()

        # 创建工具实例
        self._tools = [
            EmbedTextTool(self._provider),
            ComputeSimilarityTool(self._provider),
        ]

        self.context.logger.info("Local Embeddings 插件已激活，提供 2 个工具")

    async def on_plugin_deactivate(self) -> None:
        """插件停用"""
        self._tools = []
        await super().on_plugin_deactivate()
        self.context.logger.info("Local Embeddings 插件已停用")

    def get_tools(self) -> List[BaseTool]:
        """返回插件提供的工具"""
        return self._tools


# 插件入口点
def create_plugin() -> Plugin:
    """创建插件实例"""
    return LocalEmbeddingsPlugin()

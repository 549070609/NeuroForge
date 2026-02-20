"""
Local Embeddings Python

基于 sentence-transformers 的本地文本嵌入模块
使用 all-MiniLM-L6-v2 模型，输出 384 维向量
"""

from .embeddings_provider import EmbeddingsProvider

__all__ = ["EmbeddingsProvider"]
__version__ = "1.0.0"

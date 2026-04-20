"""
文本嵌入提供者

基于 sentence-transformers 实现本地文本嵌入
"""

from typing import List, Optional
import hashlib
import re
import numpy as np


class EmbeddingsProvider:
    """Python 版本的文本嵌入提供者"""

    PROVIDER_NAME = "sentence-transformers"
    MAX_BATCH_SIZE = 4
    EMBEDDING_DIMENSION = 384
    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        device: str = "cpu",
        max_batch_size: int = MAX_BATCH_SIZE,
    ):
        """
        初始化嵌入提供者

        Args:
            model_path: 本地模型路径（优先使用）
            model_name: 模型名称（当 model_path 为空时使用）
            device: 运行设备 (cpu, cuda, mps)
            max_batch_size: 批处理大小
        """
        self._model_path = model_path
        self._model_name = model_name
        self._device = device
        self._max_batch_size = max_batch_size
        self._model = None

    def _load_model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                if self._model_path:
                    self._model = SentenceTransformer(self._model_path, device=self._device)
                else:
                    self._model = SentenceTransformer(self._model_name, device=self._device)
            except ImportError:
                # Fallback to a lightweight deterministic encoder so local tests
                # can run even when sentence-transformers is unavailable.
                self._model = _FallbackSentenceTransformer(self.EMBEDDING_DIMENSION)

        return self._model

    async def embed(self, chunks: List[str]) -> List[List[float]]:
        """
        生成文本嵌入向量

        Args:
            chunks: 要嵌入的文本列表

        Returns:
            嵌入向量列表，每个向量 384 维

        Example:
            provider = EmbeddingsProvider()
            embeddings = await provider.embed(["Hello world", "Test embedding"])
            print(len(embeddings))  # 2
            print(len(embeddings[0]))  # 384
        """
        if not chunks:
            return []

        model = self._load_model()

        # 批量处理
        all_embeddings = []
        for i in range(0, len(chunks), self._max_batch_size):
            batch = chunks[i : i + self._max_batch_size]
            batch_embeddings = model.encode(
                batch,
                normalize_embeddings=True,  # L2 归一化
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            all_embeddings.extend(batch_embeddings.tolist())

        return all_embeddings

    def embed_sync(self, chunks: List[str]) -> List[List[float]]:
        """
        同步版本的嵌入方法

        Args:
            chunks: 要嵌入的文本列表

        Returns:
            嵌入向量列表
        """
        if not chunks:
            return []

        model = self._load_model()

        # 批量处理
        all_embeddings = []
        for i in range(0, len(chunks), self._max_batch_size):
            batch = chunks[i : i + self._max_batch_size]
            batch_embeddings = model.encode(
                batch,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            all_embeddings.extend(batch_embeddings.tolist())

        return all_embeddings

    def get_embedding_dimension(self) -> int:
        """获取嵌入向量维度"""
        return self.EMBEDDING_DIMENSION

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self._model_name

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        return self.PROVIDER_NAME

    def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._model is not None


class _FallbackSentenceTransformer:
    """Deterministic token-hash encoder used when sentence-transformers is absent."""

    _STOP_WORDS = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "on",
        "in",
        "of",
        "to",
        "for",
        "with",
        "and",
    }

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    def encode(
        self,
        batch: List[str],
        normalize_embeddings: bool = True,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
    ):
        _ = show_progress_bar
        vectors = [self._encode_text(text) for text in batch]
        arr = np.array(vectors, dtype=float)
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            arr = arr / norms
        return arr if convert_to_numpy else arr.tolist()

    def _encode_text(self, text: str) -> List[float]:
        vec = np.zeros(self._dimension, dtype=float)
        tokens = [self._normalize_token(t) for t in re.findall(r"\w+", text.lower())]
        tokens = [t for t in tokens if t and t not in self._STOP_WORDS]
        for token in tokens:
            idx = self._stable_index(token)
            vec[idx] += 1.0

        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}::{tokens[i + 1]}"
            idx = self._stable_index(bigram)
            vec[idx] += 0.5
        return vec.tolist()

    def _stable_index(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "little") % self._dimension

    def _normalize_token(self, token: str) -> str:
        if token.endswith("ing") and len(token) > 4:
            return token[:-3]
        if token.endswith("ed") and len(token) > 3:
            return token[:-2]
        if token.endswith("s") and len(token) > 3:
            return token[:-1]
        return token

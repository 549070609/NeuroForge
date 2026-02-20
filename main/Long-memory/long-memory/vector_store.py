"""
ChromaDB 向量存储封装

提供记忆的存储、搜索、删除等功能
"""

from typing import Any, Dict, List, Optional
import logging

try:
    from .models import MemoryEntry, MemorySearchResult, MemoryStats, MessageType, MemorySource
    from .config import LongMemoryConfig
except ImportError:
    # 支持独立运行时的导入
    from models import MemoryEntry, MemorySearchResult, MemoryStats, MessageType, MemorySource
    from config import LongMemoryConfig

logger = logging.getLogger(__name__)


class LocalEmbeddingFunction:
    """
    ChromaDB 嵌入函数适配器

    将 EmbeddingsProvider 适配为 ChromaDB 需要的格式
    """

    def __init__(self, embeddings_provider):
        """
        初始化嵌入函数

        Args:
            embeddings_provider: EmbeddingsProvider 实例
        """
        self._provider = embeddings_provider

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        ChromaDB 调用接口（同步）

        Args:
            input: 文本列表

        Returns:
            嵌入向量列表
        """
        return self._provider.embed_sync(input)

    def name(self) -> str:
        """返回嵌入函数名称（ChromaDB 要求）"""
        return "local_embeddings"

    def embed_query(self, input: List[str]) -> List[List[float]]:
        """查询文本嵌入（ChromaDB 1.5+ 要求）"""
        return self._provider.embed_sync(input)

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        """文档文本嵌入（ChromaDB 1.5+ 要求）"""
        return self._provider.embed_sync(input)


class ChromaVectorStore:
    """ChromaDB 向量存储"""

    def __init__(
        self,
        config: LongMemoryConfig,
        embeddings_provider,
    ):
        """
        初始化向量存储

        Args:
            config: 长记忆配置
            embeddings_provider: EmbeddingsProvider 实例
        """
        self._config = config
        self._provider = embeddings_provider
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        """确保 ChromaDB 已初始化"""
        if self._client is None:
            try:
                import chromadb
            except ImportError:
                raise ImportError(
                    "chromadb is required. Install with: pip install chromadb>=0.4.22"
                )

            # 确保目录存在
            self._config.ensure_directory()

            # 创建持久化客户端
            self._client = chromadb.PersistentClient(path=self._config.persist_directory)

            # 创建或获取集合
            self._collection = self._client.get_or_create_collection(
                name=self._config.collection_name,
                embedding_function=LocalEmbeddingFunction(self._provider),
                metadata={"hnsw:space": "cosine"}
            )

            logger.info(
                f"ChromaVectorStore initialized with {self._collection.count()} memories"
            )

    async def store(self, entry: MemoryEntry) -> str:
        """
        存储记忆

        Args:
            entry: 记忆条目

        Returns:
            记忆 ID
        """
        self._ensure_initialized()

        # 存储到 ChromaDB
        self._collection.add(
            ids=[entry.id],
            documents=[entry.content],
            metadatas=[entry.to_dict()],
        )

        logger.debug(f"Stored memory: {entry.id}")
        return entry.id

    async def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[MemorySearchResult]:
        """
        语义搜索记忆

        Args:
            query: 查询文本
            n_results: 返回结果数量
            where: 过滤条件（ChromaDB where 子句）

        Returns:
            搜索结果列表
        """
        self._ensure_initialized()

        # 限制结果数量
        n_results = min(n_results, self._config.max_search_limit)

        # 执行搜索
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # 解析结果
        search_results = []

        if not results["ids"] or not results["ids"][0]:
            return search_results

        for i, doc_id in enumerate(results["ids"][0]):
            try:
                metadata = results["metadatas"][0][i]
                entry = MemoryEntry.from_dict(metadata)
                distance = results["distances"][0][i] if results.get("distances") else 0

                # 将余弦距离转换为相似度分数 (0-1)
                # ChromaDB 使用余弦距离，distance 越小越相似
                score = max(0.0, 1.0 - distance)

                search_results.append(MemorySearchResult(
                    entry=entry,
                    score=score,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse search result {doc_id}: {e}")

        return search_results

    async def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        删除记忆

        Args:
            ids: 要删除的记忆 ID 列表
            where: 过滤条件（与 ids 互斥）

        Returns:
            删除的记忆数量
        """
        self._ensure_initialized()

        if ids:
            # 按 ID 删除
            self._collection.delete(ids=ids)
            count = len(ids)
            logger.debug(f"Deleted {count} memories by ID")
        elif where:
            # 按条件删除
            # 先查询要删除的 ID
            results = self._collection.get(where=where)
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                count = len(results["ids"])
                logger.debug(f"Deleted {count} memories by filter")
            else:
                count = 0
        else:
            count = 0

        return count

    async def list_memories(
        self,
        limit: int = 10,
        offset: int = 0,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryEntry]:
        """
        列出记忆

        Args:
            limit: 返回数量限制
            offset: 偏移量
            where: 过滤条件

        Returns:
            记忆条目列表
        """
        self._ensure_initialized()

        # ChromaDB 不支持 offset，我们获取更多然后切片
        fetch_limit = limit + offset

        results = self._collection.get(
            where=where,
            limit=fetch_limit,
            include=["documents", "metadatas"]
        )

        entries = []
        if results["ids"]:
            # 跳过 offset
            start = min(offset, len(results["ids"]))
            end = min(offset + limit, len(results["ids"]))

            for i in range(start, end):
                try:
                    metadata = results["metadatas"][i]
                    entry = MemoryEntry.from_dict(metadata)
                    entries.append(entry)
                except Exception as e:
                    logger.warning(f"Failed to parse memory {results['ids'][i]}: {e}")

        return entries

    async def get_stats(self) -> MemoryStats:
        """
        获取统计信息

        Returns:
            统计信息
        """
        self._ensure_initialized()

        total_count = self._collection.count()

        if total_count == 0:
            return MemoryStats(total_count=0)

        # 获取所有记忆用于统计
        results = self._collection.get(
            include=["metadatas"]
        )

        by_type: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        total_importance = 0.0
        timestamps = []
        sessions = set()

        if results["metadatas"]:
            for metadata in results["metadatas"]:
                # 统计类型
                msg_type = metadata.get("message_type", "user")
                by_type[msg_type] = by_type.get(msg_type, 0) + 1

                # 统计来源
                source = metadata.get("source", "manual")
                by_source[source] = by_source.get(source, 0) + 1

                # 统计重要性
                importance = float(metadata.get("importance", 0.5))
                total_importance += importance

                # 收集时间戳
                timestamp = metadata.get("timestamp", "")
                if timestamp:
                    timestamps.append(timestamp)

                # 收集会话
                session_id = metadata.get("session_id", "")
                if session_id:
                    sessions.add(session_id)

        stats = MemoryStats(
            total_count=total_count,
            by_type=by_type,
            by_source=by_source,
            avg_importance=total_importance / total_count if total_count > 0 else 0,
            oldest_timestamp=min(timestamps) if timestamps else "",
            newest_timestamp=max(timestamps) if timestamps else "",
            unique_sessions=len(sessions),
        )

        return stats

    async def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        根据 ID 获取记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆条目或 None
        """
        self._ensure_initialized()

        results = self._collection.get(
            ids=[memory_id],
            include=["metadatas"]
        )

        if results["ids"] and results["metadatas"]:
            try:
                return MemoryEntry.from_dict(results["metadatas"][0])
            except Exception as e:
                logger.warning(f"Failed to parse memory {memory_id}: {e}")

        return None

    async def clear(self) -> int:
        """
        清空所有记忆

        Returns:
            删除的记忆数量
        """
        self._ensure_initialized()

        count = self._collection.count()

        # 删除集合并重新创建
        self._client.delete_collection(self._config.collection_name)
        self._collection = self._client.create_collection(
            name=self._config.collection_name,
            embedding_function=LocalEmbeddingFunction(self._provider),
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(f"Cleared {count} memories")
        return count

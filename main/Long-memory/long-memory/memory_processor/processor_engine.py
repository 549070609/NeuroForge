"""
记忆加工引擎

核心处理逻辑，负责：
1. 单条记忆加工
2. 批量记忆加工
3. 重加工未处理的记忆
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

try:
    from ..models import MemoryEntry
    from ..vector_store import ChromaVectorStore
except ImportError:
    from models import MemoryEntry
    from vector_store import ChromaVectorStore

from .config import ProcessorConfig
from .llm_analyzer import LLMAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """加工结果"""

    memory_id: str
    success: bool
    analysis: Optional[AnalysisResult] = None
    error: Optional[str] = None
    original_entry: Optional[MemoryEntry] = None
    updated_entry: Optional[MemoryEntry] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "memory_id": self.memory_id,
            "success": self.success,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "error": self.error,
            "original": {
                "topic": self.original_entry.topic if self.original_entry else None,
                "tags": self.original_entry.tags if self.original_entry else None,
                "summary": self.original_entry.summary if self.original_entry else None,
            },
            "updated": {
                "topic": self.updated_entry.topic if self.updated_entry else None,
                "tags": self.updated_entry.tags if self.updated_entry else None,
                "summary": self.updated_entry.summary if self.updated_entry else None,
            } if self.updated_entry else None,
        }


class ProcessorEngine:
    """记忆加工引擎"""

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        config: ProcessorConfig,
        llm_client: Optional[Any] = None,
    ):
        """
        初始化引擎

        Args:
            vector_store: 向量存储
            config: 加工配置
            llm_client: LLM 客户端（可选）
        """
        self._store = vector_store
        self._config = config

        # 初始化分析器
        self._analyzer = LLMAnalyzer(
            llm_client=llm_client,
            tag_pool=config.flat_tag_pool,
            max_summary_length=config.max_summary_length,
            max_topic_length=config.max_topic_length,
            max_tags=config.max_tags,
            timeout=config.timeout,
            fallback_to_rules=config.fallback_to_rules,
        )

    async def process_memory(
        self,
        entry: MemoryEntry,
        force: bool = False,
    ) -> ProcessResult:
        """
        加工单条记忆

        Args:
            entry: 记忆条目
            force: 是否强制重新加工（即使已有标签/主题）

        Returns:
            加工结果
        """
        memory_id = entry.id

        # 检查是否需要加工
        if not force and self._is_already_processed(entry):
            logger.debug(f"Memory {memory_id} already processed, skipping")
            return ProcessResult(
                memory_id=memory_id,
                success=True,
                analysis=AnalysisResult(
                    tags=entry.tags,
                    topic=entry.topic,
                    summary=entry.summary,
                    confidence=1.0,
                    method="existing",
                ),
                original_entry=entry,
                updated_entry=entry,
            )

        try:
            # 分析内容
            analysis = await self._analyzer.analyze(entry.content)

            if analysis.confidence < 0.3:
                logger.warning(f"Low confidence analysis for {memory_id}: {analysis.confidence}")

            # 更新条目
            updated_entry = MemoryEntry(
                id=entry.id,
                content=entry.content,
                timestamp=entry.timestamp,
                session_id=entry.session_id,
                topic=analysis.topic or entry.topic,
                summary=analysis.summary,
                message_type=entry.message_type,
                source=entry.source,
                importance=entry.importance,
                tags=analysis.tags if analysis.tags else entry.tags,
                metadata=entry.metadata,
            )

            # 保存到存储
            success = await self._store.update(updated_entry)

            if success:
                logger.info(f"Processed memory {memory_id}: topic={analysis.topic}, tags={analysis.tags}")
                return ProcessResult(
                    memory_id=memory_id,
                    success=True,
                    analysis=analysis,
                    original_entry=entry,
                    updated_entry=updated_entry,
                )
            else:
                return ProcessResult(
                    memory_id=memory_id,
                    success=False,
                    error="Failed to update memory in store",
                    original_entry=entry,
                )

        except Exception as e:
            logger.error(f"Failed to process memory {memory_id}: {e}")
            return ProcessResult(
                memory_id=memory_id,
                success=False,
                error=str(e),
                original_entry=entry,
            )

    async def process_by_id(self, memory_id: str, force: bool = False) -> ProcessResult:
        """
        根据 ID 加工记忆

        Args:
            memory_id: 记忆 ID
            force: 是否强制重新加工

        Returns:
            加工结果
        """
        entry = await self._store.get_by_id(memory_id)
        if entry is None:
            return ProcessResult(
                memory_id=memory_id,
                success=False,
                error=f"Memory not found: {memory_id}",
            )

        return await self.process_memory(entry, force=force)

    async def process_batch(
        self,
        entries: List[MemoryEntry],
        force: bool = False,
    ) -> List[ProcessResult]:
        """
        批量加工记忆

        Args:
            entries: 记忆条目列表
            force: 是否强制重新加工

        Returns:
            加工结果列表
        """
        results = []
        for entry in entries:
            result = await self.process_memory(entry, force=force)
            results.append(result)
        return results

    async def reprocess_unprocessed(
        self,
        limit: int = 50,
    ) -> List[ProcessResult]:
        """
        重加工未处理的记忆

        查找没有标签、主题或摘要的记忆并加工

        Args:
            limit: 最大处理数量

        Returns:
            加工结果列表
        """
        # 获取所有记忆
        all_entries = await self._store.list_memories(limit=1000)

        # 过滤出未加工的
        unprocessed = []
        for entry in all_entries:
            if self._needs_processing(entry):
                unprocessed.append(entry)
                if len(unprocessed) >= limit:
                    break

        logger.info(f"Found {len(unprocessed)} unprocessed memories")

        # 批量处理
        return await self.process_batch(unprocessed, force=False)

    async def reprocess_by_filter(
        self,
        filter_tags: Optional[List[str]] = None,
        filter_topic: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProcessResult]:
        """
        根据过滤条件重加工

        Args:
            filter_tags: 只处理包含这些标签的记忆
            filter_topic: 只处理主题匹配的记忆
            limit: 最大处理数量

        Returns:
            加工结果列表
        """
        entries = await self._store.list_memories(limit=1000)

        to_process = []
        for entry in entries:
            # 标签过滤
            if filter_tags:
                if not any(tag in entry.tags for tag in filter_tags):
                    continue

            # 主题过滤
            if filter_topic:
                if filter_topic not in entry.topic:
                    continue

            to_process.append(entry)
            if len(to_process) >= limit:
                break

        return await self.process_batch(to_process, force=True)

    def _is_already_processed(self, entry: MemoryEntry) -> bool:
        """检查记忆是否已加工"""
        # 如果有标签、主题和摘要，认为已加工
        return bool(entry.tags and entry.topic and entry.summary)

    def _needs_processing(self, entry: MemoryEntry) -> bool:
        """检查记忆是否需要加工"""
        # 如果缺少标签、主题或摘要，需要加工
        return not (entry.tags and entry.topic and entry.summary)

    def update_llm_client(self, llm_client: Any) -> None:
        """更新 LLM 客户端"""
        self._analyzer.update_llm_client(llm_client)

    @property
    def config(self) -> ProcessorConfig:
        """获取配置"""
        return self._config

    @property
    def analyzer(self) -> LLMAnalyzer:
        """获取分析器"""
        return self._analyzer

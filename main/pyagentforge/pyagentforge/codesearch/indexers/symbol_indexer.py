"""
符号索引器

负责索引文件和目录中的符号
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Callable

from pyagentforge.codesearch.config import CodeSearchConfig
from pyagentforge.codesearch.parsers.base import ParserRegistry
from pyagentforge.codesearch.storage.database import CodeSearchDatabase
from pyagentforge.codesearch.storage.models import Symbol
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SymbolIndexer:
    """符号索引器"""

    def __init__(
        self,
        db: CodeSearchDatabase,
        parser_registry: ParserRegistry,
        config: CodeSearchConfig | None = None,
    ) -> None:
        self.db = db
        self.parser_registry = parser_registry
        self.config = config or CodeSearchConfig()
        self._progress_callback: Callable[[int, int], None] | None = None

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """设置进度回调函数"""
        self._progress_callback = callback

    async def index_directory(
        self,
        directory: Path,
        pattern: str = "*",
        incremental: bool = True,
    ) -> int:
        """
        索引目录中的所有文件

        Args:
            directory: 目录路径
            pattern: 文件模式
            incremental: 是否增量索引

        Returns:
            索引的文件数量
        """
        directory = Path(directory).resolve()
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return 0

        # 收集需要索引的文件
        files_to_index = await self._collect_files(directory, pattern)

        if not files_to_index:
            logger.info(f"No files to index in {directory}")
            return 0

        total_files = len(files_to_index)
        indexed_count = 0

        logger.info(
            "Starting directory indexing",
            extra_data={"directory": str(directory), "total_files": total_files},
        )

        # 增量索引：过滤已索引且未变更的文件
        if incremental:
            files_to_index = [
                f for f in files_to_index
                if await self._needs_reindex(f)
            ]
            logger.info(
                f"Incremental indexing: {len(files_to_index)}/{total_files} files need reindexing"
            )

        # 并行索引文件
        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def index_with_semaphore(file_path: Path) -> list[Symbol]:
            async with semaphore:
                return await self._index_file(file_path)

        # 分批处理
        batch_size = 50
        all_symbols: list[Symbol] = []

        for i in range(0, len(files_to_index), batch_size):
            batch = files_to_index[i:i + batch_size]
            results = await asyncio.gather(*[index_with_semaphore(f) for f in batch])

            for symbols in results:
                all_symbols.extend(symbols)

            indexed_count += len(batch)

            # 进度回调
            if self._progress_callback:
                self._progress_callback(indexed_count, len(files_to_index))

            # 批量存储
            if all_symbols:
                await self.db.store_symbols(all_symbols)
                all_symbols.clear()

        logger.info(
            "Directory indexing complete",
            extra_data={"directory": str(directory), "indexed_files": indexed_count},
        )

        return indexed_count

    async def index_file(self, file_path: Path) -> list[Symbol]:
        """索引单个文件"""
        return await self._index_file(file_path)

    async def _collect_files(self, directory: Path, pattern: str) -> list[Path]:
        """收集需要索引的文件"""
        files: list[Path] = []

        for file_path in directory.rglob(pattern):
            if not file_path.is_file():
                continue

            # 检查文件是否应该被索引
            if not self.config.should_index_file(file_path):
                continue

            # 检查文件大小
            try:
                size_kb = file_path.stat().st_size / 1024
                if size_kb > self.config.max_file_size_kb:
                    logger.debug(f"Skipping large file: {file_path} ({size_kb:.1f}KB)")
                    continue
            except OSError:
                continue

            files.append(file_path)

        return files

    async def _needs_reindex(self, file_path: Path) -> bool:
        """检查文件是否需要重新索引"""
        try:
            stat = file_path.stat()
            file_hash = await self._compute_file_hash(file_path)

            # 查询数据库中的哈希记录
            stored_hash = await self.db.get_file_hash(str(file_path))

            if stored_hash is None:
                # 新文件，需要索引
                return True

            # 检查内容哈希
            if stored_hash.content_hash != file_hash:
                return True

            # 检查修改时间（作为后备）
            if stored_hash.modified_time < stat.st_mtime:
                return True

            return False

        except Exception as e:
            logger.debug(f"Error checking file hash: {e}")
            return True

    async def _index_file(self, file_path: Path) -> list[Symbol]:
        """索引单个文件"""
        try:
            # 读取文件内容
            content = await asyncio.to_thread(self._read_file, file_path)

            # 计算哈希
            file_hash = hashlib.md5(content.encode()).hexdigest()

            # 获取语言
            language = self.config.matches_language(file_path)
            if not language:
                language = file_path.suffix.lstrip(".")

            # 获取解析器
            parser = self.parser_registry.get_parser(language)
            if not parser:
                logger.debug(f"No parser for language: {language}")
                return []

            # 解析文件
            symbols = await parser.parse_file(content, file_path)

            # 更新文件哈希记录
            stat = file_path.stat()
            await self.db.update_file_hash(
                file_path=str(file_path),
                content_hash=file_hash,
                file_size=stat.st_size,
                modified_time=stat.st_mtime,
                symbol_count=len(symbols),
            )

            logger.debug(
                f"Indexed file: {file_path}",
                extra_data={"symbols": len(symbols)},
            )

            return symbols

        except Exception as e:
            logger.warning(
                f"Failed to index file: {file_path}",
                extra_data={"error": str(e)},
            )
            return []

    def _read_file(self, file_path: Path) -> str:
        """同步读取文件内容"""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    async def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件内容哈希"""
        content = await asyncio.to_thread(self._read_file, file_path)
        return hashlib.md5(content.encode()).hexdigest()

    async def remove_file(self, file_path: Path) -> None:
        """从索引中移除文件"""
        await self.db.delete_file_symbols(str(file_path))
        logger.info(f"Removed file from index: {file_path}")

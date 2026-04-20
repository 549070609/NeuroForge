"""
CodeSearch 数据库管理器

SQLite 后端存储
"""

import json
from datetime import datetime
from typing import Any

import aiosqlite

from pyagentforge.codesearch.storage.models import FileHash, Symbol, SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CodeSearchDatabase:
    """CodeSearch SQLite 数据库管理器"""

    def __init__(self, db_path: str = ":memory:"):
        """
        初始化数据库

        Args:
            db_path: 数据库路径, 默认内存数据库
        """
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """初始化数据库表"""
        self._db = await aiosqlite.connect(self.db_path)
        # 启用 WAL 模式提高并发性能
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        logger.info(
            "CodeSearch database initialized",
            extra_data={"db_path": self.db_path},
        )

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            self._db = None

    async def _create_tables(self) -> None:
        """创建数据库表"""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS codesearch_symbols (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                column_start INTEGER NOT NULL,
                column_end INTEGER NOT NULL,
                language TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                parent_scope TEXT,
                docstring TEXT,
                signature TEXT,
                metadata TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_name
                ON codesearch_symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_kind
                ON codesearch_symbols(kind);
            CREATE INDEX IF NOT EXISTS idx_symbols_file
                ON codesearch_symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_symbols_language
                ON codesearch_symbols(language);
            CREATE INDEX IF NOT EXISTS idx_symbols_name_kind
                ON codesearch_symbols(name, kind);

            CREATE TABLE IF NOT EXISTS codesearch_file_hashes (
                file_path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                symbol_count INTEGER DEFAULT 0,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._db.commit()

    async def store_symbols(self, symbols: list[Symbol]) -> None:
        """批量存储符号"""
        if not symbols:
            return

        await self._db.executemany("""
            INSERT OR REPLACE INTO codesearch_symbols
            (id, name, kind, file_path, line_start, line_end,
             column_start, column_end, language, file_hash,
             parent_scope, docstring, signature, metadata, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                s.id, s.name, s.kind.value, s.file_path,
                s.line_start, s.line_end, s.column_start, s.column_end,
                s.language, s.file_hash, s.parent_scope,
                s.docstring, s.signature, json.dumps(s.metadata), s.indexed_at.isoformat()
            )
            for s in symbols
        ])
        await self._db.commit()

    async def search_symbols(
        self,
        name: str | None = None,
        kind: SymbolKind | None = None,
        file_pattern: str | None = None,
        language: str | None = None,
        limit: int = 100,
    ) -> list[Symbol]:
        """搜索符号"""
        conditions = []
        params: list[Any] = []

        if name:
            conditions.append("name LIKE ?")
            params.append(f"%{name}%")
        if kind:
            conditions.append("kind = ?")
            params.append(kind.value)
        if file_pattern:
            conditions.append("file_path LIKE ?")
            params.append(f"%{file_pattern}%")
        if language:
            conditions.append("language = ?")
            params.append(language)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT id, name, kind, file_path, line_start, line_end,
                   column_start, column_end, language, file_hash,
                   parent_scope, docstring, signature, metadata, indexed_at
            FROM codesearch_symbols
            WHERE {where_clause}
            ORDER BY indexed_at DESC
            LIMIT ?
        """
        params.append(limit)

        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_symbol(row) for row in rows]

    async def get_file_hash(self, file_path: str) -> FileHash | None:
        """获取文件哈希记录"""
        async with self._db.execute(
            "SELECT file_path, content_hash, file_size, modified_time, symbol_count, indexed_at FROM codesearch_file_hashes WHERE file_path = ?",
            (file_path,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return FileHash(
                    file_path=row[0],
                    content_hash=row[1],
                    file_size=row[2],
                    modified_time=row[3],
                    symbol_count=row[4],
                    indexed_at=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow(),
                )
            return None

    async def update_file_hash(
        self,
        file_path: str,
        content_hash: str,
        file_size: int,
        modified_time: float,
        symbol_count: int = 0,
    ) -> None:
        """更新文件哈希记录"""
        await self._db.execute("""
            INSERT OR REPLACE INTO codesearch_file_hashes
            (file_path, content_hash, file_size, modified_time, symbol_count, indexed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (file_path, content_hash, file_size, modified_time, symbol_count))
        await self._db.commit()

    async def delete_file_symbols(self, file_path: str) -> None:
        """删除文件的所有符号"""
        await self._db.execute(
            "DELETE FROM codesearch_symbols WHERE file_path = ?",
            (file_path,)
        )
        await self._db.execute(
            "DELETE FROM codesearch_file_hashes WHERE file_path = ?",
            (file_path,)
        )
        await self._db.commit()

    async def get_stats(self) -> dict[str, int]:
        """获取索引统计信息"""
        async with self._db.execute(
            "SELECT COUNT(*) FROM codesearch_symbols"
        ) as cursor:
            symbol_count = (await cursor.fetchone())[0]

        async with self._db.execute(
            "SELECT COUNT(*) FROM codesearch_file_hashes"
        ) as cursor:
            file_count = (await cursor.fetchone())[0]

        return {
            "symbol_count": symbol_count,
            "file_count": file_count,
        }

    async def clear_all(self) -> None:
        """清除所有索引数据"""
        await self._db.execute("DELETE FROM codesearch_symbols")
        await self._db.execute("DELETE FROM codesearch_file_hashes")
        await self._db.commit()

    def _row_to_symbol(self, row: tuple) -> Symbol:
        """将数据库行转换为 Symbol"""
        return Symbol(
            id=row[0],
            name=row[1],
            kind=SymbolKind(row[2]),
            file_path=row[3],
            line_start=row[4],
            line_end=row[5],
            column_start=row[6],
            column_end=row[7],
            language=row[8],
            file_hash=row[9],
            parent_scope=row[10],
            docstring=row[11],
            signature=row[12],
            metadata=json.loads(row[13]) if row[13] else {},
            indexed_at=datetime.fromisoformat(row[14]) if row[14] else datetime.utcnow(),
        )

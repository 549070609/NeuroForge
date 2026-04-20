"""Persistence module - unified storage backends for runtime state."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_ts() -> int:
    return int(time.time())


@dataclass(slots=True)
class StoreRecord:
    """Stored state record."""

    namespace: str
    key: str
    value: dict[str, Any]
    version: int
    updated_at: int
    expires_at: int | None = None

    def is_expired(self, now_ts: int | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = _now_ts() if now_ts is None else now_ts
        return self.expires_at <= current


@dataclass(slots=True)
class StoreWriteResult:
    """Write result with optimistic-concurrency feedback."""

    applied: bool
    record: StoreRecord | None = None
    reason: str | None = None


class StateStore(ABC):
    """Unified state store for session/task/plan/workflow data."""

    @abstractmethod
    async def get(self, key: str, *, namespace: str = "session") -> StoreRecord | None:
        """Get a state record by key."""

    @abstractmethod
    async def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        namespace: str = "session",
        ttl: int | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> StoreWriteResult:
        """Upsert a state record."""

    @abstractmethod
    async def delete(
        self,
        key: str,
        *,
        namespace: str = "session",
        expected_version: int | None = None,
    ) -> bool:
        """Delete a state record."""

    @abstractmethod
    async def exists(self, key: str, *, namespace: str = "session") -> bool:
        """Check whether a key exists and is not expired."""

    @abstractmethod
    async def list(
        self,
        *,
        namespace: str = "session",
        prefix: str | None = None,
    ) -> list[StoreRecord]:
        """List state records in a namespace."""

    @abstractmethod
    async def clear(self, *, namespace: str | None = None) -> None:
        """Clear state records."""

    @abstractmethod
    async def close(self) -> None:
        """Close store resources."""


class MemoryStore(StateStore):
    """In-memory state store with TTL/idempotency/version support."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], StoreRecord] = {}
        self._idempotency: dict[tuple[str, str, str], StoreRecord] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _clone(record: StoreRecord | None) -> StoreRecord | None:
        if record is None:
            return None
        return StoreRecord(
            namespace=record.namespace,
            key=record.key,
            value=copy.deepcopy(record.value),
            version=record.version,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
        )

    def _purge_expired_unlocked(self, now_ts: int) -> None:
        expired_keys = [
            key for key, record in self._data.items() if record.is_expired(now_ts)
        ]
        for namespace, record_key in expired_keys:
            self._data.pop((namespace, record_key), None)
            for idem_key in list(self._idempotency.keys()):
                if idem_key[0] == namespace and idem_key[1] == record_key:
                    self._idempotency.pop(idem_key, None)

    async def get(self, key: str, *, namespace: str = "session") -> StoreRecord | None:
        async with self._lock:
            self._purge_expired_unlocked(_now_ts())
            return self._clone(self._data.get((namespace, key)))

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        namespace: str = "session",
        ttl: int | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> StoreWriteResult:
        async with self._lock:
            now_ts = _now_ts()
            self._purge_expired_unlocked(now_ts)

            if idempotency_key:
                replay = self._idempotency.get((namespace, key, idempotency_key))
                if replay is not None:
                    return StoreWriteResult(
                        applied=False,
                        record=self._clone(replay),
                        reason="idempotent_replay",
                    )

            current = self._data.get((namespace, key))
            if expected_version is not None:
                if current is None and expected_version != 0:
                    return StoreWriteResult(
                        applied=False,
                        record=None,
                        reason="version_conflict",
                    )
                if current is not None and current.version != expected_version:
                    return StoreWriteResult(
                        applied=False,
                        record=self._clone(current),
                        reason="version_conflict",
                    )

            version = 1 if current is None else current.version + 1
            expires_at = (now_ts + ttl) if ttl is not None else None
            record = StoreRecord(
                namespace=namespace,
                key=key,
                value=copy.deepcopy(value),
                version=version,
                updated_at=now_ts,
                expires_at=expires_at,
            )
            self._data[(namespace, key)] = record
            if idempotency_key:
                self._idempotency[(namespace, key, idempotency_key)] = record
            return StoreWriteResult(applied=True, record=self._clone(record))

    async def delete(
        self,
        key: str,
        *,
        namespace: str = "session",
        expected_version: int | None = None,
    ) -> bool:
        async with self._lock:
            now_ts = _now_ts()
            self._purge_expired_unlocked(now_ts)
            current = self._data.get((namespace, key))
            if current is None:
                return False
            if expected_version is not None and current.version != expected_version:
                return False

            self._data.pop((namespace, key), None)
            for idem_key in list(self._idempotency.keys()):
                if idem_key[0] == namespace and idem_key[1] == key:
                    self._idempotency.pop(idem_key, None)
            return True

    async def exists(self, key: str, *, namespace: str = "session") -> bool:
        return await self.get(key, namespace=namespace) is not None

    async def list(
        self,
        *,
        namespace: str = "session",
        prefix: str | None = None,
    ) -> list[StoreRecord]:
        async with self._lock:
            now_ts = _now_ts()
            self._purge_expired_unlocked(now_ts)
            records = [
                self._clone(record)
                for (ns, record_key), record in self._data.items()
                if ns == namespace and (prefix is None or record_key.startswith(prefix))
            ]
            return [record for record in records if record is not None]

    async def clear(self, *, namespace: str | None = None) -> None:
        async with self._lock:
            if namespace is None:
                self._data.clear()
                self._idempotency.clear()
                return

            for namespaced_key in list(self._data.keys()):
                if namespaced_key[0] == namespace:
                    self._data.pop(namespaced_key, None)
            for idem_key in list(self._idempotency.keys()):
                if idem_key[0] == namespace:
                    self._idempotency.pop(idem_key, None)

    async def close(self) -> None:
        return None


class SQLiteStateStore(StateStore):
    """SQLite-backed state store with persistence and optimistic concurrency."""

    def __init__(self, sqlite_path: str | Path) -> None:
        self._path = Path(sqlite_path)
        self._init_lock = asyncio.Lock()
        self._op_lock = asyncio.Lock()
        self._initialized = False
        self._conn: Any = None

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)

            import aiosqlite

            self._conn = await aiosqlite.connect(str(self._path))
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_store (
                    namespace TEXT NOT NULL,
                    store_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    PRIMARY KEY(namespace, store_key)
                )
                """
            )
            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_idempotency (
                    namespace TEXT NOT NULL,
                    store_key TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    PRIMARY KEY(namespace, store_key, idempotency_key)
                )
                """
            )
            await self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_state_store_expires
                ON state_store(namespace, expires_at)
                """
            )
            await self._conn.commit()
            self._initialized = True

    @staticmethod
    def _to_record(row: Any) -> StoreRecord:
        return StoreRecord(
            namespace=row["namespace"],
            key=row["store_key"],
            value=json.loads(row["value_json"]),
            version=int(row["version"]),
            updated_at=int(row["updated_at"]),
            expires_at=row["expires_at"],
        )

    async def _purge_expired_for_key(self, namespace: str, key: str, now_ts: int) -> None:
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT expires_at
            FROM state_store
            WHERE namespace = ? AND store_key = ?
            """,
            (namespace, key),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return
        expires_at = row["expires_at"]
        if expires_at is not None and int(expires_at) <= now_ts:
            await self._conn.execute(
                """
                DELETE FROM state_store
                WHERE namespace = ? AND store_key = ?
                """,
                (namespace, key),
            )
            await self._conn.execute(
                """
                DELETE FROM state_idempotency
                WHERE namespace = ? AND store_key = ?
                """,
                (namespace, key),
            )

    async def _purge_expired_namespace(self, namespace: str, now_ts: int) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            DELETE FROM state_store
            WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at <= ?
            """,
            (namespace, now_ts),
        )
        await self._conn.execute(
            """
            DELETE FROM state_idempotency
            WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at <= ?
            """,
            (namespace, now_ts),
        )

    async def get(self, key: str, *, namespace: str = "session") -> StoreRecord | None:
        await self._ensure_initialized()
        assert self._conn is not None
        async with self._op_lock:
            now_ts = _now_ts()
            await self._purge_expired_for_key(namespace, key, now_ts)
            await self._conn.commit()
            cursor = await self._conn.execute(
                """
                SELECT namespace, store_key, value_json, version, updated_at, expires_at
                FROM state_store
                WHERE namespace = ? AND store_key = ?
                """,
                (namespace, key),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                return None
            return self._to_record(row)

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        namespace: str = "session",
        ttl: int | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> StoreWriteResult:
        await self._ensure_initialized()
        assert self._conn is not None
        async with self._op_lock:
            now_ts = _now_ts()
            await self._conn.execute("BEGIN IMMEDIATE")
            try:
                await self._purge_expired_for_key(namespace, key, now_ts)

                if idempotency_key:
                    replay_cursor = await self._conn.execute(
                        """
                        SELECT namespace, store_key, value_json, version, updated_at, expires_at
                        FROM state_idempotency
                        WHERE namespace = ? AND store_key = ? AND idempotency_key = ?
                        """,
                        (namespace, key, idempotency_key),
                    )
                    replay_row = await replay_cursor.fetchone()
                    await replay_cursor.close()
                    if replay_row is not None:
                        await self._conn.commit()
                        return StoreWriteResult(
                            applied=False,
                            record=self._to_record(replay_row),
                            reason="idempotent_replay",
                        )

                current_cursor = await self._conn.execute(
                    """
                    SELECT namespace, store_key, value_json, version, updated_at, expires_at
                    FROM state_store
                    WHERE namespace = ? AND store_key = ?
                    """,
                    (namespace, key),
                )
                current_row = await current_cursor.fetchone()
                await current_cursor.close()

                if expected_version is not None:
                    if current_row is None and expected_version != 0:
                        await self._conn.rollback()
                        return StoreWriteResult(
                            applied=False,
                            record=None,
                            reason="version_conflict",
                        )
                    if current_row is not None and int(current_row["version"]) != expected_version:
                        await self._conn.rollback()
                        return StoreWriteResult(
                            applied=False,
                            record=self._to_record(current_row),
                            reason="version_conflict",
                        )

                new_version = 1 if current_row is None else int(current_row["version"]) + 1
                expires_at = (now_ts + ttl) if ttl is not None else None
                payload = json.dumps(value, ensure_ascii=False)

                await self._conn.execute(
                    """
                    INSERT INTO state_store(namespace, store_key, value_json, version, updated_at, expires_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, store_key)
                    DO UPDATE SET
                        value_json = excluded.value_json,
                        version = excluded.version,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (namespace, key, payload, new_version, now_ts, expires_at),
                )

                if idempotency_key:
                    await self._conn.execute(
                        """
                        INSERT OR REPLACE INTO state_idempotency(
                            namespace, store_key, idempotency_key, value_json, version, updated_at, expires_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?)
                        """,
                        (namespace, key, idempotency_key, payload, new_version, now_ts, expires_at),
                    )

                await self._conn.commit()

                return StoreWriteResult(
                    applied=True,
                    record=StoreRecord(
                        namespace=namespace,
                        key=key,
                        value=copy.deepcopy(value),
                        version=new_version,
                        updated_at=now_ts,
                        expires_at=expires_at,
                    ),
                )
            except Exception:
                await self._conn.rollback()
                raise

    async def delete(
        self,
        key: str,
        *,
        namespace: str = "session",
        expected_version: int | None = None,
    ) -> bool:
        await self._ensure_initialized()
        assert self._conn is not None
        async with self._op_lock:
            now_ts = _now_ts()
            await self._conn.execute("BEGIN IMMEDIATE")
            try:
                await self._purge_expired_for_key(namespace, key, now_ts)
                cursor = await self._conn.execute(
                    """
                    SELECT version
                    FROM state_store
                    WHERE namespace = ? AND store_key = ?
                    """,
                    (namespace, key),
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row is None:
                    await self._conn.commit()
                    return False
                if expected_version is not None and int(row["version"]) != expected_version:
                    await self._conn.rollback()
                    return False

                await self._conn.execute(
                    """
                    DELETE FROM state_store
                    WHERE namespace = ? AND store_key = ?
                    """,
                    (namespace, key),
                )
                await self._conn.execute(
                    """
                    DELETE FROM state_idempotency
                    WHERE namespace = ? AND store_key = ?
                    """,
                    (namespace, key),
                )
                await self._conn.commit()
                return True
            except Exception:
                await self._conn.rollback()
                raise

    async def exists(self, key: str, *, namespace: str = "session") -> bool:
        return await self.get(key, namespace=namespace) is not None

    async def list(
        self,
        *,
        namespace: str = "session",
        prefix: str | None = None,
    ) -> list[StoreRecord]:
        await self._ensure_initialized()
        assert self._conn is not None
        async with self._op_lock:
            now_ts = _now_ts()
            await self._purge_expired_namespace(namespace, now_ts)
            await self._conn.commit()

            query = """
                SELECT namespace, store_key, value_json, version, updated_at, expires_at
                FROM state_store
                WHERE namespace = ?
            """
            params: list[Any] = [namespace]
            if prefix:
                query += " AND store_key LIKE ?"
                params.append(f"{prefix}%")
            query += " ORDER BY updated_at DESC"

            cursor = await self._conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            await cursor.close()
            return [self._to_record(row) for row in rows]

    async def clear(self, *, namespace: str | None = None) -> None:
        await self._ensure_initialized()
        assert self._conn is not None
        async with self._op_lock:
            if namespace is None:
                await self._conn.execute("DELETE FROM state_store")
                await self._conn.execute("DELETE FROM state_idempotency")
            else:
                await self._conn.execute(
                    "DELETE FROM state_store WHERE namespace = ?",
                    (namespace,),
                )
                await self._conn.execute(
                    "DELETE FROM state_idempotency WHERE namespace = ?",
                    (namespace,),
                )
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._initialized = False


# Backward-compatible alias
SessionStore = StateStore


def create_store(settings: Any) -> StateStore:
    """
    Factory function to create appropriate store.

    Priority:
      1. Redis (if enabled and implementation available)
      2. SQLite (default persistent backend)
      3. In-memory fallback
    """
    if getattr(settings, "redis_url", None) and getattr(settings, "redis_enabled", False):
        try:
            from .redis_store import RedisStore

            return RedisStore(settings.redis_url)
        except ImportError:
            logger.warning("Redis backend unavailable, falling back to SQLite/Memory")

    sqlite_path = getattr(settings, "sqlite_path", None)
    if sqlite_path:
        return SQLiteStateStore(sqlite_path)

    logger.warning("No persistent store configured, using MemoryStore")
    return MemoryStore()

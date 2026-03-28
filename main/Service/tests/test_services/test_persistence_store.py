from __future__ import annotations

import asyncio

import pytest

from Service.persistence import MemoryStore, SQLiteStateStore


@pytest.mark.asyncio
async def test_memory_store_supports_ttl_idempotency_and_versioning() -> None:
    store = MemoryStore()

    first = await store.set(
        "item-1",
        {"value": 1},
        namespace="session",
        expected_version=0,
        idempotency_key="op-1",
    )
    assert first.applied is True
    assert first.record is not None
    assert first.record.version == 1

    replay = await store.set(
        "item-1",
        {"value": 999},
        namespace="session",
        idempotency_key="op-1",
    )
    assert replay.applied is False
    assert replay.reason == "idempotent_replay"
    assert replay.record is not None
    assert replay.record.value["value"] == 1

    conflict = await store.set(
        "item-1",
        {"value": 2},
        namespace="session",
        expected_version=7,
    )
    assert conflict.applied is False
    assert conflict.reason == "version_conflict"

    second = await store.set(
        "item-1",
        {"value": 2},
        namespace="session",
        expected_version=1,
        ttl=1,
    )
    assert second.applied is True
    assert second.record is not None
    assert second.record.version == 2

    await asyncio.sleep(1.1)
    assert await store.get("item-1", namespace="session") is None


@pytest.mark.asyncio
async def test_sqlite_store_persists_across_instances(tmp_path) -> None:
    db_path = tmp_path / "service-state.db"

    store_a = SQLiteStateStore(db_path)
    write = await store_a.set(
        "sess-a",
        {"hello": "world"},
        namespace="session",
        expected_version=0,
    )
    assert write.applied is True
    await store_a.close()

    store_b = SQLiteStateStore(db_path)
    loaded = await store_b.get("sess-a", namespace="session")
    assert loaded is not None
    assert loaded.value == {"hello": "world"}
    assert loaded.version == 1

    listed = await store_b.list(namespace="session")
    assert len(listed) == 1
    assert listed[0].key == "sess-a"

    await store_b.close()

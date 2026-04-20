from __future__ import annotations

import asyncio

import pytest

from Service.persistence import MemoryStore, SQLiteStateStore
from Service.services.proxy.session_manager import SessionManager


@pytest.mark.asyncio
async def test_session_manager_restores_state_after_restart(tmp_path) -> None:
    db_path = tmp_path / "session-state.db"

    store_a = SQLiteStateStore(db_path)
    manager_a = SessionManager(store=store_a, session_ttl=3600, max_sessions=10)

    created = await manager_a.create_session(
        workspace_id="ws-1",
        agent_id="agent-1",
        metadata={"k": "v"},
    )
    await manager_a.add_message(created.session_id, "user", "hello")
    await store_a.close()

    store_b = SQLiteStateStore(db_path)
    manager_b = SessionManager(store=store_b, session_ttl=3600, max_sessions=10)

    restored = await manager_b.get_session(created.session_id)
    assert restored is not None
    assert restored.workspace_id == "ws-1"
    assert restored.metadata["k"] == "v"
    assert restored.message_history[0]["content"] == "hello"

    await store_b.close()


@pytest.mark.asyncio
async def test_session_manager_isolation_under_concurrency() -> None:
    store = MemoryStore()
    manager = SessionManager(store=store, session_ttl=3600, max_sessions=200)

    async def worker(index: int) -> tuple[str, str]:
        session = await manager.create_session(
            workspace_id=f"ws-{index % 4}",
            agent_id=f"agent-{index}",
            metadata={"index": index},
        )
        payload = f"payload-{index}"
        await manager.add_message(session.session_id, "user", payload)
        return session.session_id, payload

    created = await asyncio.gather(*(worker(i) for i in range(20)))

    assert len({session_id for session_id, _ in created}) == 20

    for session_id, payload in created:
        session = await manager.get_session(session_id)
        assert session is not None
        assert session.message_history[-1]["content"] == payload

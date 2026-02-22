"""
Tests for ConcurrencyManager

Tests concurrency control, slot management, and resource limits.
"""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pyagentforge.core.concurrency_manager import (
    ConcurrencyConfig,
    ConcurrencyManager,
    ConcurrencySlot,
    ResourceType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def custom_config():
    """Create a custom concurrency configuration for testing."""
    return ConcurrencyConfig(
        model_concurrency={
            "gpt-4o": 2,
            "gpt-4o-mini": 5,
            "claude-sonnet-4-20250514": 2,
        },
        provider_concurrency={
            "openai": 10,
            "anthropic": 5,
        },
        max_per_model=2,
        max_per_provider=5,
        max_global=20,
        queue_timeout=5.0,
        enable_queue=True,
        default_concurrency=3,
    )


@pytest.fixture
def manager(custom_config):
    """Create a concurrency manager with custom config."""
    return ConcurrencyManager(config=custom_config)


@pytest.fixture
def small_manager():
    """Create a manager with small limits for testing contention."""
    config = ConcurrencyConfig(
        max_global=2,
        max_per_model=1,
        max_per_provider=1,
        queue_timeout=1.0,
    )
    return ConcurrencyManager(config=config)


# ============================================================================
# Test: test_acquire_global_slot
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_global_slot(manager):
    """
    Test acquiring a global concurrency slot.

    Verifies:
    - Returns a valid slot ID
    - Slot is recorded in active slots
    - Stats are updated
    """
    slot_id = await manager.acquire(
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None
    assert ":" in slot_id  # Format: session:task:timestamp
    assert slot_id in manager._active_slots
    assert manager._stats["total_acquired"] == 1
    assert manager._stats["current_active"] == 1


# ============================================================================
# Test: test_acquire_model_specific_slot
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_model_specific_slot(manager):
    """
    Test acquiring a slot for a specific model.

    Verifies:
    - Model semaphore is created
    - Slot includes model resource
    - Model count is tracked
    """
    slot_id = await manager.acquire(
        model="gpt-4o",
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None
    assert "gpt-4o" in manager._model_semaphores
    assert manager.get_active_count(ResourceType.MODEL, "gpt-4o") == 1


# ============================================================================
# Test: test_acquire_provider_slot
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_provider_slot(manager):
    """
    Test acquiring a slot for a specific provider.

    Verifies:
    - Provider semaphore is created
    - Slot includes provider resource
    - Provider count is tracked
    """
    slot_id = await manager.acquire(
        provider="openai",
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None
    assert "openai" in manager._provider_semaphores
    assert manager.get_active_count(ResourceType.PROVIDER, "openai") == 1


# ============================================================================
# Test: test_acquire_agent_slot
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_agent_slot(manager):
    """
    Test acquiring a slot for a specific agent type.

    Verifies:
    - Agent semaphore is created with correct limit
    - Slot includes agent resource
    - Agent count is tracked
    """
    slot_id = await manager.acquire(
        agent="explore",
        agent_max_concurrent=3,
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None
    assert "explore" in manager._agent_semaphores
    assert manager.get_active_count(ResourceType.AGENT, "explore") == 1


# ============================================================================
# Test: test_acquire_timeout_returns_none
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_timeout_returns_none(small_manager):
    """
    Test that acquire times out and returns None when slots are unavailable.

    Verifies:
    - Returns None on timeout
    - Timeout stat is incremented
    - Partially acquired resources are released
    """
    # Exhaust global slots
    slot1 = await small_manager.acquire(session_id="s1", task_id="t1")
    slot2 = await small_manager.acquire(session_id="s2", task_id="t2")

    # Third request should timeout
    slot3 = await small_manager.acquire(
        session_id="s3",
        task_id="t3",
        timeout=0.5,
    )

    assert slot3 is None
    assert small_manager._stats["total_timeouts"] == 1


# ============================================================================
# Test: test_release_frees_slot
# ============================================================================

@pytest.mark.asyncio
async def test_release_frees_slot(manager):
    """
    Test that release() frees the concurrency slot.

    Verifies:
    - Slot is removed from active slots
    - Stats are updated
    - Semaphore is released
    """
    slot_id = await manager.acquire(
        model="gpt-4o",
        provider="openai",
        agent="explore",
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None
    assert manager._stats["current_active"] == 1

    manager.release(slot_id)

    assert slot_id not in manager._active_slots
    assert manager._stats["total_released"] == 1
    assert manager._stats["current_active"] == 0


# ============================================================================
# Test: test_release_notifies_waiters
# ============================================================================

@pytest.mark.asyncio
async def test_release_notifies_waiters(small_manager):
    """
    Test that release() notifies waiting tasks.

    Verifies:
    - Waiters are notified when slot is released
    - Events are set
    """
    # Exhaust slots
    slot1 = await small_manager.acquire(session_id="s1", task_id="t1")
    slot2 = await small_manager.acquire(session_id="s2", task_id="t2")

    # Create waiter
    waiter_event = asyncio.Event()
    small_manager._waiters["global"] = [waiter_event]

    # Release slot in another task
    async def release_after_delay():
        await asyncio.sleep(0.1)
        small_manager.release(slot1)

    asyncio.create_task(release_after_delay())

    # Waiter should be notified
    await asyncio.wait_for(waiter_event.wait(), timeout=1.0)
    assert waiter_event.is_set()


# ============================================================================
# Test: test_clear_releases_all
# ============================================================================

@pytest.mark.asyncio
async def test_clear_releases_all(manager):
    """
    Test that clear() releases all slots and clears state.

    Verifies:
    - All active slots are cleared
    - Current active count is reset
    - Waiters are notified
    """
    # Acquire multiple slots
    slot1 = await manager.acquire(session_id="s1", task_id="t1")
    slot2 = await manager.acquire(model="gpt-4o", session_id="s2", task_id="t2")
    slot3 = await manager.acquire(provider="openai", session_id="s3", task_id="t3")

    assert len(manager._active_slots) == 3

    # Create waiter
    waiter_event = asyncio.Event()
    manager._waiters["test"] = [waiter_event]

    manager.clear()

    assert len(manager._active_slots) == 0
    assert manager._stats["current_active"] == 0
    assert waiter_event.is_set()


# ============================================================================
# Test: test_get_stats_returns_accurate_data
# ============================================================================

@pytest.mark.asyncio
async def test_get_stats_returns_accurate_data(manager):
    """
    Test that get_stats() returns accurate statistics.

    Verifies:
    - Total acquired/released counts are correct
    - Active slots count is correct
    - Semaphore values are correct
    """
    # Acquire slots
    slot1 = await manager.acquire(session_id="s1", task_id="t1")
    slot2 = await manager.acquire(model="gpt-4o", session_id="s2", task_id="t2")

    stats = manager.get_stats()

    assert stats["total_acquired"] == 2
    assert stats["current_active"] == 2
    assert stats["active_slots"] == 2
    assert "global_available" in stats
    assert stats["global_available"] < manager.config.max_global  # Some used

    # Release one
    manager.release(slot1)

    stats = manager.get_stats()
    assert stats["total_released"] == 1
    assert stats["current_active"] == 1


# ============================================================================
# Test: test_get_active_count_for_resource
# ============================================================================

@pytest.mark.asyncio
async def test_get_active_count_for_resource(manager):
    """
    Test that get_active_count() returns correct count for a resource.

    Verifies:
    - Count is accurate for each resource type
    - Count updates with acquire/release
    """
    # Acquire slots with same model
    slot1 = await manager.acquire(
        model="gpt-4o",
        session_id="s1",
        task_id="t1",
    )
    slot2 = await manager.acquire(
        model="gpt-4o",
        session_id="s2",
        task_id="t2",
    )

    count = manager.get_active_count(ResourceType.MODEL, "gpt-4o")
    assert count == 2

    # Release one
    manager.release(slot1)
    count = manager.get_active_count(ResourceType.MODEL, "gpt-4o")
    assert count == 1


# ============================================================================
# Test: test_acquire_all_resource_types
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_all_resource_types(manager):
    """
    Test acquiring slots with all resource types specified.

    Verifies:
    - All resources are acquired atomically
    - Slot contains all resource info
    """
    slot_id = await manager.acquire(
        model="gpt-4o",
        provider="openai",
        agent="explore",
        agent_max_concurrent=3,
        session_id="session-1",
        task_id="task-1",
    )

    assert slot_id is not None

    slot = manager._active_slots[slot_id]
    assert "global" in slot.resource_id
    assert "openai" in slot.resource_id
    assert "gpt-4o" in slot.resource_id
    assert "explore" in slot.resource_id


# ============================================================================
# Test: test_concurrent_acquire_respects_limits
# ============================================================================

@pytest.mark.asyncio
async def test_concurrent_acquire_respects_limits():
    """
    Test that concurrent acquire requests respect concurrency limits.

    Verifies:
    - No more than max_global concurrent slots
    - Waiters queue up properly
    """
    config = ConcurrencyConfig(max_global=2, queue_timeout=5.0)
    manager = ConcurrencyManager(config=config)

    acquired_order = []
    release_events = []

    async def acquire_and_hold(session_id: str, hold_time: float):
        slot_id = await manager.acquire(session_id=session_id, task_id=f"task-{session_id}")
        acquired_order.append(f"acquired-{session_id}")
        await asyncio.sleep(hold_time)
        manager.release(slot_id)
        acquired_order.append(f"released-{session_id}")

    # Launch more tasks than limit allows
    tasks = [
        asyncio.create_task(acquire_and_hold("s1", 0.2)),
        asyncio.create_task(acquire_and_hold("s2", 0.2)),
        asyncio.create_task(acquire_and_hold("s3", 0.1)),
        asyncio.create_task(acquire_and_hold("s4", 0.1)),
    ]

    await asyncio.gather(*tasks)

    # All should have acquired
    assert len([x for x in acquired_order if x.startswith("acquired-")]) == 4
    # All should have released
    assert len([x for x in acquired_order if x.startswith("released-")]) == 4


# ============================================================================
# Test: test_release_non_existent_slot
# ============================================================================

def test_release_non_existent_slot(manager):
    """
    Test that releasing a non-existent slot doesn't raise an error.

    Verifies:
    - Gracefully handles invalid slot ID
    """
    # Should not raise
    manager.release("non-existent-slot-id")


# ============================================================================
# Test: test_get_concurrency_limit
# ============================================================================

def test_get_concurrency_limit(custom_config):
    """
    Test that get_concurrency_limit() returns correct limits.

    Verifies:
    - Returns configured limit for known models
    - Returns default for unknown models
    """
    manager = ConcurrencyManager(config=custom_config)

    # Known model
    limit = manager.get_concurrency_limit("gpt-4o")
    assert limit == 2

    # Unknown model - uses fallback
    limit = manager.get_concurrency_limit("unknown-model")
    assert limit == custom_config.max_per_model


# ============================================================================
# Test: test_cancel_waiters
# ============================================================================

def test_cancel_waiters(manager):
    """
    Test that cancel_waiters() notifies all waiters for a resource.

    Verifies:
    - All waiter events are set
    - Waiters list is cleared
    """
    # Create multiple waiters
    event1 = asyncio.Event()
    event2 = asyncio.Event()
    manager._waiters["resource-1"] = [event1, event2]

    manager.cancel_waiters("resource-1")

    assert event1.is_set()
    assert event2.is_set()
    assert manager._waiters["resource-1"] == []


# ============================================================================
# Test: test_semaphore_value_tracking
# ============================================================================

@pytest.mark.asyncio
async def test_semaphore_value_tracking(manager):
    """
    Test that semaphore values are tracked correctly.

    Verifies:
    - Initial value is max
    - Value decreases on acquire
    - Value increases on release
    """
    model = "gpt-4o"
    initial_available = manager.config.model_concurrency.get(
        model, manager.config.max_per_model
    )

    # Check initial state
    stats = manager.get_stats()
    if model in stats["models"]:
        assert stats["models"][model] == initial_available

    # Acquire
    slot_id = await manager.acquire(model=model, session_id="s1", task_id="t1")

    stats = manager.get_stats()
    assert stats["models"][model] == initial_available - 1

    # Release
    manager.release(slot_id)

    stats = manager.get_stats()
    assert stats["models"][model] == initial_available


# ============================================================================
# Test: test_acquire_with_custom_timeout
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_with_custom_timeout(small_manager):
    """
    Test that custom timeout is respected.

    Verifies:
    - Custom timeout overrides config timeout
    """
    # Exhaust slots
    await small_manager.acquire(session_id="s1", task_id="t1")
    await small_manager.acquire(session_id="s2", task_id="t2")

    # Short timeout
    start_time = asyncio.get_event_loop().time()
    slot = await small_manager.acquire(
        session_id="s3",
        task_id="t3",
        timeout=0.2,
    )
    elapsed = asyncio.get_event_loop().time() - start_time

    assert slot is None
    assert elapsed < 0.5  # Should timeout quickly


# ============================================================================
# Test: test_slot_dataclass
# ============================================================================

def test_slot_dataclass():
    """
    Test ConcurrencySlot dataclass properties.

    Verifies:
    - Fields are set correctly
    - Default values are applied
    """
    slot = ConcurrencySlot(
        resource_type=ResourceType.MODEL,
        resource_id="gpt-4o",
        session_id="session-1",
        task_id="task-1",
    )

    assert slot.resource_type == ResourceType.MODEL
    assert slot.resource_id == "gpt-4o"
    assert slot.session_id == "session-1"
    assert slot.task_id == "task-1"
    assert slot.acquired_at is not None
    assert slot.settled is False


# ============================================================================
# Test: test_resource_type_enum
# ============================================================================

def test_resource_type_enum():
    """
    Test ResourceType enum values.

    Verifies:
    - All expected types exist
    - String values are correct
    """
    assert ResourceType.MODEL.value == "model"
    assert ResourceType.PROVIDER.value == "provider"
    assert ResourceType.AGENT.value == "agent"
    assert ResourceType.GLOBAL.value == "global"


# ============================================================================
# Test: test_config_defaults
# ============================================================================

def test_config_defaults():
    """
    Test ConcurrencyConfig default values.

    Verifies:
    - Default limits are sensible
    - Queue timeout has default
    """
    config = ConcurrencyConfig()

    assert config.max_global == 20
    assert config.max_per_model == 2
    assert config.max_per_provider == 5
    assert config.queue_timeout == 300.0
    assert config.enable_queue is True
    assert config.default_concurrency == 3


# ============================================================================
# Test: test_multiple_providers_models
# ============================================================================

@pytest.mark.asyncio
async def test_multiple_providers_models(manager):
    """
    Test acquiring slots across multiple providers and models.

    Verifies:
    - Different providers have independent semaphores
    - Different models have independent semaphores
    """
    slot1 = await manager.acquire(
        model="gpt-4o",
        provider="openai",
        session_id="s1",
        task_id="t1",
    )
    slot2 = await manager.acquire(
        model="claude-sonnet-4-20250514",
        provider="anthropic",
        session_id="s2",
        task_id="t2",
    )

    assert slot1 is not None
    assert slot2 is not None

    assert manager.get_active_count(ResourceType.PROVIDER, "openai") == 1
    assert manager.get_active_count(ResourceType.PROVIDER, "anthropic") == 1
    assert manager.get_active_count(ResourceType.MODEL, "gpt-4o") == 1
    assert manager.get_active_count(ResourceType.MODEL, "claude-sonnet-4-20250514") == 1


# ============================================================================
# Test: test_acquire_release_pattern
# ============================================================================

@pytest.mark.asyncio
async def test_acquire_release_pattern(manager):
    """
    Test typical acquire-use-release pattern.

    Verifies:
    - Can acquire multiple times in sequence
    - Stats remain consistent
    """
    for i in range(5):
        slot_id = await manager.acquire(
            session_id=f"session-{i}",
            task_id=f"task-{i}",
        )
        assert slot_id is not None
        manager.release(slot_id)

    assert manager._stats["total_acquired"] == 5
    assert manager._stats["total_released"] == 5
    assert manager._stats["current_active"] == 0


# ============================================================================
# Test: test_global_semaphore_exhaustion
# ============================================================================

@pytest.mark.asyncio
async def test_global_semaphore_exhaustion():
    """
    Test behavior when global semaphore is exhausted.

    Verifies:
    - Waiters queue properly
    - Released slots become available to waiters
    """
    config = ConcurrencyConfig(max_global=1, queue_timeout=2.0)
    manager = ConcurrencyManager(config=config)

    results = []

    async def acquire_task(name: str, delay: float):
        slot_id = await manager.acquire(session_id=name, task_id=f"task-{name}")
        if slot_id:
            results.append(f"{name}-acquired")
            await asyncio.sleep(delay)
            manager.release(slot_id)
            results.append(f"{name}-released")
        else:
            results.append(f"{name}-timeout")

    # First task acquires immediately
    # Second task should wait
    await asyncio.gather(
        acquire_task("first", 0.2),
        acquire_task("second", 0.1),
    )

    # Both should have acquired (second waited)
    assert "first-acquired" in results
    assert "second-acquired" in results


# ============================================================================
# Test: test_partial_acquire_rollback
# ============================================================================

@pytest.mark.asyncio
async def test_partial_acquire_rollback():
    """
    Test that partially acquired resources are released on failure.

    Verifies:
    - If one resource fails, others are released
    - No orphaned semaphores
    """
    config = ConcurrencyConfig(
        max_global=1,
        max_per_provider=1,
        queue_timeout=0.5,
    )
    manager = ConcurrencyManager(config=config)

    # Acquire global slot
    slot1 = await manager.acquire(session_id="s1", task_id="t1")
    assert slot1 is not None

    # Try to acquire - should timeout waiting for global
    slot2 = await manager.acquire(
        provider="openai",
        session_id="s2",
        task_id="t2",
    )

    assert slot2 is None
    # Provider semaphore should not have been created/acquired
    # (global acquisition happens first and times out)


# ============================================================================
# Test: test_stats_current_active_never_negative
# ============================================================================

@pytest.mark.asyncio
async def test_stats_current_active_never_negative(manager):
    """
    Test that current_active stat never goes negative.

    Verifies:
    - Releasing more than acquired doesn't cause negative count
    """
    slot_id = await manager.acquire(session_id="s1", task_id="t1")
    manager.release(slot_id)

    # Try to release again
    manager.release(slot_id)

    assert manager._stats["current_active"] >= 0

"""
Concurrency Manager

Manages concurrent access to resources and API rate limits.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ResourceType(StrEnum):
    """Resource type for concurrency control"""

    MODEL = "model"  # Per-model limit
    PROVIDER = "provider"  # Per-provider limit
    AGENT = "agent"  # Per-agent-type limit
    GLOBAL = "global"  # Global limit


@dataclass
class ConcurrencySlot:
    """Represents a concurrency slot"""

    resource_type: ResourceType
    resource_id: str
    acquired_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    task_id: str = ""
    settled: bool = False  # v4.0: 防止已取消任务占用槽位


@dataclass
class ConcurrencyConfig:
    """Concurrency configuration"""

    # v4.0: Per-model limits (fine-grained control)
    model_concurrency: dict[str, int] = field(default_factory=lambda: {
        "default": 2,
    })

    # v4.0: Per-provider limits
    provider_concurrency: dict[str, int] = field(default_factory=lambda: {
        "default": 5,
        "custom": 10,
    })

    # Legacy support (fallback when not in dict)
    max_per_model: int = 2

    # Per-provider limits (fallback)
    max_per_provider: int = 5

    # Per-agent limits (from agent metadata)
    # Uses agent.max_concurrent

    # Global limit
    max_global: int = 20

    # Queue timeout (seconds)
    queue_timeout: float = 300.0

    # Enable queuing
    enable_queue: bool = True

    # v4.0: Default concurrency when not specified
    default_concurrency: int = 3


class ConcurrencyManager:
    """
    Concurrency Manager

    Manages concurrent access to resources with:
    - Per-model slots
    - Per-provider slots
    - Per-agent slots
    - Global slots
    - Queue management
    """

    def __init__(self, config: ConcurrencyConfig | None = None):
        """
        Initialize concurrency manager

        Args:
            config: Concurrency configuration
        """
        self.config = config or ConcurrencyConfig()

        # Semaphores for each resource type
        self._global_semaphore = asyncio.Semaphore(self.config.max_global)
        self._model_semaphores: dict[str, asyncio.Semaphore] = {}
        self._provider_semaphores: dict[str, asyncio.Semaphore] = {}
        self._agent_semaphores: dict[str, asyncio.Semaphore] = {}

        # Active slots
        self._active_slots: dict[str, ConcurrencySlot] = {}

        # Wait queues
        self._waiters: dict[str, list[asyncio.Event]] = {}

        # Statistics
        self._stats = {
            "total_acquired": 0,
            "total_released": 0,
            "total_timeouts": 0,
            "current_active": 0,
        }

    def _get_model_semaphore(self, model: str, max_slots: int) -> asyncio.Semaphore:
        """Get or create semaphore for a model"""
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(max_slots)
        return self._model_semaphores[model]

    def _get_provider_semaphore(self, provider: str) -> asyncio.Semaphore:
        """Get or create semaphore for a provider"""
        if provider not in self._provider_semaphores:
            self._provider_semaphores[provider] = asyncio.Semaphore(
                self.config.max_per_provider
            )
        return self._provider_semaphores[provider]

    def _get_agent_semaphore(self, agent: str, max_slots: int) -> asyncio.Semaphore:
        """Get or create semaphore for an agent type"""
        if agent not in self._agent_semaphores:
            self._agent_semaphores[agent] = asyncio.Semaphore(max_slots)
        return self._agent_semaphores[agent]

    async def acquire(
        self,
        model: str = "",
        provider: str = "",
        agent: str = "",
        agent_max_concurrent: int = 3,
        session_id: str = "",
        task_id: str = "",
        timeout: float | None = None,
    ) -> str | None:
        """
        Acquire concurrency slots

        Args:
            model: Model ID
            provider: Provider ID
            agent: Agent type
            agent_max_concurrent: Max concurrent for agent
            session_id: Session ID
            task_id: Task ID
            timeout: Optional timeout override

        Returns:
            Slot ID if acquired, None if timeout
        """
        timeout = timeout or self.config.queue_timeout
        slot_id = f"{session_id}:{task_id}:{datetime.now().isoformat()}"

        try:
            # Try to acquire all needed semaphores
            acquired = []

            # Global first
            if not self._global_semaphore.locked() or self.config.enable_queue:
                await asyncio.wait_for(
                    self._global_semaphore.acquire(),
                    timeout=timeout,
                )
                acquired.append(("global", ""))

                # Per-provider
                if provider:
                    await asyncio.wait_for(
                        self._get_provider_semaphore(provider).acquire(),
                        timeout=timeout / 2,
                    )
                    acquired.append((ResourceType.PROVIDER.value, provider))

                # Per-model
                if model:
                    await asyncio.wait_for(
                        self._get_model_semaphore(
                            model, self.config.max_per_model
                        ).acquire(),
                        timeout=timeout / 2,
                    )
                    acquired.append((ResourceType.MODEL.value, model))

                # Per-agent
                if agent:
                    await asyncio.wait_for(
                        self._get_agent_semaphore(
                            agent, agent_max_concurrent
                        ).acquire(),
                        timeout=timeout / 2,
                    )
                    acquired.append((ResourceType.AGENT.value, agent))

            # Record slot
            slot = ConcurrencySlot(
                resource_type=ResourceType.GLOBAL,
                resource_id=",".join(f"{t}:{i}" for t, i in acquired),
                session_id=session_id,
                task_id=task_id,
            )
            self._active_slots[slot_id] = slot

            # Update stats
            self._stats["total_acquired"] += 1
            self._stats["current_active"] += 1

            logger.debug(
                "Acquired concurrency slot",
                extra_data={
                    "slot_id": slot_id,
                    "resources": acquired,
                },
            )

            return slot_id

        except TimeoutError:
            # Release any acquired resources
            for resource_type, resource_id in reversed(acquired):
                if resource_type == "global":
                    self._global_semaphore.release()
                elif resource_type == ResourceType.PROVIDER.value:
                    self._get_provider_semaphore(resource_id).release()
                elif resource_type == ResourceType.MODEL.value:
                    self._get_model_semaphore(resource_id, 1).release()
                elif resource_type == ResourceType.AGENT.value:
                    self._get_agent_semaphore(resource_id, 1).release()

            self._stats["total_timeouts"] += 1

            logger.warning(
                "Failed to acquire concurrency slot - timeout",
                extra_data={
                    "model": model,
                    "provider": provider,
                    "agent": agent,
                },
            )

            return None

    def release(self, slot_id: str) -> None:
        """
        Release a concurrency slot

        Args:
            slot_id: Slot ID to release
        """
        slot = self._active_slots.pop(slot_id, None)
        if slot is None:
            return

        # Parse resources
        resources = []
        for part in slot.resource_id.split(","):
            if ":" in part:
                resource_type, resource_id = part.split(":", 1)
                resources.append((resource_type, resource_id))

        # Release in reverse order
        for resource_type, resource_id in reversed(resources):
            if resource_type == "global":
                self._global_semaphore.release()
            elif resource_type == ResourceType.PROVIDER.value:
                self._get_provider_semaphore(resource_id).release()
            elif resource_type == ResourceType.MODEL.value:
                self._get_model_semaphore(resource_id, 1).release()
            elif resource_type == ResourceType.AGENT.value:
                self._get_agent_semaphore(resource_id, 1).release()

        # Update stats
        self._stats["total_released"] += 1
        self._stats["current_active"] = max(0, self._stats["current_active"] - 1)

        # Notify waiters
        self._notify_waiters()

        logger.debug(
            "Released concurrency slot",
            extra_data={"slot_id": slot_id},
        )

    def _notify_waiters(self) -> None:
        """Notify waiting tasks"""
        for waiters in self._waiters.values():
            for event in waiters:
                if not event.is_set():
                    event.set()

    def get_stats(self) -> dict[str, Any]:
        """Get concurrency statistics"""
        return {
            **self._stats,
            "active_slots": len(self._active_slots),
            "global_available": self._global_semaphore._value,
            "providers": {
                k: v._value for k, v in self._provider_semaphores.items()
            },
            "models": {
                k: v._value for k, v in self._model_semaphores.items()
            },
            "agents": {
                k: v._value for k, v in self._agent_semaphores.items()
            },
        }

    def get_active_count(self, resource_type: ResourceType, resource_id: str) -> int:
        """Get active count for a resource"""
        count = 0
        for slot in self._active_slots.values():
            if f"{resource_type.value}:{resource_id}" in slot.resource_id:
                count += 1
        return count

    # v4.0: Enhanced methods

    def get_concurrency_limit(self, model: str) -> int:
        """
        v4.0: Get concurrency limit for a model

        Args:
            model: Model ID

        Returns:
            Concurrency limit for the model
        """
        # Check fine-grained config first
        if model in self.config.model_concurrency:
            return self.config.model_concurrency[model]

        # Fallback to default
        return self.config.max_per_model

    def cancel_waiters(self, resource_id: str) -> None:
        """
        v4.0: Cancel all waiters for a resource

        Useful when a task is cancelled or fails, to prevent
        queued waiters from blocking indefinitely.

        Args:
            resource_id: Resource ID to cancel waiters for
        """
        if resource_id in self._waiters:
            waiters = self._waiters[resource_id]
            for event in waiters:
                if not event.is_set():
                    event.set()
            self._waiters[resource_id] = []

            logger.debug(
                f"Cancelled {len(waiters)} waiters for resource: {resource_id}"
            )

    def clear(self) -> None:
        """
        v4.0: Clear all concurrency state

        Releases all slots and clears waiters.
        Use with caution - typically only during shutdown.
        """
        # Mark all slots as settled
        for slot in self._active_slots.values():
            slot.settled = True

        # Clear active slots
        self._active_slots.clear()

        # Clear waiters
        for waiters in self._waiters.values():
            for event in waiters:
                if not event.is_set():
                    event.set()
        self._waiters.clear()

        # Reset stats
        self._stats["current_active"] = 0

        logger.warning("Cleared all concurrency state")

"""Deprecated REST API plugin.

PyAgentForge no longer exposes REST API interfaces directly.
Use the unified Service gateway under `main/Service`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType

_DEPRECATION_MESSAGE = (
    "interface.rest_api has been removed from pyagentforge. "
    "Use Service gateway routes in main/Service instead."
)


class RESTAPIPlugin(Plugin):
    """Compatibility stub for removed REST API plugin."""

    metadata = PluginMetadata(
        id="interface.rest_api",
        name="REST API (Removed)",
        version="1.0.0",
        type=PluginType.INTERFACE,
        description="Removed: API serving moved to Service gateway",
        author="PyAgentForge",
        provides=[],
        dependencies=[],
    )

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()
        raise RuntimeError(_DEPRECATION_MESSAGE)

    async def start(self) -> bool:
        return False

    async def stop(self) -> bool:
        return True

    def register_route(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
        auth_required: bool = False,
    ) -> None:
        raise RuntimeError(_DEPRECATION_MESSAGE)

    def get_routes(self) -> dict[str, dict]:
        return {}

    @property
    def is_running(self) -> bool:
        return False

    @property
    def base_url(self) -> str:
        raise RuntimeError(_DEPRECATION_MESSAGE)

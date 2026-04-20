"""
Persistence Plugin

Provides session persistence functionality
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class PersistencePlugin(Plugin):
    """Session persistence plugin"""

    metadata = PluginMetadata(
        id="integration.persistence",
        name="Session Persistence",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Provides session persistence functionality to save and restore agent state",
        author="PyAgentForge",
        provides=["persistence"],
        dependencies=["integration.events"],
    )

    def __init__(self):
        super().__init__()
        self._storage_path: Path | None = None
        self._sessions: dict[str, Any] = {}

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Get storage path from config
        config = self.context.config or {}
        storage_dir = config.get("storage_path", "./data/sessions")
        self._storage_path = Path(storage_dir)
        self._storage_path.mkdir(parents=True, exist_ok=True)

        self.context.logger.info(
            "Persistence plugin initialized",
            extra_data={"storage_path": str(self._storage_path)},
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        # Save all active sessions
        for session_id in list(self._sessions.keys()):
            await self.save_session(session_id)
        await super().on_plugin_deactivate()

    async def save_session(self, session_id: str, data: dict | None = None) -> str:
        """
        Save session data to disk

        Args:
            session_id: Session identifier
            data: Optional data to save (uses current session data if not provided)

        Returns:
            Path to saved session file
        """
        if data is None:
            data = self._sessions.get(session_id, {})

        # Add metadata
        data["_metadata"] = {
            "session_id": session_id,
            "saved_at": datetime.now(UTC).isoformat(),
            "version": "1.0",
        }

        # Save to file
        session_file = self._storage_path / f"{session_id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.context.logger.info(
            "Session saved",
            extra_data={"session_id": session_id, "file": str(session_file)},
        )

        return str(session_file)

    async def load_session(self, session_id: str) -> dict | None:
        """
        Load session data from disk

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        session_file = self._storage_path / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)

            self._sessions[session_id] = data

            self.context.logger.info(
                "Session loaded",
                extra_data={"session_id": session_id},
            )

            return data

        except Exception as e:
            self.context.logger.error(
                "Failed to load session",
                extra_data={"session_id": session_id, "error": str(e)},
            )
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session data

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        session_file = self._storage_path / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            self._sessions.pop(session_id, None)

            self.context.logger.info(
                "Session deleted",
                extra_data={"session_id": session_id},
            )
            return True

        return False

    def list_sessions(self) -> list[str]:
        """
        List all saved sessions

        Returns:
            List of session IDs
        """
        if not self._storage_path:
            return []

        return [f.stem for f in self._storage_path.glob("*.json")]

    def get_session_data(self, session_id: str) -> dict | None:
        """Get current session data (in-memory)"""
        return self._sessions.get(session_id)

    def set_session_data(self, session_id: str, data: dict) -> None:
        """Set session data (in-memory)"""
        self._sessions[session_id] = data

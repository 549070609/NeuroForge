"""
Session Recovery Plugin

Auto-recovery from session crashes with automatic state saving.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.plugins.integration.persistence.persistence import (
    SessionManager,
    SessionMetadata,
    SessionPersistence,
)
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.kernel.context import ContextManager
    from pyagentforge.kernel.engine import AgentEngine

logger = get_logger(__name__)


@dataclass
class SessionRecoveryConfig:
    """Session recovery configuration"""

    enabled: bool = True
    auto_save: bool = True
    auto_save_interval: int = 5  # Save every N LLM calls
    max_sessions: int = 100  # Maximum sessions to keep
    sessions_dir: Path = field(default_factory=lambda: Path(".sessions"))
    ask_before_recovery: bool = True


class SessionRecoveryPlugin(Plugin):
    """
    Session Recovery Plugin

    Features:
    - Auto-recovery from session crashes
    - Automatic state saving after LLM calls
    - Session state tracking (completed/interrupted)
    - Process cleanup integration for graceful shutdown

    Hooks:
    - ON_ENGINE_START: Check for recoverable sessions
    - ON_AFTER_LLM_CALL: Auto-save state
    - ON_TASK_COMPLETE: Mark session as completed
    """

    metadata = PluginMetadata(
        id="integration.session_recovery",
        name="Session Recovery",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Auto-recovery from session crashes with automatic state saving",
        author="PyAgentForge",
        provides=["session_recovery", "auto_save"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._config: SessionRecoveryConfig = SessionRecoveryConfig()
        self._session_manager: SessionManager | None = None
        self._current_session: SessionPersistence | None = None
        self._call_count: int = 0
        self._engine: AgentEngine | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._config = SessionRecoveryConfig(
            enabled=config.get("enabled", True),
            auto_save=config.get("auto_save", True),
            auto_save_interval=config.get("auto_save_interval", 5),
            max_sessions=config.get("max_sessions", 100),
            sessions_dir=Path(config.get("sessions_dir", ".sessions")),
            ask_before_recovery=config.get("ask_before_recovery", True),
        )

        # Create session manager
        self._session_manager = SessionManager(self._config.sessions_dir)

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_ENGINE_START,
            self,
            self._on_engine_start,
            priority=800,  # High priority for early recovery
        )
        self.context.hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            self,
            self._on_after_llm_call,
            priority=200,  # Lower priority, let other hooks process first
        )
        self.context.hook_registry.register(
            HookType.ON_TASK_COMPLETE,
            self,
            self._on_task_complete,
            priority=500,
        )

        # Register process cleanup
        self._register_cleanup()

        self.context.logger.info(
            "Session recovery plugin activated",
            extra_data={
                "enabled": self._config.enabled,
                "auto_save": self._config.auto_save,
                "sessions_dir": str(self._config.sessions_dir),
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        # Save final state
        await self._save_current_state()

        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    def _register_cleanup(self) -> None:
        """Register cleanup handler for graceful shutdown"""
        try:
            from pyagentforge.kernel.cleanup import register_cleanup_async

            register_cleanup_async(
                self._cleanup_handler,
                name="session_recovery_save",
            )
        except ImportError:
            self.context.logger.warning(
                "ProcessCleanup not available, graceful shutdown may not save state"
            )

    async def _cleanup_handler(self) -> None:
        """Cleanup handler for graceful shutdown"""
        if self._current_session:
            await self._save_current_state()
            self.context.logger.info(
                "Session state saved on shutdown",
                extra_data={"session_id": self._current_session.session_id},
            )

    async def _on_engine_start(
        self,
        engine: "AgentEngine",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Check for recoverable sessions on engine start

        Args:
            engine: Agent engine instance

        Returns:
            Recovery info if session was recovered
        """
        if not self._config.enabled:
            return None

        self._engine = engine

        # Check for interrupted sessions
        last_session = self._find_last_interrupted_session()

        if last_session is None:
            # Start new session
            self._current_session = self._session_manager.create_session(
                model=getattr(engine, "model", ""),
                workspace=str(Path.cwd()),
                title="New Session",
            )
            return None

        # Found interrupted session
        if self._config.ask_before_recovery:
            # For now, auto-recover. In interactive mode, would ask user.
            self.context.logger.info(
                "Found interrupted session, attempting recovery",
                extra_data={"session_id": last_session.id},
            )

        # Load session
        self._current_session = self._session_manager.load_session(last_session.id)

        if self._current_session is None:
            return None

        # Restore messages
        messages = self._current_session.get_messages_list()
        if messages:
            restored = self._restore_messages(engine, messages)

            self.context.logger.info(
                "Session recovered",
                extra_data={
                    "session_id": self._current_session.session_id,
                    "messages_restored": restored,
                },
            )

            return {
                "recovered": True,
                "session_id": self._current_session.session_id,
                "messages_restored": restored,
            }

        return None

    def _find_last_interrupted_session(self) -> SessionMetadata | None:
        """Find the last interrupted session that can be recovered"""
        if self._session_manager is None:
            return None

        sessions = self._session_manager.get_recent_sessions(limit=10)

        for session_info in sessions:
            session = self._session_manager.load_session(session_info["id"])
            if session is None:
                continue

            state = session.load_state()

            # Check if session was interrupted (has messages but not marked complete)
            if session_info["message_count"] > 0:
                # Check for completion marker
                if not state.variables.get("completed", False):
                    return session.load_metadata()

        return None

    def _restore_messages(
        self,
        engine: "AgentEngine",
        messages: list[dict[str, Any]],
    ) -> int:
        """
        Restore messages to engine context

        Args:
            engine: Agent engine
            messages: List of message dictionaries

        Returns:
            Number of messages restored
        """
        context = getattr(engine, "context", None)
        if context is None:
            return 0

        # Clear existing messages
        context.messages.clear()

        # Import message types
        try:
            from pyagentforge.kernel.message import Message

            for msg_dict in messages:
                try:
                    msg = Message.from_dict(msg_dict)
                    context.messages.append(msg)
                except Exception as e:
                    self.context.logger.warning(
                        f"Failed to restore message: {e}",
                        extra_data={"message_role": msg_dict.get("role")},
                    )

            return len(context.messages)

        except ImportError:
            # Fallback: restore as raw dicts
            for msg_dict in messages:
                context.messages.append(msg_dict)

            return len(context.messages)

    async def _on_after_llm_call(
        self,
        response: Any,
        context: "ContextManager",
        session_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Auto-save state after LLM call

        Args:
            response: LLM response
            context: Context manager
            session_id: Optional session identifier

        Returns:
            Save info if saved
        """
        if not self._config.enabled or not self._config.auto_save:
            return None

        self._call_count += 1

        # Check if we should save
        if self._call_count % self._config.auto_save_interval != 0:
            return None

        # Save current state
        saved = await self._save_current_state()

        if saved:
            return {
                "auto_saved": True,
                "call_count": self._call_count,
                "session_id": self._current_session.session_id if self._current_session else None,
            }

        return None

    async def _on_task_complete(
        self,
        result: str,
        session_id: str | None = None,
        **kwargs,
    ) -> None:
        """
        Hook: Mark session as completed

        Args:
            result: Task result
            session_id: Optional session identifier
        """
        if self._current_session is None:
            return

        # Update state to mark as completed
        self._current_session.update_state(completed=True)

        # Save final state
        await self._save_current_state()

        self.context.logger.info(
            "Session marked as completed",
            extra_data={"session_id": self._current_session.session_id},
        )

    async def _save_current_state(self) -> bool:
        """
        Save current session state

        Returns:
            True if saved successfully
        """
        if self._current_session is None or self._engine is None:
            return False

        try:
            context = getattr(self._engine, "context", None)
            if context is None:
                return False

            # Clear existing messages and rewrite
            # (Could optimize by only appending new messages)
            self._current_session.messages_file.write_text("", encoding="utf-8")

            for msg in context.messages:
                # Convert message to dict
                if hasattr(msg, "to_api_format"):
                    msg_dict = msg.to_api_format()
                elif hasattr(msg, "__dict__"):
                    msg_dict = msg.__dict__
                else:
                    msg_dict = {"role": getattr(msg, "role", "unknown"), "content": str(msg)}

                self._current_session.append_message(msg_dict)

            # Update metadata
            self._current_session.update_metadata(
                message_count=len(context.messages),
                updated_at=datetime.utcnow().isoformat() + "Z",
            )

            return True

        except Exception as e:
            self.context.logger.error(
                f"Failed to save session state: {e}",
                extra_data={"error": str(e)},
            )
            return False

    def get_current_session_id(self) -> str | None:
        """Get the current session ID"""
        if self._current_session:
            return self._current_session.session_id
        return None

    def force_save(self) -> bool:
        """Force save current state"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self._save_current_state())
        except RuntimeError:
            return asyncio.run(self._save_current_state())

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions"""
        if self._session_manager is None:
            return []
        return self._session_manager.list_sessions()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if self._session_manager is None:
            return False

        persistence = self._session_manager.load_session(session_id)
        if persistence:
            return persistence.delete_session()
        return False

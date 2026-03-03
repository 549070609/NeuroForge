"""Legacy runtime service.

This service migrates standalone pyagentforge API capabilities into the
Service gateway, so the gateway can host legacy-compatible runtime endpoints.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from pyagentforge import (
    AgentEngine,
    ToolRegistry,
    ContextManager,
    register_core_tools,
    AnthropicProvider,
    get_engine_settings,
)

from ..config import get_settings
from ..core.registry import ServiceRegistry
from .base import BaseService

logger = logging.getLogger(__name__)


class LegacyRuntimeService(BaseService):
    """Service implementation for migrated legacy runtime endpoints."""

    def __init__(self, registry: ServiceRegistry):
        super().__init__(registry)
        self._agents: dict[str, dict[str, Any]] = {}
        self._engines: dict[str, Any] = {}
        self._persistences: dict[str, Any] = {}
        self._session_messages: dict[str, list[dict[str, Any]]] = {}
        self._session_status: dict[str, str] = {}
        self._session_manager: Any | None = None

    async def _on_initialize(self) -> None:
        self._session_manager = self._create_session_manager()
        self._logger.info("LegacyRuntimeService initialized")

    async def _on_shutdown(self) -> None:
        self._agents.clear()
        self._engines.clear()
        self._persistences.clear()
        self._session_messages.clear()
        self._session_status.clear()
        self._logger.info("LegacyRuntimeService shut down")

    def _create_session_manager(self) -> Any | None:
        try:
            from pyagentforge.core.persistence import SessionManager
        except ImportError as exc:
            self._logger.warning("pyagentforge session persistence unavailable: %s", exc)
            return None

        sessions_dir = Path(get_settings().legacy_sessions_dir)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return SessionManager(sessions_dir=sessions_dir)

    def _get_default_model(self) -> str:
        try:
            return get_engine_settings().default_model
        except Exception:
            return get_settings().default_model

    def _create_runtime_engine(
        self,
        model: str | None = None,
        system_prompt: str | None = None,
        seeded_messages: list[dict[str, Any]] | None = None,
    ) -> Any:
        selected_model = model or self._get_default_model()
        messages = seeded_messages or []

        try:
            pa_settings = get_engine_settings()
            provider = AnthropicProvider(
                api_key=pa_settings.anthropic_api_key,
                model=selected_model,
            )
            tools = ToolRegistry()
            register_core_tools(tools)

            context = ContextManager(
                system_prompt=system_prompt or "You are a helpful AI assistant."
            )
            for message in messages:
                if isinstance(message, dict):
                    context.messages.append(message)

            return AgentEngine(
                provider=provider,
                tool_registry=tools,
                context=context,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to create pyagentforge runtime engine: {exc}") from exc

    def _resolve_agent_profile(
        self,
        agent_id: str | None,
        override_system_prompt: str | None,
    ) -> tuple[str, str | None]:
        model = self._get_default_model()
        system_prompt = override_system_prompt

        if agent_id and agent_id in self._agents:
            agent = self._agents[agent_id]
            model = agent.get("model", model)
            if system_prompt is None:
                system_prompt = agent.get("system_prompt")

        return model, system_prompt

    async def _ensure_session_loaded(self, session_id: str) -> None:
        if session_id in self._engines:
            return

        if self._session_manager is None:
            raise KeyError(session_id)

        persistence = self._session_manager.load_session(session_id)
        if persistence is None:
            raise KeyError(session_id)

        messages = list(persistence.read_messages())
        metadata = persistence.load_metadata()
        model = metadata.model if metadata else self._get_default_model()

        engine = self._create_runtime_engine(model=model, seeded_messages=messages)
        setattr(engine, "_session_id", session_id)

        self._engines[session_id] = engine
        self._persistences[session_id] = persistence
        self._session_messages[session_id] = messages
        self._session_status[session_id] = "active"

    async def create_session(
        self,
        agent_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, str]:
        model, resolved_system_prompt = self._resolve_agent_profile(agent_id, system_prompt)
        engine = self._create_runtime_engine(model=model, system_prompt=resolved_system_prompt)

        session_id = getattr(engine, "session_id", f"session_{uuid.uuid4().hex[:12]}")
        persistence = None

        if self._session_manager is not None:
            try:
                persistence = self._session_manager.create_session(
                    model=model,
                    title=f"Session {session_id[:12]}",
                )
                session_id = persistence.session_id
            except Exception as exc:
                self._logger.warning("Failed to create persisted session, using memory only: %s", exc)

        setattr(engine, "_session_id", session_id)

        self._engines[session_id] = engine
        self._session_messages[session_id] = []
        self._session_status[session_id] = "active"

        if persistence is not None:
            self._persistences[session_id] = persistence

        return {
            "session_id": session_id,
            "status": "created",
        }

    async def get_session_detail(self, session_id: str) -> dict[str, Any]:
        await self._ensure_session_loaded(session_id)

        messages = self._session_messages.get(session_id, [])
        return {
            "session_id": session_id,
            "status": self._session_status.get(session_id, "active"),
            "message_count": len(messages),
            "messages": messages,
        }

    async def send_message(self, session_id: str, message: str) -> dict[str, str]:
        await self._ensure_session_loaded(session_id)

        engine = self._engines[session_id]
        persistence = self._persistences.get(session_id)

        user_message = {"role": "user", "content": message}
        self._session_messages[session_id].append(user_message)
        if persistence is not None:
            persistence.append_message(user_message)

        response = await engine.run(message)

        assistant_message = {"role": "assistant", "content": response}
        self._session_messages[session_id].append(assistant_message)
        if persistence is not None:
            persistence.append_message(assistant_message)

        return {
            "role": "assistant",
            "content": response,
        }

    async def stream_message(
        self,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        await self._ensure_session_loaded(session_id)

        engine = self._engines[session_id]
        persistence = self._persistences.get(session_id)

        user_message = {"role": "user", "content": message}
        self._session_messages[session_id].append(user_message)
        if persistence is not None:
            persistence.append_message(user_message)

        final_text = ""
        async for event in engine.run_stream(message):
            if not isinstance(event, dict):
                continue

            event_type = event.get("type")
            if event_type == "complete":
                final_text = str(event.get("text", ""))
            elif event_type == "error":
                final_text = f"Error: {event.get('message', 'Unknown error')}"

            yield event

        if final_text:
            assistant_message = {"role": "assistant", "content": final_text}
            self._session_messages[session_id].append(assistant_message)
            if persistence is not None:
                persistence.append_message(assistant_message)

    async def delete_session(self, session_id: str) -> None:
        self._engines.pop(session_id, None)
        self._session_messages.pop(session_id, None)
        self._session_status.pop(session_id, None)

        persistence = self._persistences.pop(session_id, None)
        if persistence is not None:
            try:
                persistence.delete_session()
            except Exception as exc:
                self._logger.warning("Failed to delete persisted session %s: %s", session_id, exc)
            return

        if self._session_manager is not None:
            loaded = self._session_manager.load_session(session_id)
            if loaded is not None:
                loaded.delete_session()

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        seen: set[str] = set()

        if self._session_manager is not None:
            try:
                sessions = self._session_manager.list_sessions()
                for session in sessions:
                    session_id = session.get("id")
                    if isinstance(session_id, str):
                        seen.add(session_id)
            except Exception as exc:
                self._logger.warning("Failed to list persisted sessions: %s", exc)

        for session_id, messages in self._session_messages.items():
            if session_id in seen:
                continue

            sessions.append(
                {
                    "id": session_id,
                    "title": f"Session {session_id[:12]}",
                    "model": self._get_default_model(),
                    "created_at": "",
                    "updated_at": "",
                    "message_count": len(messages),
                }
            )

        return sessions

    def create_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(uuid.uuid4())
        agent_data = {
            "id": agent_id,
            "name": payload["name"],
            "description": payload.get("description"),
            "system_prompt": payload.get("system_prompt", "You are a helpful AI assistant."),
            "allowed_tools": payload.get("allowed_tools", ["*"]),
            "model": payload.get("model", self._get_default_model()),
            "is_active": True,
        }

        self._agents[agent_id] = agent_data
        return self._agent_response(agent_data)

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(agent_id)
        return self._agent_response(agent)

    def update_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(agent_id)

        for field in ("description", "system_prompt", "allowed_tools", "is_active"):
            if field in payload and payload[field] is not None:
                agent[field] = payload[field]

        return self._agent_response(agent)

    def delete_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def list_agents(self) -> list[dict[str, Any]]:
        return [self._agent_response(agent) for agent in self._agents.values()]

    def _agent_response(self, agent: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": agent["id"],
            "name": agent["name"],
            "description": agent.get("description"),
            "model": agent["model"],
            "is_active": bool(agent.get("is_active", True)),
        }

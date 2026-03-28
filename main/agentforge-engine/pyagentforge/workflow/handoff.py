"""
Agent Handoff 协议

定义 Agent 间上下文传递的标准协议，
灵感来自 OpenAI Agents SDK 的 handoff 模式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyagentforge.kernel.context import ContextManager
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HandoffPayload:
    """Agent 间移交的上下文载荷"""

    source_agent: str
    target_agent: str
    instruction: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    shared_state: dict[str, Any] = field(default_factory=dict)
    max_history: int = 10

    @classmethod
    def from_context(
        cls,
        source_agent: str,
        target_agent: str,
        instruction: str,
        context: ContextManager,
        shared_state: dict[str, Any] | None = None,
        max_history: int = 10,
    ) -> HandoffPayload:
        """从 ContextManager 构建移交载荷"""
        recent_messages = context.get_messages_for_api()[-max_history:]
        return cls(
            source_agent=source_agent,
            target_agent=target_agent,
            instruction=instruction,
            messages=recent_messages,
            shared_state=shared_state or {},
            max_history=max_history,
        )

    def apply_to_context(self, context: ContextManager) -> None:
        """将移交载荷中的历史消息注入目标 context"""
        handoff_summary = (
            f"[Handoff from '{self.source_agent}']\n"
            f"Instruction: {self.instruction}\n"
        )

        if self.shared_state:
            state_str = "\n".join(
                f"- {k}: {str(v)[:200]}" for k, v in self.shared_state.items()
            )
            handoff_summary += f"Shared context:\n{state_str}\n"

        if self.messages:
            handoff_summary += f"(Includes {len(self.messages)} messages of prior conversation)"

        context.add_user_message(handoff_summary)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "instruction": self.instruction,
            "messages": self.messages,
            "shared_state": self.shared_state,
            "max_history": self.max_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandoffPayload:
        return cls(**data)


class HandoffManager:
    """管理 Agent 间的 handoff 流程"""

    def __init__(self) -> None:
        self._pending: dict[str, HandoffPayload] = {}
        self._history: list[dict[str, Any]] = []

    def initiate(
        self,
        source_agent: str,
        target_agent: str,
        instruction: str,
        context: ContextManager,
        shared_state: dict[str, Any] | None = None,
    ) -> HandoffPayload:
        """发起一次 handoff"""
        payload = HandoffPayload.from_context(
            source_agent=source_agent,
            target_agent=target_agent,
            instruction=instruction,
            context=context,
            shared_state=shared_state,
        )
        self._pending[target_agent] = payload
        self._history.append({
            "source": source_agent,
            "target": target_agent,
            "instruction": instruction,
        })
        logger.info(
            f"Handoff initiated: {source_agent} → {target_agent}",
            extra_data={"instruction": instruction[:100]},
        )
        return payload

    def accept(self, agent_name: str, context: ContextManager) -> bool:
        """目标 agent 接受 handoff 并注入 context"""
        payload = self._pending.pop(agent_name, None)
        if payload is None:
            return False
        payload.apply_to_context(context)
        logger.info(f"Handoff accepted by '{agent_name}'")
        return True

    def has_pending(self, agent_name: str) -> bool:
        return agent_name in self._pending

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)

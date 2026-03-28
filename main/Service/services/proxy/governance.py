"""Governance building blocks for guardrails, HITL, handoff protocol, and SLO."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from ...persistence import StateStore


def utc_ts() -> int:
    return int(time.time())


def utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class GuardrailDecision:
    rule_id: str
    action: Literal["allow", "review", "block"]
    message: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action": self.action,
            "message": self.message,
            "severity": self.severity,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class GuardrailResult:
    decisions: list[GuardrailDecision] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(decision.action == "block" for decision in self.decisions)

    @property
    def requires_approval(self) -> bool:
        return any(decision.action == "review" for decision in self.decisions) and not self.blocked

    @property
    def allow(self) -> bool:
        return not self.blocked and not self.requires_approval

    def top_decision(self) -> GuardrailDecision | None:
        if not self.decisions:
            return None
        priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return max(self.decisions, key=lambda d: (priority[d.severity], d.action))

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "requires_approval": self.requires_approval,
            "allow": self.allow,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


class GuardrailEngine:
    """Rule-based guardrail engine for input/output/runtime checks."""

    def __init__(self) -> None:
        self._blocked_rules: list[tuple[str, re.Pattern[str], str]] = [
            (
                "prompt_injection_disable_safety",
                re.compile(r"\b(ignore|bypass|disable)\b.{0,24}\b(safety|policy|guardrail)\b", re.I),
                "Potential prompt-injection instruction to disable safety checks.",
            ),
            (
                "secret_exfiltration",
                re.compile(r"\b(exfiltrate|steal|dump|leak)\b.{0,32}\b(password|secret|token|api[\s_-]?key)\b", re.I),
                "Potential secret exfiltration request detected.",
            ),
            (
                "malware_intent",
                re.compile(r"\b(ransomware|keylogger|botnet|credential\s*stuffing)\b", re.I),
                "Potential malicious intent detected.",
            ),
        ]
        self._review_rules: list[tuple[str, re.Pattern[str], str]] = [
            (
                "destructive_filesystem",
                re.compile(r"\b(rm\s+-rf|delete\s+all|format\s+disk|drop\s+database|truncate)\b", re.I),
                "Potential destructive operation requested.",
            ),
            (
                "production_change",
                re.compile(r"\b(production|prod)\b.{0,24}\b(deploy|restart|shutdown|migrate)\b", re.I),
                "Potential production-impacting operation requested.",
            ),
            (
                "privilege_escalation",
                re.compile(r"\b(sudo|admin|root|elevat(e|ion))\b", re.I),
                "Potential privileged operation requested.",
            ),
        ]
        self._output_block_rules: list[tuple[str, re.Pattern[str], str]] = [
            (
                "token_leak",
                re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})\b"),
                "Potential credential/token leak in output.",
            ),
            (
                "private_key_leak",
                re.compile(r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----"),
                "Potential private key leak in output.",
            ),
        ]
        self._high_risk_tools = {"Bash", "Write", "Edit", "ApplyPatch", "Batch"}

    def evaluate_input(self, prompt: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        result = GuardrailResult()
        text = prompt or ""
        for rule_id, pattern, message in self._blocked_rules:
            if pattern.search(text):
                result.decisions.append(
                    GuardrailDecision(
                        rule_id=rule_id,
                        action="block",
                        message=message,
                        severity="critical",
                    )
                )
        for rule_id, pattern, message in self._review_rules:
            if pattern.search(text):
                result.decisions.append(
                    GuardrailDecision(
                        rule_id=rule_id,
                        action="review",
                        message=message,
                        severity="high",
                    )
                )

        if context:
            requested_tool = context.get("tool_name")
            if isinstance(requested_tool, str) and requested_tool in self._high_risk_tools:
                result.decisions.append(
                    GuardrailDecision(
                        rule_id="high_risk_tool_request",
                        action="review",
                        message=f"High-risk tool requested: {requested_tool}",
                        severity="high",
                        metadata={"tool_name": requested_tool},
                    )
                )
        return result

    def evaluate_output(self, output_text: str) -> GuardrailResult:
        result = GuardrailResult()
        text = output_text or ""
        for rule_id, pattern, message in self._output_block_rules:
            if pattern.search(text):
                result.decisions.append(
                    GuardrailDecision(
                        rule_id=rule_id,
                        action="block",
                        message=message,
                        severity="critical",
                    )
                )
        return result


@dataclass(slots=True)
class ApprovalRecord:
    approval_id: str
    kind: str
    reason: str
    payload_hash: str
    payload: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "expired"]
    created_at: str
    expires_at: int
    resolved_at: str | None = None
    reviewer: str | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "kind": self.kind,
            "reason": self.reason,
            "payload_hash": self.payload_hash,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "resolved_at": self.resolved_at,
            "reviewer": self.reviewer,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRecord:
        return cls(
            approval_id=str(data["approval_id"]),
            kind=str(data["kind"]),
            reason=str(data["reason"]),
            payload_hash=str(data["payload_hash"]),
            payload=dict(data.get("payload", {})),
            status=data.get("status", "pending"),
            created_at=str(data.get("created_at", utc_iso())),
            expires_at=int(data.get("expires_at", utc_ts())),
            resolved_at=data.get("resolved_at"),
            reviewer=data.get("reviewer"),
            comment=data.get("comment"),
        )


class HumanApprovalManager:
    """Human-in-the-loop approval flow with optional persistent backing store."""

    NAMESPACE = "approval"

    def __init__(
        self,
        *,
        store: StateStore | None = None,
        approval_ttl: int = 900,
        auto_approve: bool = False,
    ) -> None:
        self._store = store
        self._approval_ttl = approval_ttl
        self._auto_approve = auto_approve
        self._cache: dict[str, ApprovalRecord] = {}

    async def create(
        self,
        *,
        kind: str,
        reason: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ApprovalRecord:
        approval_id = f"apr-{uuid.uuid4().hex[:12]}"
        now = utc_ts()
        payload_hash = stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        status: Literal["pending", "approved", "rejected", "expired"] = (
            "approved" if self._auto_approve else "pending"
        )
        record = ApprovalRecord(
            approval_id=approval_id,
            kind=kind,
            reason=reason,
            payload_hash=payload_hash,
            payload=payload,
            status=status,
            created_at=utc_iso(),
            expires_at=now + self._approval_ttl,
            resolved_at=utc_iso() if status == "approved" else None,
            reviewer="system-auto" if status == "approved" else None,
            comment="auto approved by config" if status == "approved" else None,
        )
        self._cache[approval_id] = record
        if self._store:
            await self._store.set(
                approval_id,
                record.to_dict(),
                namespace=self.NAMESPACE,
                ttl=self._approval_ttl,
                idempotency_key=idempotency_key,
            )
        return record

    async def get(self, approval_id: str) -> ApprovalRecord | None:
        cached = self._cache.get(approval_id)
        if cached:
            self._expire_if_needed(cached)
            return cached
        if not self._store:
            return None
        record = await self._store.get(approval_id, namespace=self.NAMESPACE)
        if not record:
            return None
        approval = ApprovalRecord.from_dict(record.value)
        self._expire_if_needed(approval)
        self._cache[approval_id] = approval
        return approval

    async def list(self, *, status: str | None = None) -> list[ApprovalRecord]:
        approvals: list[ApprovalRecord] = []
        if self._store:
            for record in await self._store.list(namespace=self.NAMESPACE):
                approval = ApprovalRecord.from_dict(record.value)
                self._expire_if_needed(approval)
                approvals.append(approval)
                self._cache[approval.approval_id] = approval
        else:
            approvals = list(self._cache.values())
            for approval in approvals:
                self._expire_if_needed(approval)
        approvals.sort(key=lambda item: item.created_at, reverse=True)
        if status:
            approvals = [item for item in approvals if item.status == status]
        return approvals

    async def resolve(
        self,
        approval_id: str,
        *,
        approved: bool,
        reviewer: str,
        comment: str | None = None,
    ) -> ApprovalRecord | None:
        approval = await self.get(approval_id)
        if not approval:
            return None
        if approval.status != "pending":
            return approval

        approval.status = "approved" if approved else "rejected"
        approval.reviewer = reviewer
        approval.comment = comment
        approval.resolved_at = utc_iso()

        self._cache[approval_id] = approval
        if self._store:
            await self._store.set(
                approval_id,
                approval.to_dict(),
                namespace=self.NAMESPACE,
                ttl=max(1, approval.expires_at - utc_ts()),
            )
        return approval

    async def is_approved(
        self,
        approval_id: str | None,
        *,
        kind: str,
        payload: dict[str, Any],
    ) -> bool:
        if not approval_id:
            return False
        approval = await self.get(approval_id)
        if not approval:
            return False
        if approval.status != "approved":
            return False
        if approval.kind != kind:
            return False
        payload_hash = stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return approval.payload_hash == payload_hash

    def _expire_if_needed(self, record: ApprovalRecord) -> None:
        if record.status == "pending" and record.expires_at <= utc_ts():
            record.status = "expired"
            record.resolved_at = utc_iso()
            record.comment = "approval expired"


class HandoffEnvelopeV1(BaseModel):
    """Typed handoff envelope v1."""

    version: Literal["1.0"] = Field(default="1.0")
    source_agent: str = Field(description="Source agent id")
    target_agent: str = Field(description="Target agent id")
    task: str = Field(description="Delegated task summary")
    context: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)
    timestamp: str = Field(default_factory=utc_iso)


class HandoffProtocol:
    """Typed handoff protocol with backward-compatible legacy parser."""

    LEGACY_TAG = re.compile(
        r"<handoff[^>]*source=['\"](?P<source>[^'\"]+)['\"][^>]*target=['\"](?P<target>[^'\"]+)['\"][^>]*>(?P<body>.*?)</handoff>",
        re.I | re.S,
    )

    def build_envelope(
        self,
        *,
        source_agent: str,
        target_agent: str,
        task: str,
        context: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        trace_id: str | None = None,
    ) -> HandoffEnvelopeV1:
        return HandoffEnvelopeV1(
            source_agent=source_agent,
            target_agent=target_agent,
            task=task,
            context=context or {},
            artifacts=artifacts or [],
            trace_id=trace_id,
        )

    def parse(self, raw: str) -> HandoffEnvelopeV1:
        raw = (raw or "").strip()
        if not raw:
            raise ValueError("handoff payload is empty")

        # typed envelope JSON
        try:
            maybe_json = json.loads(raw)
            if isinstance(maybe_json, dict) and "source_agent" in maybe_json and "target_agent" in maybe_json:
                return HandoffEnvelopeV1.model_validate(maybe_json)
        except json.JSONDecodeError:
            pass

        # legacy XML-like handoff
        match = self.LEGACY_TAG.search(raw)
        if match:
            source = match.group("source")
            target = match.group("target")
            body = match.group("body").strip()
            context = {"legacy_format": True, "raw": raw}
            return HandoffEnvelopeV1(
                source_agent=source,
                target_agent=target,
                task=body or "legacy handoff",
                context=context,
                artifacts=[],
            )

        raise ValueError("unsupported handoff payload format")


class SLOManager:
    """SLO dashboard + alerts + lightweight circuit breaker."""

    NAMESPACE = "slo"
    SNAPSHOT_KEY = "dashboard"

    def __init__(
        self,
        *,
        store: StateStore | None = None,
        window_size: int = 1000,
        target_success_rate: float = 0.995,
        target_p95_ms: int = 30_000,
        circuit_failure_threshold: int = 5,
        circuit_open_seconds: int = 60,
    ) -> None:
        self._store = store
        self._window_size = window_size
        self._target_success_rate = target_success_rate
        self._target_p95_ms = target_p95_ms
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_open_seconds = circuit_open_seconds

        self._events: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=self._window_size))
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._circuit_open_until: dict[str, int] = defaultdict(int)
        self._alerts: deque[dict[str, Any]] = deque(maxlen=200)

    def should_allow(self, scope: str) -> tuple[bool, str | None]:
        open_until = self._circuit_open_until.get(scope, 0)
        now = utc_ts()
        if open_until > now:
            return False, f"circuit open for scope={scope} until {open_until}"
        return True, None

    async def record(
        self,
        *,
        scope: str,
        success: bool,
        latency_ms: int,
        failure_class: str | None = None,
        retried: bool = False,
    ) -> None:
        event = {
            "timestamp": utc_iso(),
            "scope": scope,
            "success": success,
            "latency_ms": latency_ms,
            "failure_class": failure_class,
            "retried": retried,
        }
        self._events[scope].append(event)

        if success:
            self._consecutive_failures[scope] = 0
        else:
            self._consecutive_failures[scope] += 1
            if self._consecutive_failures[scope] >= self._circuit_failure_threshold:
                self._circuit_open_until[scope] = utc_ts() + self._circuit_open_seconds
                self._alerts.append(
                    {
                        "severity": "critical",
                        "type": "circuit_opened",
                        "scope": scope,
                        "message": f"Circuit opened for scope={scope}",
                        "created_at": utc_iso(),
                    }
                )

        snapshot = self.snapshot()
        self._emit_threshold_alerts(snapshot)
        if self._store:
            await self._store.set(
                self.SNAPSHOT_KEY,
                snapshot,
                namespace=self.NAMESPACE,
                ttl=7 * 24 * 3600,
            )

    async def get_snapshot(self) -> dict[str, Any]:
        if self._store:
            record = await self._store.get(self.SNAPSHOT_KEY, namespace=self.NAMESPACE)
            if record:
                return record.value
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        by_scope: dict[str, Any] = {}
        for scope, events in self._events.items():
            if not events:
                continue
            successes = sum(1 for event in events if event["success"])
            total = len(events)
            success_rate = successes / total if total else 1.0
            latencies = sorted(event["latency_ms"] for event in events)
            p95 = latencies[int((len(latencies) - 1) * 0.95)] if latencies else 0
            failure_classes: dict[str, int] = {}
            retries = sum(1 for event in events if event.get("retried"))
            for event in events:
                failure_class = event.get("failure_class")
                if failure_class:
                    failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
            by_scope[scope] = {
                "total": total,
                "success_rate": round(success_rate, 6),
                "p95_latency_ms": p95,
                "retries": retries,
                "failure_classes": failure_classes,
                "circuit_open": self._circuit_open_until.get(scope, 0) > utc_ts(),
                "circuit_open_until": self._circuit_open_until.get(scope, 0),
                "consecutive_failures": self._consecutive_failures.get(scope, 0),
            }

        return {
            "timestamp": utc_iso(),
            "targets": {
                "success_rate": self._target_success_rate,
                "p95_latency_ms": self._target_p95_ms,
            },
            "by_scope": by_scope,
            "alerts": list(self._alerts),
        }

    def _emit_threshold_alerts(self, snapshot: dict[str, Any]) -> None:
        for scope, stats in snapshot.get("by_scope", {}).items():
            if stats["success_rate"] < self._target_success_rate:
                self._alerts.append(
                    {
                        "severity": "high",
                        "type": "slo_success_rate_breach",
                        "scope": scope,
                        "message": f"success_rate={stats['success_rate']} < target={self._target_success_rate}",
                        "created_at": utc_iso(),
                    }
                )
            if stats["p95_latency_ms"] > self._target_p95_ms:
                self._alerts.append(
                    {
                        "severity": "high",
                        "type": "slo_latency_breach",
                        "scope": scope,
                        "message": f"p95_latency_ms={stats['p95_latency_ms']} > target={self._target_p95_ms}",
                        "created_at": utc_iso(),
                    }
                )

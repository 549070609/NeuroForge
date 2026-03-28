"""
Plan management with in-memory + file dual-write storage.
"""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PlanStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    id: str
    title: str
    status: StepStatus = StepStatus.PENDING
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    estimated_time: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    files_affected: list[str] = field(default_factory=list)
    notes: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "description": self.description,
            "dependencies": self.dependencies,
            "estimated_time": self.estimated_time,
            "acceptance_criteria": self.acceptance_criteria,
            "files_affected": self.files_affected,
            "notes": self.notes,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            status=StepStatus(data.get("status", StepStatus.PENDING.value)),
            description=str(data.get("description", "")),
            dependencies=list(data.get("dependencies", [])),
            estimated_time=str(data.get("estimated_time", "")),
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            files_affected=list(data.get("files_affected", [])),
            notes=data.get("notes"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class PlanFile:
    id: str
    title: str
    objective: str
    status: PlanStatus = PlanStatus.ACTIVE
    priority: str = "medium"
    namespace: str = "default"
    estimated_complexity: str = "medium"
    created: str = field(default_factory=_utc_now_iso)
    updated: str = field(default_factory=_utc_now_iso)
    context: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    change_log: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for step in self.steps if step.status in {StepStatus.COMPLETED, StepStatus.SKIPPED})
        return round((completed / len(self.steps)) * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "status": self.status.value,
            "priority": self.priority,
            "namespace": self.namespace,
            "estimated_complexity": self.estimated_complexity,
            "created": self.created,
            "updated": self.updated,
            "context": self.context,
            "steps": [step.to_dict() for step in self.steps],
            "change_log": self.change_log,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanFile":
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            objective=str(data.get("objective", "")),
            status=PlanStatus(data.get("status", PlanStatus.ACTIVE.value)),
            priority=str(data.get("priority", "medium")),
            namespace=str(data.get("namespace", "default")),
            estimated_complexity=str(data.get("estimated_complexity", "medium")),
            created=str(data.get("created", _utc_now_iso())),
            updated=str(data.get("updated", _utc_now_iso())),
            context=str(data.get("context", "")),
            steps=[PlanStep.from_dict(step) for step in data.get("steps", [])],
            change_log=list(data.get("change_log", [])),
            metadata=dict(data.get("metadata", {})),
        )


class PlanFileManager:
    """Plan manager with in-memory + file dual-write persistence."""

    def __init__(self, plans_dir: str | Path | None = None) -> None:
        default_dir = Path(__file__).resolve().parents[1] / "plans"
        self._plans_dir = Path(plans_dir) if plans_dir else default_dir
        self._plans_dir.mkdir(parents=True, exist_ok=True)
        self._plans: dict[str, PlanFile] = {}
        self._lock = threading.RLock()
        self._load_from_disk()

    def create_plan(
        self,
        title: str,
        objective: str,
        steps: list[dict[str, Any]] | None = None,
        context: str = "",
        priority: str = "medium",
        namespace: str = "default",
        estimated_complexity: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> PlanFile:
        with self._lock:
            plan_id = f"plan-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8]}"
            plan_steps = self._build_steps(steps or [])
            plan = PlanFile(
                id=plan_id,
                title=title,
                objective=objective,
                priority=priority,
                namespace=namespace,
                estimated_complexity=estimated_complexity,
                context=context if isinstance(context, str) else json.dumps(context, ensure_ascii=False),
                steps=plan_steps,
                metadata=metadata or {},
            )
            plan.change_log.append({"timestamp": _utc_now_iso(), "action": "created"})
            self._plans[plan_id] = plan
            self._persist_with_rollback(plan_id, old_plan=None)
            return plan

    def get_plan(self, plan_id: str) -> PlanFile | None:
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(
        self,
        namespace: str | None = None,
        status: PlanStatus | None = None,
    ) -> list[PlanFile]:
        with self._lock:
            plans = list(self._plans.values())
            if namespace:
                plans = [plan for plan in plans if plan.namespace == namespace]
            if status:
                plans = [plan for plan in plans if plan.status == status]
            return sorted(plans, key=lambda p: p.updated, reverse=True)

    def update_step(
        self,
        plan_id: str,
        step_id: str,
        status: StepStatus | None = None,
        notes: str | None = None,
    ) -> PlanFile | None:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            old_plan = copy.deepcopy(plan)
            step = next((item for item in plan.steps if item.id == step_id), None)
            if not step:
                return None

            if status is not None:
                step.status = status
                if status == StepStatus.IN_PROGRESS and not step.started_at:
                    step.started_at = _utc_now_iso()
                if status in {StepStatus.COMPLETED, StepStatus.SKIPPED}:
                    step.completed_at = _utc_now_iso()

            if notes is not None:
                step.notes = notes

            if plan.steps and all(item.status in {StepStatus.COMPLETED, StepStatus.SKIPPED} for item in plan.steps):
                plan.status = PlanStatus.COMPLETED
            elif any(item.status == StepStatus.IN_PROGRESS for item in plan.steps):
                plan.status = PlanStatus.ACTIVE

            plan.updated = _utc_now_iso()
            plan.change_log.append(
                {
                    "timestamp": plan.updated,
                    "action": f"update_step:{step_id}",
                }
            )
            self._persist_with_rollback(plan_id, old_plan=old_plan)
            return plan

    def add_step(
        self,
        plan_id: str,
        title: str,
        description: str = "",
        dependencies: list[str] | None = None,
        estimated_time: str = "",
        acceptance_criteria: list[str] | None = None,
        files_affected: list[str] | None = None,
    ) -> PlanFile | None:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            old_plan = copy.deepcopy(plan)
            step = PlanStep(
                id=self._next_step_id(plan),
                title=title,
                description=description,
                dependencies=dependencies or [],
                estimated_time=estimated_time,
                acceptance_criteria=acceptance_criteria or [],
                files_affected=files_affected or [],
            )
            plan.steps.append(step)
            plan.updated = _utc_now_iso()
            plan.change_log.append(
                {
                    "timestamp": plan.updated,
                    "action": f"add_step:{step.id}",
                }
            )
            self._persist_with_rollback(plan_id, old_plan=old_plan)
            return plan

    def delete_plan(self, plan_id: str) -> bool:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            old_plan = copy.deepcopy(plan)
            self._plans.pop(plan_id, None)
            file_path = self._plan_file_path(plan_id)
            try:
                if file_path.exists():
                    file_path.unlink()
                return True
            except Exception:
                self._plans[plan_id] = old_plan
                return False

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            by_status: dict[str, int] = {}
            for plan in self._plans.values():
                key = plan.status.value
                by_status[key] = by_status.get(key, 0) + 1
            return {
                "total_plans": len(self._plans),
                "by_status": by_status,
            }

    def _build_steps(self, steps: list[dict[str, Any]]) -> list[PlanStep]:
        built_steps: list[PlanStep] = []
        for idx, step_data in enumerate(steps, start=1):
            built_steps.append(
                PlanStep(
                    id=str(step_data.get("id") or f"step-{idx}"),
                    title=str(step_data.get("title", f"Step {idx}")),
                    description=str(step_data.get("description", "")),
                    dependencies=list(step_data.get("dependencies", [])),
                    estimated_time=str(step_data.get("estimated_time", "")),
                    acceptance_criteria=list(step_data.get("acceptance_criteria", [])),
                    files_affected=list(step_data.get("files_affected", [])),
                )
            )
        return built_steps

    def _next_step_id(self, plan: PlanFile) -> str:
        return f"step-{len(plan.steps) + 1}"

    def _plan_file_path(self, plan_id: str) -> Path:
        return self._plans_dir / f"{plan_id}.json"

    def _persist_with_rollback(self, plan_id: str, old_plan: PlanFile | None) -> None:
        try:
            self._persist_plan(self._plans[plan_id])
        except Exception:
            if old_plan is None:
                self._plans.pop(plan_id, None)
            else:
                self._plans[plan_id] = old_plan
            raise

    def _persist_plan(self, plan: PlanFile) -> None:
        file_path = self._plan_file_path(plan.id)
        temp_path = file_path.with_suffix(".json.tmp")
        payload = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(file_path)

    def _load_from_disk(self) -> None:
        for file_path in self._plans_dir.glob("*.json"):
            try:
                raw = file_path.read_text(encoding="utf-8")
                plan = PlanFile.from_dict(json.loads(raw))
                if plan.id:
                    self._plans[plan.id] = plan
            except Exception:
                continue


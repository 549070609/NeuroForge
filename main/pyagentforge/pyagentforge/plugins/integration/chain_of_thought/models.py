"""
思维链数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class ConstraintType(str, Enum):
    """约束类型"""

    HARD = "hard"      # 硬约束：必须满足，违反则阻止执行
    SOFT = "soft"      # 软约束：建议性，违反仅警告
    FORMAT = "format"  # 形式约束：输出格式要求


@dataclass
class Constraint:
    """约束定义"""

    description: str
    constraint_type: ConstraintType = ConstraintType.SOFT
    validator: Callable[[Any], bool] | None = None

    def validate(self, data: Any) -> tuple[bool, str]:
        """验证约束"""
        if self.validator:
            try:
                is_valid = self.validator(data)
                return is_valid, "" if is_valid else self.description
            except Exception as e:
                return False, f"Validation error: {e}"
        return True, ""


@dataclass
class ConstraintViolation:
    """约束违反记录"""

    phase_name: str
    constraint_description: str
    constraint_type: ConstraintType
    violation_details: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CoTPhase:
    """思维链阶段"""

    name: str
    prompt: str
    constraints: list[Constraint] = field(default_factory=list)
    order: int = 0
    is_required: bool = True

    def validate(self, data: Any) -> list[ConstraintViolation]:
        """验证所有约束"""
        violations = []
        for constraint in self.constraints:
            is_valid, details = constraint.validate(data)
            if not is_valid:
                violations.append(ConstraintViolation(
                    phase_name=self.name,
                    constraint_description=constraint.description,
                    constraint_type=constraint.constraint_type,
                    violation_details=details,
                ))
        return violations

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "prompt": self.prompt,
            "constraints": [
                {
                    "description": c.description,
                    "type": c.constraint_type.value,
                }
                for c in self.constraints
            ],
            "order": self.order,
            "is_required": self.is_required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoTPhase":
        """从字典创建"""
        constraints = []
        for c in data.get("constraints", []):
            constraints.append(Constraint(
                description=c.get("description", ""),
                constraint_type=ConstraintType(c.get("type", "soft")),
            ))

        return cls(
            name=data["name"],
            prompt=data.get("prompt", ""),
            constraints=constraints,
            order=data.get("order", 0),
            is_required=data.get("is_required", True),
        )


@dataclass
class ChainOfThought:
    """思维链定义"""

    name: str
    description: str
    phases: list[CoTPhase] = field(default_factory=list)
    version: str = "1.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "user"  # user, agent, llm
    execution_count: int = 0
    success_rate: float = 0.0

    def get_phase(self, name: str) -> CoTPhase | None:
        """获取指定阶段"""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None

    def get_ordered_phases(self) -> list[CoTPhase]:
        """获取排序后的阶段列表"""
        return sorted(self.phases, key=lambda p: p.order)

    def validate_all(self, data_map: dict[str, Any]) -> list[ConstraintViolation]:
        """验证所有阶段的约束"""
        all_violations = []
        for phase in self.phases:
            data = data_map.get(phase.name)
            if data is not None:
                violations = phase.validate(data)
                all_violations.extend(violations)
        return all_violations

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "phases": [p.to_dict() for p in self.phases],
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "execution_count": self.execution_count,
            "success_rate": self.success_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChainOfThought":
        """从字典创建"""
        phases = [CoTPhase.from_dict(p) for p in data.get("phases", [])]

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            phases=phases,
            version=data.get("version", "1.0"),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            source=data.get("source", "user"),
            execution_count=data.get("execution_count", 0),
            success_rate=data.get("success_rate", 0.0),
        )


@dataclass
class CoTExecutionTrace:
    """思维链执行轨迹"""

    cot_name: str
    session_id: str
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str | None = None
    phase_results: dict[str, Any] = field(default_factory=dict)
    violations: list[ConstraintViolation] = field(default_factory=list)
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    reflection: str | None = None

    def add_phase_result(self, phase_name: str, result: Any) -> None:
        """添加阶段结果"""
        self.phase_results[phase_name] = {
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def add_violation(self, violation: ConstraintViolation) -> None:
        """添加约束违反"""
        self.violations.append(violation)

    def complete(self, success: bool, reflection: str | None = None) -> None:
        """完成执行"""
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.success = success
        self.reflection = reflection

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "cot_name": self.cot_name,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "phase_results": self.phase_results,
            "violations": [v.__dict__ for v in self.violations],
            "plan_steps": self.plan_steps,
            "success": self.success,
            "reflection": self.reflection,
        }

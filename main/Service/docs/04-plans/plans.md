# Plan Management

## Schemas

```python
from Service.schemas.agents import (
    PlanCreate, PlanResponse, PlanListResponse, PlanStatsResponse,
    StepCreate, StepResponse, StepUpdateRequest, StepAddRequest,
)
```

```python
class PlanCreate:
    title: str                              # required
    objective: str                          # required
    priority: str = "medium"               # "high" | "medium" | "low"
    namespace: str = "default"
    estimated_complexity: str = "medium"   # "high" | "medium" | "low"
    context: str | None = None
    steps: list[StepCreate] | None = None
    metadata: dict | None = None

class StepCreate:
    title: str                             # required
    description: str | None = None
    dependencies: list[str] | None = None  # step IDs
    estimated_time: str | None = None      # "2h", "1d"
    acceptance_criteria: list[str] | None = None
    files_affected: list[str] | None = None

class StepUpdateRequest:
    status: str | None = None   # "pending"|"in_progress"|"completed"|"blocked"|"skipped"
    notes: str | None = None

class PlanResponse:
    id: str                     # "plan-20260228-xxxxxx"
    title: str
    objective: str
    status: str                 # "active" | "completed" | "archived"
    priority: str
    namespace: str
    estimated_complexity: str
    steps: list[StepResponse]
    progress: float             # 0.0–1.0
    change_log: list[dict]
    created: str                # ISO-8601
    updated: str
```

## Operations

```python
# via AgentService (auto-initialized by create_app())
service.list_plans(namespace=None, status=None) -> PlanListResponse
service.get_plan(plan_id) -> PlanResponse           # raises KeyError if not found
service.delete_plan(plan_id)
service.get_plan_stats() -> PlanStatsResponse       # {total_plans, by_status}

plan = service.create_plan(PlanCreate(
    title="Payment Refactor",
    objective="Reduce timeout failure rate",
    priority="high",
    namespace="payment",
    steps=[
        StepCreate(title="Analyze failure logs", estimated_time="2h"),
        StepCreate(title="Design retry logic", dependencies=["step-1"], estimated_time="4h"),
    ],
))

service.update_step(plan.id, "step-1", StepUpdateRequest(status="in_progress"))
service.add_step(plan.id, StepAddRequest(title="Add regression tests", estimated_time="4h"))
```

## Plan YAML Format

```yaml
id: plan-20260228-abc123
title: Payment Refactor
objective: Reduce timeout failure rate
priority: high
namespace: payment
status: active
estimated_complexity: medium
steps:
  - id: step-1
    title: Analyze failure logs
    status: pending
    estimated_time: 2h
    dependencies: []
  - id: step-2
    title: Design retry logic
    status: pending
    estimated_time: 4h
    dependencies: [step-1]
```

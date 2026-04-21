"""P1-11 Plan 并发安全 + tz-aware datetime 回归测试。"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import timezone

import pytest

from Agent.core.plan_manager import PlanFileManager, PlanStatus, StepStatus


class TestPlanTzAwareDatetime:
    def test_utc_now_iso_ends_with_z(self):
        from Agent.core.plan_manager import _utc_now_iso
        ts = _utc_now_iso()
        assert ts.endswith("Z")

    def test_plan_created_has_z_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = PlanFileManager(plans_dir=d)
            plan = mgr.create_plan(title="t", objective="o")
            assert plan.created.endswith("Z")
            assert plan.updated.endswith("Z")


@pytest.mark.asyncio
class TestPlanConcurrency:
    async def test_concurrent_step_updates_no_data_loss(self):
        """多个并发 async_update_step 不丢数据。"""
        with tempfile.TemporaryDirectory() as d:
            mgr = PlanFileManager(plans_dir=d)
            plan = mgr.create_plan(
                title="concurrent",
                objective="test",
                steps=[
                    {"title": f"step-{i}"} for i in range(10)
                ],
            )
            plan_id = plan.id
            step_ids = [s.id for s in plan.steps]

            async def update_one(sid: str):
                await mgr.async_update_step(
                    plan_id, sid, status=StepStatus.COMPLETED, notes=f"done-{sid}",
                )

            await asyncio.gather(*[update_one(sid) for sid in step_ids])

            final = mgr.get_plan(plan_id)
            assert final is not None
            completed = [s for s in final.steps if s.status == StepStatus.COMPLETED]
            assert len(completed) == 10

    async def test_concurrent_add_steps(self):
        """多个并发 async_add_step 不丢步骤。"""
        with tempfile.TemporaryDirectory() as d:
            mgr = PlanFileManager(plans_dir=d)
            plan = mgr.create_plan(title="add-test", objective="test")
            plan_id = plan.id

            async def add_one(i: int):
                await mgr.async_add_step(plan_id, f"new-step-{i}")

            await asyncio.gather(*[add_one(i) for i in range(5)])

            final = mgr.get_plan(plan_id)
            assert final is not None
            assert len(final.steps) == 5

    async def test_per_plan_lock_isolation(self):
        """不同 plan 的 lock 相互独立。"""
        with tempfile.TemporaryDirectory() as d:
            mgr = PlanFileManager(plans_dir=d)
            lock_a = mgr._get_plan_lock("plan-a")
            lock_b = mgr._get_plan_lock("plan-b")
            assert lock_a is not lock_b
            assert mgr._get_plan_lock("plan-a") is lock_a

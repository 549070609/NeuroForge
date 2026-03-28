"""Tests for PlanFileManager dual-write behavior."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from main.Agent.core.plan_manager import PlanFileManager, PlanStatus, StepStatus


def test_create_get_list_and_dual_write(tmp_path: Path):
    manager = PlanFileManager(plans_dir=tmp_path)
    plan = manager.create_plan(
        title="P0",
        objective="close loop",
        steps=[{"title": "first step"}],
        namespace="demo",
    )

    got = manager.get_plan(plan.id)
    assert got is not None
    assert got.id == plan.id

    listed = manager.list_plans(namespace="demo")
    assert len(listed) == 1
    assert listed[0].id == plan.id

    file_path = tmp_path / f"{plan.id}.json"
    assert file_path.exists()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    assert payload["id"] == plan.id
    assert payload["title"] == "P0"


def test_update_add_delete_stats_and_reload(tmp_path: Path):
    manager = PlanFileManager(plans_dir=tmp_path)
    plan = manager.create_plan(
        title="Plan",
        objective="run",
        steps=[{"title": "step one"}],
    )

    updated = manager.update_step(plan.id, "step-1", status=StepStatus.IN_PROGRESS, notes="started")
    assert updated is not None
    assert updated.steps[0].status == StepStatus.IN_PROGRESS
    assert updated.steps[0].notes == "started"

    completed = manager.update_step(plan.id, "step-1", status=StepStatus.COMPLETED)
    assert completed is not None
    assert completed.steps[0].status == StepStatus.COMPLETED
    assert completed.status == PlanStatus.COMPLETED

    with_extra = manager.add_step(plan.id, title="step two")
    assert with_extra is not None
    assert len(with_extra.steps) == 2

    stats = manager.get_stats()
    assert stats["total_plans"] == 1
    assert stats["by_status"]["completed"] == 1

    reloaded = PlanFileManager(plans_dir=tmp_path)
    reloaded_plan = reloaded.get_plan(plan.id)
    assert reloaded_plan is not None
    assert len(reloaded_plan.steps) == 2

    assert manager.delete_plan(plan.id) is True
    assert manager.get_plan(plan.id) is None
    assert not (tmp_path / f"{plan.id}.json").exists()


def test_invalid_transition_and_missing_objects(tmp_path: Path):
    manager = PlanFileManager(plans_dir=tmp_path)
    plan = manager.create_plan(
        title="Plan",
        objective="run",
        steps=[{"title": "step one"}],
    )

    assert manager.update_step("missing", "step-1", status=StepStatus.IN_PROGRESS) is None
    assert manager.update_step(plan.id, "missing-step", status=StepStatus.IN_PROGRESS) is None

    assert manager.update_step(plan.id, "step-1", status=StepStatus.COMPLETED) is not None
    assert manager.update_step(plan.id, "step-1", status=StepStatus.IN_PROGRESS) is None


def test_dual_write_rollback_on_persist_failure(tmp_path: Path, monkeypatch):
    manager = PlanFileManager(plans_dir=tmp_path)

    def raise_disk_error(_plan):
        raise OSError("disk write failed")

    monkeypatch.setattr(manager, "_persist_plan", raise_disk_error)

    with pytest.raises(OSError):
        manager.create_plan(title="broken", objective="rollback")

    assert manager.list_plans() == []

    manager_ok = PlanFileManager(plans_dir=tmp_path)
    plan = manager_ok.create_plan(
        title="ok",
        objective="rollback update",
        steps=[{"title": "step one"}],
    )
    monkeypatch.setattr(manager_ok, "_persist_plan", raise_disk_error)

    with pytest.raises(OSError):
        manager_ok.add_step(plan.id, title="step two")

    still = manager_ok.get_plan(plan.id)
    assert still is not None
    assert len(still.steps) == 1

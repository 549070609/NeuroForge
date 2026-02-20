"""
Task Progress Report System

Generates progress reports for tasks and summaries.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class TaskReport:
    """Single task progress report"""

    task: Any  # Task
    progress_percentage: float
    subtasks_progress: dict[str, float]
    dependencies_status: dict[str, str]
    time_elapsed: timedelta | None
    estimated_remaining: timedelta | None
    blockers: list[str]


@dataclass
class SummaryReport:
    """Summary report for all tasks"""

    total_tasks: int
    completed: int
    in_progress: int
    pending: int
    blocked: int
    overall_progress: float
    by_type: dict[str, int]
    by_complexity: dict[str, int]


class TaskReporter:
    """Generate task progress reports"""

    def __init__(self, manager: Any):  # TaskManager
        self.manager = manager

    def generate_progress_report(self, task_id: str) -> TaskReport | None:
        """
        Generate report for a single task

        Args:
            task_id: Task ID

        Returns:
            TaskReport or None if task not found
        """
        task = self.manager.get_task(task_id)
        if not task:
            return None

        # Calculate subtask progress
        subtasks = self.manager.get_subtasks(task_id)
        subtasks_progress = {s.id: s.progress for s in subtasks}

        # Check dependencies
        dependencies_status = {}
        for dep_id in task.blockedBy:
            dep = self.manager.get_task(dep_id)
            dependencies_status[dep_id] = dep.status.value if dep else "unknown"

        # Calculate time
        time_elapsed = None
        if task.created_at:
            try:
                created = datetime.fromisoformat(task.created_at.replace("Z", "+00:00"))
                time_elapsed = datetime.now(created.tzinfo) - created
            except Exception:
                pass

        estimated_remaining = None
        if task.estimated_hours and task.progress > 0:
            elapsed_hours = time_elapsed.total_seconds() / 3600 if time_elapsed else 0
            total_estimated = elapsed_hours / task.progress
            remaining = total_estimated - elapsed_hours
            estimated_remaining = timedelta(hours=remaining)

        # Identify blockers
        blockers = [dep_id for dep_id, status in dependencies_status.items() if status != "completed"]

        return TaskReport(
            task=task,
            progress_percentage=task.progress * 100,
            subtasks_progress=subtasks_progress,
            dependencies_status=dependencies_status,
            time_elapsed=time_elapsed,
            estimated_remaining=estimated_remaining,
            blockers=blockers,
        )

    def generate_summary_report(self, status_filter: str | None = None) -> SummaryReport:
        """
        Generate summary report

        Args:
            status_filter: Optional status filter

        Returns:
            SummaryReport
        """
        from .PLUGIN import TaskStatus

        tasks = self.manager.list_tasks(
            status=TaskStatus(status_filter) if status_filter else None
        )

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status.value == "completed")
        in_progress = sum(1 for t in tasks if t.status.value == "in_progress")
        pending = sum(1 for t in tasks if t.status.value == "pending")

        blocked = sum(1 for t in tasks if t.blockedBy)

        overall_progress = sum(t.progress for t in tasks) / total if total > 0 else 0

        by_type: dict[str, int] = {}
        by_complexity: dict[str, int] = {}

        for task in tasks:
            type_key = task.task_type.value if hasattr(task, "task_type") else "unknown"
            by_type[type_key] = by_type.get(type_key, 0) + 1

            comp_key = task.complexity.value if hasattr(task, "complexity") else "unknown"
            by_complexity[comp_key] = by_complexity.get(comp_key, 0) + 1

        return SummaryReport(
            total_tasks=total,
            completed=completed,
            in_progress=in_progress,
            pending=pending,
            blocked=blocked,
            overall_progress=overall_progress,
            by_type=by_type,
            by_complexity=by_complexity,
        )

    def format_report(self, report: TaskReport, format: str = "markdown") -> str:
        """
        Format report for display

        Args:
            report: TaskReport to format
            format: "markdown", "json", or "text"

        Returns:
            Formatted report string
        """
        if format == "json":
            import json

            return json.dumps(
                {
                    "task_id": report.task.id,
                    "title": report.task.title,
                    "status": report.task.status.value,
                    "progress": report.progress_percentage,
                    "subtasks": report.subtasks_progress,
                    "blockers": report.blockers,
                    "time_elapsed": str(report.time_elapsed) if report.time_elapsed else None,
                    "estimated_remaining": str(report.estimated_remaining)
                    if report.estimated_remaining
                    else None,
                },
                indent=2,
            )

        # Markdown format
        lines = [
            f"# Task Progress Report",
            f"",
            f"## Overview",
            f"- **Task ID**: {report.task.id}",
            f"- **Title**: {report.task.title}",
            f"- **Status**: {report.task.status.value}",
            f"- **Progress**: {report.progress_percentage:.1f}%",
            f"- **Priority**: {report.task.priority.value}",
            f"- **Type**: {report.task.task_type.value}",
            f"- **Complexity**: {report.task.complexity.value}",
            f"",
        ]

        if report.subtasks_progress:
            lines.append("## Subtasks")
            for subtask_id, progress in report.subtasks_progress.items():
                subtask = self.manager.get_task(subtask_id)
                status = "✅" if progress >= 1.0 else "🔄" if progress > 0 else "⏳"
                title = subtask.title if subtask else subtask_id
                lines.append(f"- {status} **{title}** ({progress * 100:.0f}%)")
            lines.append("")

        if report.blockers:
            lines.append("## Blockers")
            for blocker in report.blockers:
                blocker_task = self.manager.get_task(blocker)
                blocker_info = blocker_task.title if blocker_task else blocker
                lines.append(f"- ⚠️ {blocker_info} (Status: {blocker_task.status.value if blocker_task else 'unknown'})")
            lines.append("")

        if report.time_elapsed:
            lines.append("## Time Tracking")
            elapsed_str = self._format_timedelta(report.time_elapsed)
            lines.append(f"- **Elapsed**: {elapsed_str}")
            if report.estimated_remaining:
                remaining_str = self._format_timedelta(report.estimated_remaining)
                lines.append(f"- **Estimated Remaining**: {remaining_str}")
            lines.append("")

        return "\n".join(lines)

    def format_summary(self, summary: SummaryReport, format: str = "markdown") -> str:
        """
        Format summary report

        Args:
            summary: SummaryReport to format
            format: "markdown" or "text"

        Returns:
            Formatted summary string
        """
        if format == "text":
            return (
                f"Total: {summary.total_tasks}, "
                f"Completed: {summary.completed}, "
                f"In Progress: {summary.in_progress}, "
                f"Pending: {summary.pending}, "
                f"Blocked: {summary.blocked}, "
                f"Progress: {summary.overall_progress * 100:.0f}%"
            )

        # Markdown format
        lines = [
            "# Task Summary Report",
            "",
            "## Overview",
            f"- **Total Tasks**: {summary.total_tasks}",
            f"- **Completed**: {summary.completed}",
            f"- **In Progress**: {summary.in_progress}",
            f"- **Pending**: {summary.pending}",
            f"- **Blocked**: {summary.blocked}",
            f"- **Overall Progress**: {summary.overall_progress * 100:.1f}%",
            "",
        ]

        if summary.by_type:
            lines.append("## By Type")
            for task_type, count in sorted(summary.by_type.items()):
                lines.append(f"- **{task_type.title()}**: {count}")
            lines.append("")

        if summary.by_complexity:
            lines.append("## By Complexity")
            for complexity, count in sorted(summary.by_complexity.items()):
                lines.append(f"- **{complexity.title()}**: {count}")
            lines.append("")

        return "\n".join(lines)

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta for display"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

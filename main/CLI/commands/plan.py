"""
Plan commands - Manage plans.

Commands:
    list        List all plans
    get         Get plan details
    create      Create a new plan
    delete      Delete a plan
    stats       Show plan statistics
    step        Manage plan steps
"""

from typing import Optional

import typer
from rich.table import Table
from rich.panel import Panel

from CLI.core import async_command, get_context, console, print_json, print_error, print_success

app = typer.Typer(help="Plan management commands")


@app.command("list")
@async_command
async def list_plans(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Filter by namespace"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all plans."""
    ctx = get_context()

    result = ctx.agent.list_plans(namespace=namespace, status=status)
    result_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    if json_output:
        print_json(result_dict)
        return

    plans = result_dict.get("plans", [])
    if not plans:
        console.print("[yellow]No plans found.[/yellow]")
        return

    table = Table(title=f"Plans ({result_dict.get('total', 0)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Priority", style="yellow")
    table.add_column("Progress", style="blue")

    for plan in plans:
        p_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan
        steps = p_dict.get("steps", [])
        completed = sum(1 for s in steps if s.get("status") == "completed")
        total = len(steps)
        progress = f"{completed}/{total}" if total > 0 else "-"

        table.add_row(
            str(p_dict.get("id", "-"))[:12],
            str(p_dict.get("title", "-"))[:30],
            str(p_dict.get("status", "-")),
            str(p_dict.get("priority", "-")),
            progress,
        )

    console.print(table)


@app.command("get")
@async_command
async def get_plan(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Get plan details."""
    ctx = get_context()

    plan = ctx.agent.get_plan(plan_id)

    if not plan:
        print_error(f"Plan not found: {plan_id}")
        raise typer.Exit(1)

    plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__

    if json_output:
        print_json(plan_dict)
        return

    # Print plan header
    console.print(f"\n[bold cyan]Plan: {plan_dict.get('title', '-')}[/bold cyan]")
    console.print(f"[dim]ID: {plan_dict.get('id', '-')}[/dim]\n")

    # Info table
    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Status", str(plan_dict.get("status", "-")))
    info_table.add_row("Priority", str(plan_dict.get("priority", "-")))
    info_table.add_row("Namespace", str(plan_dict.get("namespace", "-")))
    info_table.add_row("Objective", str(plan_dict.get("objective", "-")))

    console.print(info_table)

    # Print steps
    steps = plan_dict.get("steps", [])
    if steps:
        console.print("\n[bold]Steps:[/bold]")

        steps_table = Table()
        steps_table.add_column("#", style="dim")
        steps_table.add_column("Title", style="green")
        steps_table.add_column("Status", style="magenta")
        steps_table.add_column("Description")

        for i, step in enumerate(steps, 1):
            s_dict = step.model_dump() if hasattr(step, "model_dump") else step
            status = s_dict.get("status", "pending")
            status_style = {
                "completed": "[green]✓ completed[/green]",
                "in_progress": "[yellow]► in_progress[/yellow]",
                "pending": "[dim]○ pending[/dim]",
                "failed": "[red]✗ failed[/red]",
            }.get(status, status)

            steps_table.add_row(
                str(i),
                str(s_dict.get("title", "-"))[:25],
                status_style,
                str(s_dict.get("description", "-"))[:40],
            )

        console.print(steps_table)


@app.command("create")
@async_command
async def create_plan(
    title: str = typer.Option(..., "--title", "-t", help="Plan title"),
    objective: str = typer.Option(..., "--objective", "-o", help="Plan objective"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Namespace"),
    priority: str = typer.Option("medium", "--priority", "-p", help="Priority (low/medium/high)"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="JSON context"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Create a new plan."""
    ctx = get_context()

    # Import request model
    from Service.schemas import PlanCreate

    context_dict = {}
    if context:
        import json
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            print_error("Invalid JSON context")
            raise typer.Exit(1)

    request = PlanCreate(
        title=title,
        objective=objective,
        namespace=namespace,
        priority=priority,
        context=context_dict,
    )

    plan = ctx.agent.create_plan(request)

    if not plan:
        print_error("Failed to create plan")
        raise typer.Exit(1)

    plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__

    if json_output:
        print_json(plan_dict)
        return

    print_success(f"Plan created successfully")
    console.print(f"  ID: [cyan]{plan_dict.get('id', '-')}[/cyan]")
    console.print(f"  Title: {plan_dict.get('title', '-')}")


@app.command("delete")
@async_command
async def delete_plan(
    plan_id: str = typer.Argument(..., help="Plan ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
) -> None:
    """Delete a plan."""
    ctx = get_context()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete plan '{plan_id}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    result = ctx.agent.delete_plan(plan_id)

    if result:
        print_success(f"Plan '{plan_id}' deleted successfully")
    else:
        print_error(f"Failed to delete plan: {plan_id}")
        raise typer.Exit(1)


@app.command("stats")
@async_command
async def plan_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show plan statistics."""
    ctx = get_context()

    stats = ctx.agent.get_plan_stats()
    stats_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

    if json_output:
        print_json(stats_dict)
        return

    console.print("\n[bold cyan]Plan Statistics[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Total Plans", str(stats_dict.get("total_plans", 0)))

    by_status = stats_dict.get("by_status", {})
    for status, count in by_status.items():
        table.add_row(f"  {status}", str(count))

    console.print(table)


# Step management subcommands
step_app = typer.Typer(help="Plan step management")
app.add_typer(step_app, name="step")


@step_app.command("add")
@async_command
async def add_step(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    title: str = typer.Option(..., "--title", "-t", help="Step title"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Step description"),
    dependencies: Optional[str] = typer.Option(None, "--deps", help="Comma-separated dependency step IDs"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Add a step to a plan."""
    ctx = get_context()

    from Service.schemas import StepAddRequest

    deps_list = [d.strip() for d in dependencies.split(",")] if dependencies else None

    request = StepAddRequest(
        title=title,
        description=description,
        dependencies=deps_list,
    )

    plan = ctx.agent.add_step(plan_id, request)

    if not plan:
        print_error(f"Failed to add step to plan: {plan_id}")
        raise typer.Exit(1)

    plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__

    if json_output:
        print_json(plan_dict)
        return

    print_success(f"Step added to plan '{plan_id}'")


@step_app.command("update")
@async_command
async def update_step(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    step_id: str = typer.Argument(..., help="Step ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="New status"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Notes"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Update a step in a plan."""
    ctx = get_context()

    from Service.schemas import StepUpdateRequest

    request = StepUpdateRequest(
        status=status,
        notes=notes,
    )

    plan = ctx.agent.update_step(plan_id, step_id, request)

    if not plan:
        print_error(f"Failed to update step in plan: {plan_id}")
        raise typer.Exit(1)

    plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__

    if json_output:
        print_json(plan_dict)
        return

    print_success(f"Step '{step_id}' updated in plan '{plan_id}'")


if __name__ == "__main__":
    app()

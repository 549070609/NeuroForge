"""
Workspace commands - Manage workspaces.

Commands:
    create      Create a new workspace
    list        List all workspaces
    get         Get workspace details
    remove      Remove a workspace
    stats       Show workspace statistics
"""

from typing import Optional

import typer
from rich.table import Table

from CLI.core import async_command, get_context, console, print_table, print_json, print_error, print_success

app = typer.Typer(help="Workspace management commands")


@app.command("create")
@async_command
async def create_workspace(
    workspace_id: str = typer.Argument(..., help="Unique workspace ID"),
    path: str = typer.Option(..., "--path", "-p", help="Root path for workspace"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Workspace namespace"),
    readonly: bool = typer.Option(False, "--readonly", "-r", help="Make workspace read-only"),
    allowed_tools: Optional[str] = typer.Option(None, "--allowed", "-a", help="Allowed tools (comma-separated, * for all)"),
    denied_tools: Optional[str] = typer.Option(None, "--denied", "-d", help="Denied tools (comma-separated)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Create a new workspace."""
    ctx = get_context()

    allowed = [t.strip() for t in allowed_tools.split(",")] if allowed_tools else None
    denied = [t.strip() for t in denied_tools.split(",")] if denied_tools else None

    result = ctx.proxy.create_workspace(
        workspace_id=workspace_id,
        root_path=path,
        namespace=namespace,
        allowed_tools=allowed,
        denied_tools=denied,
        is_readonly=readonly,
    )

    if json_output:
        print_json(result)
        return

    print_success(f"Workspace '{workspace_id}' created successfully")
    console.print(f"  Path: {result.get('root_path', '-')}")
    console.print(f"  Namespace: {result.get('namespace', '-')}")
    console.print(f"  Read-only: {result.get('is_readonly', False)}")


@app.command("list")
@async_command
async def list_workspaces(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all workspaces."""
    ctx = get_context()

    workspace_ids = ctx.proxy.list_workspaces()

    if json_output:
        print_json({"workspaces": workspace_ids, "total": len(workspace_ids)})
        return

    if not workspace_ids:
        console.print("[yellow]No workspaces found.[/yellow]")
        return

    # Get details for each workspace
    table = Table(title=f"Workspaces ({len(workspace_ids)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Namespace", style="blue")
    table.add_column("Read-only", style="magenta")

    for ws_id in workspace_ids:
        ws = ctx.proxy.get_workspace(ws_id)
        if ws:
            table.add_row(
                ws_id,
                ws.get("root_path", "-"),
                ws.get("namespace", "-"),
                str(ws.get("is_readonly", False)),
            )
        else:
            table.add_row(ws_id, "-", "-", "-")

    console.print(table)


@app.command("get")
@async_command
async def get_workspace(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Get workspace details."""
    ctx = get_context()

    workspace = ctx.proxy.get_workspace(workspace_id)

    if not workspace:
        print_error(f"Workspace not found: {workspace_id}")
        raise typer.Exit(1)

    if json_output:
        print_json(workspace)
        return

    console.print(f"\n[bold cyan]Workspace: {workspace_id}[/bold cyan]\n")

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Root Path", str(workspace.get("root_path", "-")))
    info_table.add_row("Namespace", str(workspace.get("namespace", "-")))
    info_table.add_row("Read-only", str(workspace.get("is_readonly", False)))

    allowed = workspace.get("allowed_tools", [])
    if allowed:
        info_table.add_row("Allowed Tools", ", ".join(allowed) if allowed != ["*"] else "* (all)")

    denied = workspace.get("denied_tools", [])
    if denied:
        info_table.add_row("Denied Tools", ", ".join(denied))

    console.print(info_table)


@app.command("remove")
@async_command
async def remove_workspace(
    workspace_id: str = typer.Argument(..., help="Workspace ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal without confirmation"),
) -> None:
    """Remove a workspace."""
    ctx = get_context()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to remove workspace '{workspace_id}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    result = await ctx.proxy.remove_workspace(workspace_id)

    if result:
        print_success(f"Workspace '{workspace_id}' removed successfully")
    else:
        print_error(f"Failed to remove workspace: {workspace_id}")
        raise typer.Exit(1)


@app.command("stats")
@async_command
async def workspace_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show workspace statistics."""
    ctx = get_context()

    stats = ctx.proxy.get_stats()

    if json_output:
        print_json(stats)
        return

    console.print("\n[bold cyan]Workspace Statistics[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(str(key), str(value))

    console.print(table)


if __name__ == "__main__":
    app()

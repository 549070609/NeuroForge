"""
Agent commands - Manage and interact with Agents.

Commands:
    list        List all available agents
    get         Get details of a specific agent
    stats       Show agent statistics
    refresh     Refresh agent directory cache
    namespaces  List all namespaces
"""

from typing import Optional

import typer
from rich.table import Table

from CLI.core import async_command, get_context, console, print_table, print_json, print_error

app = typer.Typer(help="Agent management commands")


@app.command("list")
@async_command
async def list_agents(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Filter by namespace"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all available agents."""
    ctx = get_context()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    result = ctx.agent.list_agents(namespace=namespace, tags=tag_list)

    if json_output:
        print_json({
            "agents": [a.model_dump() if hasattr(a, "model_dump") else a.__dict__ for a in result.agents],
            "total": result.total,
            "namespaces": result.namespaces,
        })
        return

    if not result.agents:
        console.print("[yellow]No agents found.[/yellow]")
        return

    table = Table(title=f"Agents ({result.total} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Namespace", style="blue")
    table.add_column("Origin", style="magenta")
    table.add_column("Tags", style="yellow")
    table.add_column("Category")

    for agent in result.agents:
        agent_dict = agent.model_dump() if hasattr(agent, "model_dump") else agent.__dict__
        tags_str = ", ".join(agent_dict.get("tags", [])[:3])
        if len(agent_dict.get("tags", [])) > 3:
            tags_str += "..."

        table.add_row(
            agent_dict.get("id", "-"),
            agent_dict.get("name", "-"),
            agent_dict.get("namespace", "-"),
            agent_dict.get("origin", "-"),
            tags_str or "-",
            agent_dict.get("category", "-"),
        )

    console.print(table)

    if result.namespaces:
        console.print(f"\n[dim]Namespaces: {', '.join(result.namespaces)}[/dim]")


@app.command("get")
@async_command
async def get_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to retrieve"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Get details of a specific agent."""
    ctx = get_context()

    agent = ctx.agent.get_agent(agent_id)

    if not agent:
        print_error(f"Agent not found: {agent_id}")
        raise typer.Exit(1)

    agent_dict = agent.model_dump() if hasattr(agent, "model_dump") else agent.__dict__

    if json_output:
        print_json(agent_dict)
        return

    # Print formatted output
    console.print(f"\n[bold cyan]Agent: {agent_dict.get('name', '-')}[/bold cyan]")
    console.print(f"[dim]ID: {agent_dict.get('id', '-')}[/dim]\n")

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Namespace", str(agent_dict.get("namespace", "-")))
    info_table.add_row("Origin", str(agent_dict.get("origin", "-")))
    info_table.add_row("Category", str(agent_dict.get("category", "-")))
    info_table.add_row("Description", str(agent_dict.get("description", "-") or "N/A"))
    info_table.add_row("Read-only", str(agent_dict.get("is_readonly", False)))
    info_table.add_row("Max Concurrent", str(agent_dict.get("max_concurrent", 1)))
    info_table.add_row("Tags", ", ".join(agent_dict.get("tags", [])) or "None")
    info_table.add_row("Tools", ", ".join(agent_dict.get("tools", []))[:50] + "..." if len(", ".join(agent_dict.get("tools", []))) > 50 else ", ".join(agent_dict.get("tools", [])) or "None")

    console.print(info_table)


@app.command("stats")
@async_command
async def agent_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show agent statistics."""
    ctx = get_context()

    stats = ctx.agent.get_stats()
    stats_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

    if json_output:
        print_json(stats_dict)
        return

    console.print("\n[bold cyan]Agent Statistics[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Total Agents", str(stats_dict.get("total_agents", 0)))
    table.add_row("Total Namespaces", str(stats_dict.get("total_namespaces", 0)))

    console.print(table)

    # By origin breakdown
    by_origin = stats_dict.get("by_origin", {})
    if by_origin:
        console.print("\n[bold]By Origin:[/bold]")
        origin_table = Table(show_header=False, box=None)
        origin_table.add_column("Origin", style="blue")
        origin_table.add_column("Count", style="cyan")
        for origin, count in by_origin.items():
            origin_table.add_row(str(origin), str(count))
        console.print(origin_table)

    # Namespaces breakdown
    namespaces = stats_dict.get("namespaces", [])
    if namespaces:
        console.print(f"\n[bold]Namespaces:[/bold] {', '.join(namespaces)}")


@app.command("refresh")
@async_command
async def refresh_agents() -> None:
    """Refresh agent directory cache."""
    ctx = get_context()
    ctx.agent.refresh()
    console.print("[green]Agent cache refreshed successfully.[/green]")


@app.command("namespaces")
@async_command
async def list_namespaces(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all namespaces."""
    ctx = get_context()

    result = ctx.agent.list_namespaces()
    result_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    if json_output:
        print_json(result_dict)
        return

    console.print(f"\n[bold cyan]Namespaces ({result_dict.get('total', 0)} total)[/bold cyan]\n")

    table = Table()
    table.add_column("Name", style="green")
    table.add_column("Agent Count", style="cyan")

    for ns in result_dict.get("namespaces", []):
        ns_dict = ns.model_dump() if hasattr(ns, "model_dump") else ns
        table.add_row(
            str(ns_dict.get("name", "-")),
            str(ns_dict.get("agent_count", 0)),
        )

    console.print(table)


if __name__ == "__main__":
    app()

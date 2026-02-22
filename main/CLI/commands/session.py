"""
Session commands - Manage sessions.

Commands:
    create      Create a new session
    list        List all sessions
    get         Get session details
    delete      Delete a session
"""

from typing import Optional

import typer
from rich.table import Table

from CLI.core import async_command, get_context, console, print_json, print_error, print_success

app = typer.Typer(help="Session management commands")


@app.command("create")
@async_command
async def create_session(
    workspace_id: str = typer.Option(..., "--workspace", "-w", help="Workspace ID"),
    agent_id: str = typer.Option(..., "--agent", "-a", help="Agent ID"),
    metadata: Optional[str] = typer.Option(None, "--metadata", "-m", help="JSON metadata"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Create a new session."""
    ctx = get_context()

    meta_dict = {}
    if metadata:
        import json
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            print_error("Invalid JSON metadata")
            raise typer.Exit(1)

    session = await ctx.proxy.create_session(
        workspace_id=workspace_id,
        agent_id=agent_id,
        metadata=meta_dict,
    )

    session_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__

    if json_output:
        print_json(session_dict)
        return

    print_success(f"Session created successfully")
    console.print(f"  Session ID: [cyan]{session_dict.get('session_id', '-')}[/cyan]")
    console.print(f"  Workspace: {session_dict.get('workspace_id', '-')}")
    console.print(f"  Agent: {session_dict.get('agent_id', '-')}")


@app.command("list")
@async_command
async def list_sessions(
    workspace_id: Optional[str] = typer.Option(None, "--workspace", "-w", help="Filter by workspace"),
    agent_id: Optional[str] = typer.Option(None, "--agent", "-a", help="Filter by agent"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all sessions."""
    ctx = get_context()

    sessions = await ctx.proxy.list_sessions(
        workspace_id=workspace_id,
        agent_id=agent_id,
    )

    if json_output:
        sessions_list = [
            s.model_dump() if hasattr(s, "model_dump") else s.__dict__
            for s in sessions
        ]
        print_json({"sessions": sessions_list, "total": len(sessions)})
        return

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(title=f"Sessions ({len(sessions)} total)")
    table.add_column("Session ID", style="cyan")
    table.add_column("Workspace", style="green")
    table.add_column("Agent", style="blue")
    table.add_column("Status", style="magenta")
    table.add_column("Messages", style="yellow")
    table.add_column("Created", style="dim")

    for session in sessions:
        s_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__
        created = s_dict.get("created_at", "-")
        if hasattr(created, "strftime"):
            created = created.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            s_dict.get("session_id", "-")[:12] + "...",
            s_dict.get("workspace_id", "-"),
            s_dict.get("agent_id", "-")[:20],
            s_dict.get("status", "-"),
            str(len(s_dict.get("message_history", []))),
            str(created),
        )

    console.print(table)


@app.command("get")
@async_command
async def get_session(
    session_id: str = typer.Argument(..., help="Session ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Get session details."""
    ctx = get_context()

    session = await ctx.proxy.get_session(session_id)

    if not session:
        print_error(f"Session not found: {session_id}")
        raise typer.Exit(1)

    session_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__

    if json_output:
        print_json(session_dict)
        return

    console.print(f"\n[bold cyan]Session: {session_id}[/bold cyan]\n")

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Workspace", str(session_dict.get("workspace_id", "-")))
    info_table.add_row("Agent", str(session_dict.get("agent_id", "-")))
    info_table.add_row("Status", str(session_dict.get("status", "-")))

    created = session_dict.get("created_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    info_table.add_row("Created", str(created))

    updated = session_dict.get("updated_at")
    if hasattr(updated, "isoformat"):
        updated = updated.isoformat()
    info_table.add_row("Updated", str(updated))

    info_table.add_row("Messages", str(len(session_dict.get("message_history", []))))

    console.print(info_table)

    # Show message history summary
    messages = session_dict.get("message_history", [])
    if messages:
        console.print("\n[bold]Message History:[/bold]")
        msg_table = Table()
        msg_table.add_column("Role", style="cyan")
        msg_table.add_column("Content Preview", style="dim")

        for msg in messages[-5:]:  # Last 5 messages
            role = msg.get("role", "-")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = str(content)[:50]
            else:
                content = str(content)[:50]
            msg_table.add_row(role, content + "..." if len(str(msg.get("content", ""))) > 50 else content)

        console.print(msg_table)


@app.command("delete")
@async_command
async def delete_session(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
) -> None:
    """Delete a session."""
    ctx = get_context()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete session '{session_id}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    result = await ctx.proxy.delete_session(session_id)

    if result:
        print_success(f"Session '{session_id}' deleted successfully")
    else:
        print_error(f"Failed to delete session: {session_id}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

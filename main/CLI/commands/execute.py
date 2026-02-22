"""
Execute commands - Execute agents in sessions.

Commands:
    run         Execute a prompt in a session
    stream      Execute with streaming output
"""

from typing import Optional

import typer
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown

from CLI.core import async_command, get_context, console, print_json, print_error, print_success

app = typer.Typer(help="Agent execution commands")


@app.command("run")
@async_command
async def execute(
    session_id: str = typer.Argument(..., help="Session ID"),
    prompt: str = typer.Argument(..., help="Prompt to execute"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="JSON context data"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Execute a prompt in a session."""
    ctx = get_context()

    context_dict = {}
    if context:
        import json
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            print_error("Invalid JSON context")
            raise typer.Exit(1)

    console.print(f"\n[bold cyan]Executing in session: {session_id}[/bold cyan]")
    console.print(f"[dim]Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}[/dim]\n")

    result = await ctx.proxy.execute(
        session_id=session_id,
        prompt=prompt,
        context=context_dict,
    )

    result_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    if json_output:
        print_json(result_dict)
        return

    # Print result
    if result_dict.get("success"):
        console.print(Panel(
            Markdown(result_dict.get("output", "")),
            title="Response",
            style="green",
        ))
    else:
        print_error(result_dict.get("error", "Unknown error"))

    # Print stats
    console.print(f"\n[dim]Iterations: {result_dict.get('iterations', 0)} | Tool calls: {len(result_dict.get('tool_calls', []))}[/dim]")


@app.command("stream")
@async_command
async def execute_stream(
    session_id: str = typer.Argument(..., help="Session ID"),
    prompt: str = typer.Argument(..., help="Prompt to execute"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="JSON context data"),
) -> None:
    """Execute with streaming output."""
    ctx = get_context()

    context_dict = {}
    if context:
        import json
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            print_error("Invalid JSON context")
            raise typer.Exit(1)

    console.print(f"\n[bold cyan]Streaming in session: {session_id}[/bold cyan]")
    console.print(f"[dim]Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}[/dim]\n")

    output_text = ""
    tool_calls = []

    async for event in ctx.proxy.execute_stream(
        session_id=session_id,
        prompt=prompt,
        context=context_dict,
    ):
        event_type = event.get("type")

        if event_type == "stream":
            content = event.get("content", "")
            output_text += content
            console.print(content, end="")

        elif event_type == "tool_start":
            tool_name = event.get("tool_name", "unknown")
            tool_input = event.get("tool_input", {})
            console.print(f"\n[yellow]🔧 Tool: {tool_name}[/yellow]")
            tool_calls.append({"name": tool_name, "input": tool_input})

        elif event_type == "tool_result":
            result = event.get("result", "")
            console.print(f"[dim]{str(result)[:200]}{'...' if len(str(result)) > 200 else ''}[/dim]")

        elif event_type == "complete":
            console.print("\n\n[green]✓ Complete[/green]")

        elif event_type == "error":
            error_msg = event.get("error", "Unknown error")
            console.print(f"\n[red]Error: {error_msg}[/red]")

    console.print(f"\n[dim]Total tool calls: {len(tool_calls)}[/dim]")


@app.command("chat")
@async_command
async def chat(
    workspace_id: str = typer.Option(..., "--workspace", "-w", help="Workspace ID"),
    agent_id: str = typer.Option(..., "--agent", "-a", help="Agent ID"),
    prompt: str = typer.Argument(..., help="Prompt to execute"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="JSON context data"),
) -> None:
    """One-shot chat: creates session, executes, and cleans up."""
    ctx = get_context()

    context_dict = {}
    if context:
        import json
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            print_error("Invalid JSON context")
            raise typer.Exit(1)

    console.print(f"\n[bold cyan]Chat with agent: {agent_id}[/bold cyan]\n")

    # Create session
    session = await ctx.proxy.create_session(
        workspace_id=workspace_id,
        agent_id=agent_id,
        metadata={"type": "oneshot"},
    )
    session_id = session.session_id if hasattr(session, "session_id") else session.get("session_id")

    try:
        # Execute
        result = await ctx.proxy.execute(
            session_id=session_id,
            prompt=prompt,
            context=context_dict,
        )

        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

        if result_dict.get("success"):
            console.print(Panel(
                result_dict.get("output", ""),
                title="Response",
                style="green",
            ))
        else:
            print_error(result_dict.get("error", "Unknown error"))

    finally:
        # Cleanup
        await ctx.proxy.delete_session(session_id)


if __name__ == "__main__":
    app()

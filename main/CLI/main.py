"""
CLI Main Entry Point.

This is the main entry point for the Agent Learn CLI.

Usage:
    python -m CLI [OPTIONS] COMMAND [ARGS]...

    # Single command mode
    python -m CLI agent list
    python -m CLI workspace create dev --path /workspace

    # Interactive REPL mode
    python -m CLI repl

Commands:
    agent       Agent management commands
    workspace   Workspace management commands
    session     Session management commands
    execute     Execute agents
    plan        Plan management commands
    model       Model configuration commands
    repl        Interactive REPL mode
"""

import sys
from pathlib import Path

# Ensure parent directory is in path for imports
_cli_dir = Path(__file__).parent
_main_dir = _cli_dir.parent
if str(_main_dir) not in sys.path:
    sys.path.insert(0, str(_main_dir))

import typer
from typing import Optional

from CLI.commands.agent import app as agent_app
from CLI.commands.workspace import app as workspace_app
from CLI.commands.session import app as session_app
from CLI.commands.execute import app as execute_app
from CLI.commands.plan import app as plan_app
from CLI.commands.model import app as model_app

# Create main app
app = typer.Typer(
    name="cli",
    help="Agent Learn CLI - Command Line Interface for Agent Services",
    no_args_is_help=True,
    add_completion=False,
)

# Add sub-apps
app.add_typer(agent_app, name="agent")
app.add_typer(workspace_app, name="workspace", hidden=False)
app.add_typer(session_app, name="session")
app.add_typer(execute_app, name="execute")
app.add_typer(plan_app, name="plan")
app.add_typer(model_app, name="model")


@app.command("repl")
def repl_command():
    """Start interactive REPL mode."""
    import asyncio
    from CLI.commands.repl import run_repl
    asyncio.run(run_repl())


@app.command("version")
def version():
    """Show CLI version."""
    from CLI import __version__
    typer.echo(f"CLI version: {__version__}")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """
    Agent Learn CLI - Command Line Interface for Agent Services.
    """
    # Store global options in context
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config


if __name__ == "__main__":
    app()

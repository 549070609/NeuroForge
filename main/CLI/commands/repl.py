"""
REPL - Interactive mode for CLI.

Provides an interactive shell for managing services and executing commands.
Windows-compatible implementation without prompt_toolkit.
"""

import asyncio
import os
import shlex
from typing import Optional, Dict, Callable, Any

from CLI.core.context import CLIContext, get_context
from CLI.core.output import console, print_error, print_success


class ReplCommand:
    """REPL command handler - Windows compatible simple version."""

    def __init__(self, context: CLIContext):
        self.context = context
        self.running = True
        self.default_workspace_id = os.getenv("CLI_REPL_WORKSPACE_ID", "chat")
        self.default_workspace_path = os.getenv(
            "CLI_REPL_WORKSPACE_PATH", "./main/CLI/workspaces/chat"
        )
        self.default_agent_id = os.getenv("CLI_REPL_AGENT_ID", "mate-agent")
        self._default_chat_ready = False

        # Command registry
        self.commands: Dict[str, Callable] = {
            # Agent commands
            "agent": self._handle_agent,
            "agents": self._handle_agent,

            # Workspace commands
            "workspace": self._handle_workspace,
            "ws": self._handle_workspace,

            # Session commands
            "session": self._handle_session,

            # Execute commands
            "execute": self._handle_execute,
            "run": self._handle_execute,
            "chat": self._handle_chat,

            # Plan commands
            "plan": self._handle_plan,

            # Model commands
            "model": self._handle_model,

            # Utility commands
            "help": self._handle_help,
            "?": self._handle_help,
            "clear": self._handle_clear,
            "exit": self._handle_exit,
            "quit": self._handle_exit,
            "q": self._handle_exit,
        }

    async def run(self) -> None:
        """Run the REPL loop."""
        from rich.panel import Panel

        # Welcome message
        console.print(Panel.fit(
            "[bold cyan]Agent Learn CLI - Interactive Mode[/bold cyan]\n"
            "Type [green]help[/green] for available commands, [red]exit[/red] to quit.\n"
            "[dim]You can also type plain text directly to chat with the default agent.[/dim]",
            title="Welcome",
        ))

        while self.running:
            try:
                # Simple input (no prompt_toolkit)
                console.print()
                text = input(">>> ").strip()

                if not text:
                    continue

                # Execute command
                await self._execute_command(text)

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit.[/yellow]")
            except EOFError:
                break
            except Exception as e:
                print_error(f"Error: {e}")

        console.print("\n[green]Goodbye![/green]")

    async def _execute_command(self, text: str) -> None:
        """Execute a command string."""
        parts = text.strip().split(maxsplit=1)
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self.commands.get(cmd)
        if handler:
            await handler(args)
        else:
            await self._handle_plain_chat(text)

    async def _ensure_default_chat_workspace(self) -> bool:
        """Ensure default workspace exists for plain-text chat."""
        if self._default_chat_ready:
            return True

        try:
            existing = self.context.proxy.get_workspace(self.default_workspace_id)
            if not existing:
                self.context.proxy.create_workspace(
                    workspace_id=self.default_workspace_id,
                    root_path=self.default_workspace_path,
                )
            self._default_chat_ready = True
            return True
        except Exception as e:
            print_error(
                "Failed to prepare default chat workspace. "
                "Use 'workspace create <id> --path <path>' first. "
                f"Details: {e}"
            )
            return False

    async def _handle_plain_chat(self, text: str) -> None:
        """Treat unknown input as direct chat with the default agent."""
        if not text.strip():
            return

        ready = await self._ensure_default_chat_workspace()
        if not ready:
            return

        await self._handle_chat(
            f"--workspace {self.default_workspace_id} --agent {self.default_agent_id} {text}"
        )

    # =====================
    # Agent Commands
    # =====================

    async def _handle_agent(self, args: str) -> None:
        """Handle agent commands."""
        if not args:
            args = "list"

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._agent_list()
        elif subcmd == "get":
            await self._agent_get(subargs)
        elif subcmd == "stats":
            await self._agent_stats()
        elif subcmd == "refresh":
            self.context.agent.refresh()
            print_success("Agent cache refreshed")
        else:
            print_error(f"Unknown agent subcommand: {subcmd}")

    async def _agent_list(self) -> None:
        """List agents."""
        from rich.table import Table

        result = self.context.agent.list_agents()

        if not result.agents:
            console.print("[yellow]No agents found.[/yellow]")
            return

        table = Table(title=f"Agents ({result.total} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Namespace", style="blue")

        for agent in result.agents:
            a_dict = agent.model_dump() if hasattr(agent, "model_dump") else agent.__dict__
            table.add_row(
                str(a_dict.get("id", "-"))[:20],
                str(a_dict.get("name", "-"))[:25],
                str(a_dict.get("namespace", "-")),
            )

        console.print(table)

    async def _agent_get(self, agent_id: str) -> None:
        """Get agent details."""
        if not agent_id:
            print_error("Usage: agent get <agent_id>")
            return

        agent = self.context.agent.get_agent(agent_id)
        if not agent:
            print_error(f"Agent not found: {agent_id}")
            return

        a_dict = agent.model_dump() if hasattr(agent, "model_dump") else agent.__dict__
        console.print(f"\n[bold cyan]{a_dict.get('name', '-')}[/bold cyan]")
        console.print(f"ID: {a_dict.get('id', '-')}")
        console.print(f"Namespace: {a_dict.get('namespace', '-')}")
        console.print(f"Description: {a_dict.get('description', '-') or 'N/A'}")

    async def _agent_stats(self) -> None:
        """Show agent stats."""
        from rich.table import Table

        stats = self.context.agent.get_stats()
        s_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

        table = Table(show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Total Agents", str(s_dict.get("total_agents", 0)))
        table.add_row("Total Namespaces", str(s_dict.get("total_namespaces", 0)))
        console.print(table)

    # =====================
    # Workspace Commands
    # =====================

    async def _handle_workspace(self, args: str) -> None:
        """Handle workspace commands."""
        if not args:
            args = "list"

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._workspace_list()
        elif subcmd == "create":
            await self._workspace_create(subargs)
        elif subcmd == "get":
            await self._workspace_get(subargs)
        elif subcmd == "remove":
            await self._workspace_remove(subargs)
        else:
            print_error(f"Unknown workspace subcommand: {subcmd}")

    async def _workspace_list(self) -> None:
        """List workspaces."""
        from rich.table import Table

        workspace_ids = self.context.proxy.list_workspaces()

        if not workspace_ids:
            console.print("[yellow]No workspaces found.[/yellow]")
            return

        table = Table(title=f"Workspaces ({len(workspace_ids)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Path", style="green")

        for ws_id in workspace_ids:
            ws = self.context.proxy.get_workspace(ws_id)
            table.add_row(ws_id, ws.get("root_path", "-") if ws else "-")

        console.print(table)

    async def _workspace_create(self, args: str) -> None:
        """Create workspace."""
        import re
        match = re.match(r"(\S+)\s+--path\s+(\S+)", args)
        if not match:
            print_error("Usage: workspace create <id> --path <path>")
            return

        ws_id = match.group(1)
        path = match.group(2)

        result = self.context.proxy.create_workspace(
            workspace_id=ws_id,
            root_path=path,
        )
        print_success(f"Workspace '{ws_id}' created")

    async def _workspace_get(self, ws_id: str) -> None:
        """Get workspace details."""
        if not ws_id:
            print_error("Usage: workspace get <workspace_id>")
            return

        ws = self.context.proxy.get_workspace(ws_id)
        if not ws:
            print_error(f"Workspace not found: {ws_id}")
            return

        console.print(f"\n[bold cyan]Workspace: {ws_id}[/bold cyan]")
        console.print(f"Path: {ws.get('root_path', '-')}")
        console.print(f"Namespace: {ws.get('namespace', '-')}")
        console.print(f"Read-only: {ws.get('is_readonly', False)}")

    async def _workspace_remove(self, ws_id: str) -> None:
        """Remove workspace."""
        if not ws_id:
            print_error("Usage: workspace remove <workspace_id>")
            return

        result = await self.context.proxy.remove_workspace(ws_id)
        if result:
            print_success(f"Workspace '{ws_id}' removed")
        else:
            print_error("Failed to remove workspace")

    # =====================
    # Session Commands
    # =====================

    async def _handle_session(self, args: str) -> None:
        """Handle session commands."""
        if not args:
            args = "list"

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._session_list()
        elif subcmd == "create":
            await self._session_create(subargs)
        elif subcmd == "get":
            await self._session_get(subargs)
        elif subcmd == "delete":
            await self._session_delete(subargs)
        else:
            print_error(f"Unknown session subcommand: {subcmd}")

    async def _session_list(self) -> None:
        """List sessions."""
        from rich.table import Table

        sessions = await self.context.proxy.list_sessions()

        if not sessions:
            console.print("[yellow]No sessions found.[/yellow]")
            return

        table = Table(title=f"Sessions ({len(sessions)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Workspace", style="green")
        table.add_column("Agent", style="blue")
        table.add_column("Status", style="magenta")

        for session in sessions:
            s_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__
            table.add_row(
                str(s_dict.get("session_id", "-"))[:12],
                str(s_dict.get("workspace_id", "-")),
                str(s_dict.get("agent_id", "-"))[:20],
                str(s_dict.get("status", "-")),
            )

        console.print(table)

    async def _session_create(self, args: str) -> None:
        """Create session."""
        import re
        match = re.match(r"--workspace\s+(\S+)\s+--agent\s+(\S+)", args)
        if not match:
            print_error("Usage: session create --workspace <ws_id> --agent <agent_id>")
            return

        ws_id = match.group(1)
        agent_id = match.group(2)

        session = await self.context.proxy.create_session(
            workspace_id=ws_id,
            agent_id=agent_id,
        )
        s_id = session.session_id if hasattr(session, "session_id") else session.get("session_id")
        print_success(f"Session created: {s_id}")

    async def _session_get(self, session_id: str) -> None:
        """Get session details."""
        if not session_id:
            print_error("Usage: session get <session_id>")
            return

        session = await self.context.proxy.get_session(session_id)
        if not session:
            print_error(f"Session not found: {session_id}")
            return

        s_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__
        console.print(f"\n[bold cyan]Session: {session_id}[/bold cyan]")
        console.print(f"Workspace: {s_dict.get('workspace_id', '-')}")
        console.print(f"Agent: {s_dict.get('agent_id', '-')}")
        console.print(f"Status: {s_dict.get('status', '-')}")
        console.print(f"Messages: {len(s_dict.get('message_history', []))}")

    async def _session_delete(self, session_id: str) -> None:
        """Delete session."""
        if not session_id:
            print_error("Usage: session delete <session_id>")
            return

        result = await self.context.proxy.delete_session(session_id)
        if result:
            print_success("Session deleted")
        else:
            print_error("Failed to delete session")

    # =====================
    # Execute Commands
    # =====================

    async def _handle_execute(self, args: str) -> None:
        """Handle execute command."""
        from rich.panel import Panel
        import re

        match = re.match(r"(\S+)\s+(.+)", args, re.DOTALL)
        if not match:
            print_error("Usage: execute <session_id> <prompt>")
            return

        session_id = match.group(1)
        prompt = match.group(2)

        console.print(f"\n[bold cyan]Executing...[/bold cyan]\n")

        result = await self.context.proxy.execute(
            session_id=session_id,
            prompt=prompt,
        )

        r_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

        if r_dict.get("success"):
            console.print(Panel(
                r_dict.get("output", ""),
                title="Response",
                style="green",
            ))
        else:
            print_error(r_dict.get("error", "Unknown error"))

    async def _handle_chat(self, args: str) -> None:
        """Handle one-shot chat command."""
        from rich.panel import Panel
        import re

        match = re.match(r"--workspace\s+(\S+)\s+--agent\s+(\S+)\s+(.+)", args, re.DOTALL)
        if not match:
            print_error("Usage: chat --workspace <ws_id> --agent <agent_id> <prompt>")
            return

        ws_id = match.group(1)
        agent_id = match.group(2)
        prompt = match.group(3)

        console.print(f"\n[bold cyan]Chat with {agent_id}...[/bold cyan]\n")

        # Create temporary session
        session = await self.context.proxy.create_session(
            workspace_id=ws_id,
            agent_id=agent_id,
        )
        session_id = session.session_id if hasattr(session, "session_id") else session.get("session_id")

        try:
            result = await self.context.proxy.execute(
                session_id=session_id,
                prompt=prompt,
            )

            r_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

            if r_dict.get("success"):
                console.print(Panel(
                    r_dict.get("output", ""),
                    title="Response",
                    style="green",
                ))
            else:
                print_error(r_dict.get("error", "Unknown error"))

        finally:
            await self.context.proxy.delete_session(session_id)

    # =====================
    # Plan Commands
    # =====================

    async def _handle_plan(self, args: str) -> None:
        """Handle plan commands."""
        if not args:
            args = "list"

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._plan_list()
        elif subcmd == "get":
            await self._plan_get(subargs)
        elif subcmd == "stats":
            await self._plan_stats()
        else:
            print_error(f"Unknown plan subcommand: {subcmd}")

    async def _plan_list(self) -> None:
        """List plans."""
        from rich.table import Table

        result = self.context.agent.list_plans()
        r_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

        plans = r_dict.get("plans", [])
        if not plans:
            console.print("[yellow]No plans found.[/yellow]")
            return

        table = Table(title=f"Plans ({r_dict.get('total', 0)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Status", style="magenta")

        for plan in plans:
            p_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__
            table.add_row(
                str(p_dict.get("id", "-"))[:12],
                str(p_dict.get("title", "-"))[:30],
                str(p_dict.get("status", "-")),
            )

        console.print(table)

    async def _plan_get(self, plan_id: str) -> None:
        """Get plan details."""
        if not plan_id:
            print_error("Usage: plan get <plan_id>")
            return

        plan = self.context.agent.get_plan(plan_id)
        if not plan:
            print_error(f"Plan not found: {plan_id}")
            return

        p_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan.__dict__
        console.print(f"\n[bold cyan]{p_dict.get('title', '-')}[/bold cyan]")
        console.print(f"ID: {p_dict.get('id', '-')}")
        console.print(f"Status: {p_dict.get('status', '-')}")
        console.print(f"Objective: {p_dict.get('objective', '-')}")

        steps = p_dict.get("steps", [])
        if steps:
            console.print(f"\n[bold]Steps ({len(steps)}):[/bold]")
            for i, step in enumerate(steps, 1):
                s_dict = step.model_dump() if hasattr(step, "model_dump") else step.__dict__
                status = s_dict.get("status", "pending")
                marker = {"completed": "✓", "in_progress": "►", "pending": "○"}.get(status, "○")
                console.print(f"  {marker} {i}. {s_dict.get('title', '-')}")

    async def _plan_stats(self) -> None:
        """Show plan stats."""
        from rich.table import Table

        stats = self.context.agent.get_plan_stats()
        s_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

        table = Table(show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Total Plans", str(s_dict.get("total_plans", 0)))
        console.print(table)

    # =====================
    # Model Commands
    # =====================

    async def _handle_model(self, args: str) -> None:
        """Handle model commands."""
        if not args:
            args = "list"

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._model_list()
        elif subcmd == "get":
            await self._model_get(subargs)
        elif subcmd == "providers":
            await self._model_providers()
        elif subcmd == "stats":
            await self._model_stats()
        else:
            print_error(f"Unknown model subcommand: {subcmd}")

    async def _model_list(self) -> None:
        """List models."""
        from rich.table import Table

        models = self.context.model_config.list_models()

        if not models:
            console.print("[yellow]No models found.[/yellow]")
            return

        table = Table(title=f"Models ({len(models)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Provider", style="blue")

        for model in models[:20]:  # Limit output
            m_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__
            table.add_row(
                str(m_dict.get("id", "-"))[:20],
                str(m_dict.get("name", "-"))[:25],
                str(m_dict.get("provider", "-")),
            )

        console.print(table)
        if len(models) > 20:
            console.print(f"[dim]... and {len(models) - 20} more[/dim]")

    async def _model_get(self, model_id: str) -> None:
        """Get model details."""
        if not model_id:
            print_error("Usage: model get <model_id>")
            return

        model = self.context.model_config.get_model(model_id)
        if not model:
            print_error(f"Model not found: {model_id}")
            return

        m_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__
        console.print(f"\n[bold cyan]{m_dict.get('name', '-')}[/bold cyan]")
        console.print(f"ID: {m_dict.get('id', '-')}")
        console.print(f"Provider: {m_dict.get('provider', '-')}")
        console.print(f"Context Window: {m_dict.get('context_window', '-')}")
        console.print(f"Vision: {m_dict.get('supports_vision', False)}")
        console.print(f"Tools: {m_dict.get('supports_tools', False)}")

    async def _model_providers(self) -> None:
        """List Chinese LLM providers."""
        result = self.context.model_config.list_chinese_providers()
        r_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

        providers = r_dict.get("providers", [])
        if not providers:
            console.print("[yellow]No providers found.[/yellow]")
            return

        for provider in providers:
            p_dict = provider.model_dump() if hasattr(provider, "model_dump") else provider.__dict__
            console.print(f"[bold green]{p_dict.get('vendor_name', p_dict.get('vendor', '-'))}[/bold green]")
            console.print(f"  Default Model: {p_dict.get('default_model', '-')}")
            console.print()

    async def _model_stats(self) -> None:
        """Show model stats."""
        from rich.table import Table

        stats = self.context.model_config.get_stats()
        s_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

        table = Table(show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Total Models", str(s_dict.get("total_models", 0)))
        table.add_row("Built-in", str(s_dict.get("builtin_models", 0)))
        table.add_row("Custom", str(s_dict.get("custom_models", 0)))
        console.print(table)

    # =====================
    # Utility Commands
    # =====================

    async def _handle_help(self, args: str) -> None:
        """Show help."""
        help_text = """
[bold cyan]Available Commands:[/bold cyan]

[bold green]Agent:[/bold green]
  agent list              List all agents
  agent get <id>          Get agent details
  agent stats             Show agent statistics
  agent refresh           Refresh agent cache

[bold green]Workspace:[/bold green]
  workspace list          List workspaces
  workspace create <id> --path <path>   Create workspace
  workspace get <id>      Get workspace details
  workspace remove <id>   Remove workspace

[bold green]Session:[/bold green]
  session list            List sessions
  session create --workspace <ws> --agent <agent>   Create session
  session get <id>        Get session details
  session delete <id>     Delete session

[bold green]Execute:[/bold green]
  execute <session_id> <prompt>    Execute in session
  chat --workspace <ws> --agent <agent> <prompt>   One-shot chat

[bold green]Plan:[/bold green]
  plan list               List plans
  plan get <id>           Get plan details
  plan stats              Show plan statistics

[bold green]Model:[/bold green]
  model list              List models
  model get <id>          Get model details
  model providers         List Chinese LLM providers
  model stats             Show model statistics

[bold green]Utility:[/bold green]
  help, ?                 Show this help
  clear                   Clear screen
  exit, quit, q           Exit REPL

[bold green]Direct Chat:[/bold green]
  Any non-command text    Chat directly (workspace: chat, agent: mate-agent)
"""
        console.print(help_text)

    async def _handle_clear(self, args: str) -> None:
        """Clear screen."""
        import os
        os.system("cls" if os.name == "nt" else "clear")

    async def _handle_exit(self, args: str) -> None:
        """Exit REPL."""
        self.running = False


async def run_repl() -> None:
    """Run the REPL with proper lifecycle management."""
    ctx = get_context()

    try:
        await ctx.initialize()

        repl = ReplCommand(ctx)
        await repl.run()

    finally:
        await ctx.shutdown()

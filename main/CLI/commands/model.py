"""
Model commands - Manage model configurations.

Commands:
    list        List all models
    get         Get model details
    create      Create a custom model
    update      Update a model
    delete      Delete a custom model
    stats       Show model statistics
    providers   List Chinese LLM providers
"""

from typing import Optional

import typer
from rich.table import Table

from CLI.core import async_command, get_context, console, print_json, print_error, print_success

app = typer.Typer(help="Model configuration commands")


@app.command("list")
@async_command
async def list_models(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    vision: Optional[bool] = typer.Option(None, "--vision", help="Filter by vision support"),
    tools: Optional[bool] = typer.Option(None, "--tools", help="Filter by tools support"),
    builtin: Optional[bool] = typer.Option(None, "--builtin", help="Filter built-in/custom"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List all model configurations."""
    ctx = get_context()

    models = ctx.model_config.list_models(
        provider=provider,
        supports_vision=vision,
        supports_tools=tools,
        is_builtin=builtin,
    )

    if json_output:
        models_list = [
            m.model_dump() if hasattr(m, "model_dump") else m.__dict__
            for m in models
        ]
        print_json({"models": models_list, "total": len(models)})
        return

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return

    table = Table(title=f"Models ({len(models)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Provider", style="blue")
    table.add_column("Vision", style="magenta")
    table.add_column("Tools", style="yellow")
    table.add_column("Context", style="dim")

    for model in models:
        m_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__
        table.add_row(
            str(m_dict.get("id", "-"))[:20],
            str(m_dict.get("name", "-"))[:25],
            str(m_dict.get("provider", "-")),
            "✓" if m_dict.get("supports_vision") else "✗",
            "✓" if m_dict.get("supports_tools") else "✗",
            str(m_dict.get("context_window", "-")),
        )

    console.print(table)


@app.command("get")
@async_command
async def get_model(
    model_id: str = typer.Argument(..., help="Model ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Get model details."""
    ctx = get_context()

    model = ctx.model_config.get_model(model_id)

    if not model:
        print_error(f"Model not found: {model_id}")
        raise typer.Exit(1)

    model_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__

    if json_output:
        print_json(model_dict)
        return

    console.print(f"\n[bold cyan]Model: {model_dict.get('name', '-')}[/bold cyan]")
    console.print(f"[dim]ID: {model_dict.get('id', '-')}[/dim]\n")

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Provider", str(model_dict.get("provider", "-")))
    info_table.add_row("API Type", str(model_dict.get("api_type", "-")))
    info_table.add_row("Built-in", str(model_dict.get("is_builtin", False)))
    info_table.add_row("Vision Support", str(model_dict.get("supports_vision", False)))
    info_table.add_row("Tools Support", str(model_dict.get("supports_tools", False)))
    info_table.add_row("Streaming", str(model_dict.get("supports_streaming", True)))
    info_table.add_row("Context Window", str(model_dict.get("context_window", "-")))
    info_table.add_row("Max Output", str(model_dict.get("max_output_tokens", "-")))

    # Pricing info
    cost_input = model_dict.get("cost_input")
    cost_output = model_dict.get("cost_output")
    if cost_input or cost_output:
        info_table.add_row("Cost (Input)", f"${cost_input}/1K tokens" if cost_input else "-")
        info_table.add_row("Cost (Output)", f"${cost_output}/1K tokens" if cost_output else "-")

    # Cache pricing
    cache_read = model_dict.get("cost_cache_read")
    cache_write = model_dict.get("cost_cache_write")
    if cache_read or cache_write:
        info_table.add_row("Cache Read", f"${cache_read}/1K tokens" if cache_read else "-")
        info_table.add_row("Cache Write", f"${cache_write}/1K tokens" if cache_write else "-")

    console.print(info_table)


@app.command("create")
@async_command
async def create_model(
    model_id: str = typer.Option(..., "--id", help="Model ID"),
    name: str = typer.Option(..., "--name", "-n", help="Model name"),
    provider: str = typer.Option(..., "--provider", "-p", help="Provider name"),
    api_type: str = typer.Option("openai", "--api-type", help="API type (openai/anthropic)"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Base URL"),
    api_key_env: Optional[str] = typer.Option(None, "--api-key-env", help="API key environment variable"),
    context_window: int = typer.Option(4096, "--context", help="Context window size"),
    max_output: int = typer.Option(2048, "--max-output", help="Max output tokens"),
    vision: bool = typer.Option(False, "--vision", help="Supports vision"),
    tools: bool = typer.Option(False, "--tools", help="Supports tools"),
    streaming: bool = typer.Option(True, "--streaming", help="Supports streaming"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Create a custom model configuration."""
    ctx = get_context()

    from Service.schemas.models import ModelConfigCreate

    request = ModelConfigCreate(
        id=model_id,
        name=name,
        provider=provider,
        api_type=api_type,
        base_url=base_url,
        api_key_env=api_key_env,
        context_window=context_window,
        max_output_tokens=max_output,
        supports_vision=vision,
        supports_tools=tools,
        supports_streaming=streaming,
    )

    try:
        model = ctx.model_config.create_model(request)
        model_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__

        if json_output:
            print_json(model_dict)
            return

        print_success(f"Model '{model_id}' created successfully")
        console.print(f"  Name: {model_dict.get('name', '-')}")
        console.print(f"  Provider: {model_dict.get('provider', '-')}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("update")
@async_command
async def update_model(
    model_id: str = typer.Argument(..., help="Model ID to update"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Model name"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Base URL"),
    context_window: Optional[int] = typer.Option(None, "--context", help="Context window size"),
    max_output: Optional[int] = typer.Option(None, "--max-output", help="Max output tokens"),
    vision: Optional[bool] = typer.Option(None, "--vision", help="Supports vision"),
    tools: Optional[bool] = typer.Option(None, "--tools", help="Supports tools"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Update a model configuration."""
    ctx = get_context()

    from Service.schemas.models import ModelConfigUpdate

    request = ModelConfigUpdate(
        name=name,
        base_url=base_url,
        context_window=context_window,
        max_output_tokens=max_output,
        supports_vision=vision,
        supports_tools=tools,
    )

    # Filter out None values
    request = ModelConfigUpdate(**{k: v for k, v in request.model_dump().items() if v is not None})

    try:
        model = ctx.model_config.update_model(model_id, request)
        model_dict = model.model_dump() if hasattr(model, "model_dump") else model.__dict__

        if json_output:
            print_json(model_dict)
            return

        print_success(f"Model '{model_id}' updated successfully")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("delete")
@async_command
async def delete_model(
    model_id: str = typer.Argument(..., help="Model ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
) -> None:
    """Delete a custom model configuration."""
    ctx = get_context()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete model '{model_id}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        result = ctx.model_config.delete_model(model_id)

        if result:
            print_success(f"Model '{model_id}' deleted successfully")
        else:
            print_error(f"Failed to delete model: {model_id}")
            raise typer.Exit(1)

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("stats")
@async_command
async def model_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show model statistics."""
    ctx = get_context()

    stats = ctx.model_config.get_stats()
    stats_dict = stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__

    if json_output:
        print_json(stats_dict)
        return

    console.print("\n[bold cyan]Model Statistics[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Total Models", str(stats_dict.get("total_models", 0)))
    table.add_row("Built-in Models", str(stats_dict.get("builtin_models", 0)))
    table.add_row("Custom Models", str(stats_dict.get("custom_models", 0)))

    console.print(table)

    # By provider breakdown
    by_provider = stats_dict.get("by_provider", {})
    if by_provider:
        console.print("\n[bold]By Provider:[/bold]")
        provider_table = Table(show_header=False, box=None)
        provider_table.add_column("Provider", style="blue")
        provider_table.add_column("Count", style="cyan")
        for provider_name, count in by_provider.items():
            provider_table.add_row(str(provider_name), str(count))
        console.print(provider_table)


@app.command("providers")
@async_command
async def list_providers(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List Chinese LLM providers."""
    ctx = get_context()

    result = ctx.model_config.list_chinese_providers()
    result_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    if json_output:
        print_json(result_dict)
        return

    providers = result_dict.get("providers", [])
    if not providers:
        console.print("[yellow]No Chinese LLM providers found.[/yellow]")
        return

    console.print(f"\n[bold cyan]Chinese LLM Providers ({len(providers)} total)[/bold cyan]\n")

    for provider in providers:
        p_dict = provider.model_dump() if hasattr(provider, "model_dump") else provider
        console.print(f"[bold green]{p_dict.get('vendor_name', p_dict.get('vendor', '-'))}[/bold green]")
        console.print(f"  Vendor: {p_dict.get('vendor', '-')}")
        console.print(f"  Default Model: {p_dict.get('default_model', '-')}")
        console.print(f"  API Key Env: {p_dict.get('api_key_env', '-')}")
        console.print(f"  Base URL: {p_dict.get('base_url', '-')}")
        models = p_dict.get("models", [])
        if models:
            console.print(f"  Models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
        console.print()


if __name__ == "__main__":
    app()

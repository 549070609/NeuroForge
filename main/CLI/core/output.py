"""
Output formatting utilities for CLI.

Uses Rich library for beautiful terminal output.
"""

import json
from typing import Any, Optional, Sequence

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint

# Global console instance
console = Console()


def print_table(
    title: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    show_header: bool = True,
    show_lines: bool = False,
    box_style: Optional[str] = None,
) -> None:
    """
    Print a formatted table.

    Args:
        title: Table title
        columns: Column headers
        rows: Table data rows
        show_header: Whether to show column headers
        show_lines: Whether to show row separator lines
        box_style: Box style (e.g., "rounded", "simple", "none")
    """
    table = Table(
        title=title,
        show_header=show_header,
        show_lines=show_lines,
    )

    if box_style:
        from rich.box import get_box
        table.box = get_box(box_style)

    for col in columns:
        table.add_column(col)

    for row in rows:
        table.add_row(*[str(cell) if cell is not None else "-" for cell in row])

    console.print(table)


def print_json(
    data: Any,
    *,
    title: Optional[str] = None,
    indent: int = 2,
) -> None:
    """
    Print formatted JSON output.

    Args:
        data: Data to print as JSON
        title: Optional title for the output
        indent: JSON indentation level
    """
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    if isinstance(data, str):
        # Already a JSON string
        try:
            parsed = json.loads(data)
            json_str = json.dumps(parsed, indent=indent, ensure_ascii=False)
        except json.JSONDecodeError:
            json_str = data
    else:
        # Convert to JSON
        json_str = json.dumps(data, indent=indent, ensure_ascii=False, default=str)

    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)


def print_error(message: str, *, title: str = "Error") -> None:
    """
    Print an error message.

    Args:
        message: Error message
        title: Error title
    """
    console.print(Panel(message, title=title, style="red"))


def print_success(message: str, *, title: str = "Success") -> None:
    """
    Print a success message.

    Args:
        message: Success message
        title: Success title
    """
    console.print(Panel(message, title=title, style="green"))


def print_info(message: str, *, title: Optional[str] = None) -> None:
    """
    Print an info message.

    Args:
        message: Info message
        title: Optional title
    """
    if title:
        console.print(Panel(message, title=title, style="blue"))
    else:
        console.print(f"[blue]{message}[/blue]")


def print_warning(message: str, *, title: str = "Warning") -> None:
    """
    Print a warning message.

    Args:
        message: Warning message
        title: Warning title
    """
    console.print(Panel(message, title=title, style="yellow"))


def print_header(title: str) -> None:
    """
    Print a section header.

    Args:
        title: Header title
    """
    console.print(f"\n[bold cyan]{'=' * 10} {title} {'=' * 10}[/bold cyan]\n")


def print_key_value(
    data: dict[str, Any],
    *,
    key_style: str = "bold",
    value_style: str = "white",
) -> None:
    """
    Print key-value pairs.

    Args:
        data: Dictionary to print
        key_style: Style for keys
        value_style: Style for values
    """
    for key, value in data.items():
        console.print(f"[{key_style}]{key}:[/{key_style}] [{value_style}]{value}[/{value_style}]")


def format_datetime(dt: Any) -> str:
    """Format a datetime object for display."""
    if dt is None:
        return "-"
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def truncate_string(s: str, max_length: int = 50) -> str:
    """Truncate a string if it exceeds max_length."""
    if len(s) <= max_length:
        return s
    return s[: max_length - 3] + "..."

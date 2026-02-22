"""
Quick launcher for Agent Learn CLI interactive chat.

Usage:
    python main/CLI/start_cli_chat.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _prepare_environment() -> None:
    """Prepare import path and working directory for stable CLI startup."""
    cli_dir = Path(__file__).resolve().parent
    main_dir = cli_dir.parent
    engine_dir = main_dir / "agentforge-engine"
    repo_root = main_dir.parent

    for path in (engine_dir, main_dir):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    os.environ.setdefault("LLM_CONFIG_PATH", str(main_dir / "llm_config.json"))

    # Service defaults use relative paths like "main/Agent" and "data/...".
    os.chdir(repo_root)


def main() -> int:
    """Start interactive REPL chat."""
    _prepare_environment()

    from CLI.commands.repl import run_repl

    try:
        asyncio.run(run_repl())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

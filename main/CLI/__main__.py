"""
CLI Module Entry Point.

Allows running CLI as: python -m CLI
"""

import sys
from pathlib import Path

# Ensure parent directory is in path for imports
_cli_dir = Path(__file__).parent
_main_dir = _cli_dir.parent
if str(_main_dir) not in sys.path:
    sys.path.insert(0, str(_main_dir))

from CLI.main import app

if __name__ == "__main__":
    app()

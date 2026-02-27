"""
NeuroForge Demo — One-click launcher

Starts both the backend (FastAPI/uvicorn :8080) and frontend (Vite :5173)
with a single command.  Press Ctrl+C to stop everything.

Usage:
    python start.py              # start both
    python start.py --install    # install dependencies first, then start
    python start.py --backend    # backend only
    python start.py --frontend   # frontend only
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# ANSI colors (Windows 10+ supports them with VT mode)
C_RESET = "\033[0m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_DIM = "\033[2m"


def _banner() -> None:
    print(f"""
{C_CYAN}╔══════════════════════════════════════════════╗
║       NeuroForge Agent Demo  Launcher        ║
╚══════════════════════════════════════════════╝{C_RESET}
""")


def _log(tag: str, msg: str, color: str = C_GREEN) -> None:
    print(f"  {color}[{tag}]{C_RESET} {msg}")


def _check_prerequisites() -> None:
    """Verify that python and npm/node are available."""
    if not (BACKEND_DIR / "app.py").exists():
        sys.exit(f"{C_RED}Error: backend/app.py not found. Run from test/ directory.{C_RESET}")
    if not (FRONTEND_DIR / "package.json").exists():
        sys.exit(f"{C_RED}Error: frontend/package.json not found.{C_RESET}")


def _install_backend() -> None:
    _log("pip", "Installing backend dependencies...")
    req = BACKEND_DIR / "requirements.txt"
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
        cwd=str(BACKEND_DIR),
    )
    _log("pip", "Backend dependencies ready.")


def _install_frontend() -> None:
    _log("npm", "Installing frontend dependencies...")
    subprocess.check_call(["npm", "install"], cwd=str(FRONTEND_DIR), shell=True)
    _log("npm", "Frontend dependencies ready.")


def _has_node_modules() -> bool:
    return (FRONTEND_DIR / "node_modules").is_dir()


def main() -> None:
    parser = argparse.ArgumentParser(description="NeuroForge Demo Launcher")
    parser.add_argument("--install", action="store_true", help="Install dependencies before starting")
    parser.add_argument("--backend", action="store_true", help="Start backend only")
    parser.add_argument("--frontend", action="store_true", help="Start frontend only")
    args = parser.parse_args()

    # Default: start both
    start_backend = not args.frontend or args.backend
    start_frontend = not args.backend or args.frontend
    if not args.backend and not args.frontend:
        start_backend = start_frontend = True

    os.system("")  # enable ANSI on Windows
    _banner()
    _check_prerequisites()

    if args.install:
        if start_backend:
            _install_backend()
        if start_frontend:
            _install_frontend()
    elif start_frontend and not _has_node_modules():
        _log("npm", "node_modules not found, running npm install...", C_YELLOW)
        _install_frontend()

    procs: list[subprocess.Popen] = []

    def _shutdown(*_: object) -> None:
        print(f"\n  {C_YELLOW}[stop]{C_RESET} Shutting down...")
        for p in procs:
            try:
                p.terminate()
            except OSError:
                pass
        deadline = time.monotonic() + 5
        for p in procs:
            remaining = max(0, deadline - time.monotonic())
            try:
                p.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                p.kill()
        print(f"  {C_GREEN}[done]{C_RESET} All processes stopped.\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        if start_backend:
            _log("backend", f"Starting uvicorn on http://localhost:8080 ...", C_CYAN)
            backend_proc = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "app:app",
                    "--host", "0.0.0.0",
                    "--port", "8080",
                    "--reload",
                    "--log-level", "info",
                ],
                cwd=str(BACKEND_DIR),
            )
            procs.append(backend_proc)

        if start_frontend:
            _log("frontend", f"Starting Vite dev server on http://localhost:5173 ...", C_CYAN)
            frontend_proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(FRONTEND_DIR),
                shell=True,
            )
            procs.append(frontend_proc)

        if start_backend and start_frontend:
            print(f"""
  {C_GREEN}✓ Both servers starting up.{C_RESET}
  {C_DIM}─────────────────────────────────────────{C_RESET}
    Backend  →  {C_CYAN}http://localhost:8080{C_RESET}
    Frontend →  {C_CYAN}http://localhost:5173{C_RESET}
  {C_DIM}─────────────────────────────────────────{C_RESET}
    Open the frontend URL in your browser.
    Press {C_YELLOW}Ctrl+C{C_RESET} to stop all services.
""")

        # Wait for any process to exit
        while True:
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    name = "backend" if p is procs[0] and start_backend else "frontend"
                    _log(name, f"Process exited with code {ret}", C_RED if ret else C_GREEN)
                    _shutdown()
            time.sleep(0.5)

    except Exception as exc:
        _log("error", str(exc), C_RED)
        _shutdown()


if __name__ == "__main__":
    main()

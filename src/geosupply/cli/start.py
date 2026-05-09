"""
GeoSupply AI — Central Service Launcher

Starts all GeoSupply services in one command with a live Rich TUI showing
health, URLs, and tailed logs for each process.

Usage:
    geosupply-start                     # Start everything (default)
    geosupply-start --no-dashboard      # Skip admin dashboard
    geosupply-start --no-playground     # Skip playground UI
    geosupply-start --with-mcp          # Also start MCP server (stdio — logs only)
    geosupply-start --api-port 9000     # Custom API port
    geosupply-start --only api          # Start only the API
    geosupply-start --check             # Check port/env status without starting
    geosupply-start --stop              # Send SIGTERM to all GeoSupply processes

Services managed:
    geosupply-api       → http://localhost:8000  (FastAPI + Uvicorn)
    geosupply-dashboard → http://localhost:8501  (Streamlit Admin)
    geosupply-playground→ http://localhost:8502  (Streamlit Playground)
    geosupply-mcp       → stdio only (optional)
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque

# ── Rich ──────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False

console = Console() if _RICH else None
IS_WINDOWS = platform.system() == "Windows"
PYTHON = sys.executable

# ── Service definitions ───────────────────────────────────────────────────────

@dataclass
class ServiceDef:
    key: str
    label: str
    cmd_fn: "callable"          # called at launch to build the command list
    port: int | None            # None = no HTTP port (MCP)
    url_path: str = ""
    color: str = "cyan"
    log_lines: Deque[str] = field(default_factory=lambda: deque(maxlen=120))
    process: "subprocess.Popen | None" = None
    started_at: float = 0.0
    exit_code: int | None = None

    @property
    def url(self) -> str:
        if self.port:
            return f"http://localhost:{self.port}{self.url_path}"
        return "stdio"

    @property
    def status(self) -> str:
        if self.process is None:
            return "idle"
        if self.process.poll() is None:
            return "running"
        return "stopped"

    @property
    def uptime(self) -> str:
        if self.started_at == 0:
            return "—"
        secs = int(time.time() - self.started_at)
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"


def _make_services(api_port: int, dash_port: int, play_port: int, with_mcp: bool) -> list[ServiceDef]:
    services = [
        ServiceDef(
            key="api",
            label="API Server",
            cmd_fn=lambda: [
                PYTHON, "-m", "uvicorn",
                "geosupply.api.main:app",
                "--host", "0.0.0.0",
                "--port", str(api_port),
                "--log-level", "info",
            ],
            port=api_port,
            url_path="/docs",
            color="green",
        ),
        ServiceDef(
            key="dashboard",
            label="Admin Dashboard",
            cmd_fn=lambda: [
                PYTHON, "-m", "streamlit", "run",
                str(_dashboard_path()),
                "--server.port", str(dash_port),
                "--server.headless", "true",
                "--logger.level", "warning",
            ],
            port=dash_port,
            color="blue",
        ),
        ServiceDef(
            key="playground",
            label="Playground",
            cmd_fn=lambda: [
                PYTHON, "-m", "streamlit", "run",
                str(_playground_path()),
                "--server.port", str(play_port),
                "--server.headless", "true",
                "--logger.level", "warning",
            ],
            port=play_port,
            color="magenta",
        ),
    ]
    if with_mcp:
        services.append(ServiceDef(
            key="mcp",
            label="MCP Server",
            cmd_fn=lambda: [PYTHON, "-m", "geosupply.mcp.server"],
            port=None,
            color="yellow",
        ))
    return services


def _dashboard_path() -> Path:
    return Path(__file__).resolve().parent.parent / "dashboard" / "admin_dashboard.py"


def _playground_path() -> Path:
    return Path(__file__).resolve().parent.parent / "dashboard" / "playground.py"


# ── Port / env checks ─────────────────────────────────────────────────────────

def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _env_status() -> list[tuple[str, bool, str]]:
    checks = [
        ("ANTHROPIC_API_KEY",      bool(os.getenv("ANTHROPIC_API_KEY")),      "Tier-2/3 LLM inference"),
        ("ADMIN_API_KEY",          bool(os.getenv("ADMIN_API_KEY")),           "Admin API auth (defaults to 'dev-key')"),
        ("SQLITE_PATH",            True,                                        "SQLite (auto-created)"),
        ("SUPABASE_URL",           bool(os.getenv("SUPABASE_URL")),            "Task persistence (optional)"),
        ("NEO4J_URI",              bool(os.getenv("NEO4J_URI")),               "Knowledge graph (optional)"),
        ("NEWS_API_KEY",           bool(os.getenv("NEWS_API_KEY")),            "News ingestion (optional)"),
    ]
    return checks


# ── Process log reader (background thread) ────────────────────────────────────

def _tail_process(service: ServiceDef) -> None:
    """Background thread: read stdout+stderr from the process into log_lines."""
    proc = service.process
    if proc is None or proc.stdout is None:
        return
    try:
        for raw in proc.stdout:
            line = raw.rstrip() if isinstance(raw, str) else raw.decode("utf-8", errors="replace").rstrip()
            if line:
                ts = datetime.now().strftime("%H:%M:%S")
                service.log_lines.append(f"[dim]{ts}[/dim] {line}")
    except Exception:
        pass


# ── Pre-flight check display ───────────────────────────────────────────────────

def run_check(services: list[ServiceDef]) -> None:
    if not console:
        print("rich not installed — run: pip install rich")
        return

    console.rule("[bold cyan]GeoSupply — Pre-flight Check[/]")

    # Port status
    t = Table("Port", "Service", "Status", box=box.SIMPLE_HEAD)
    for svc in services:
        if svc.port:
            free = _port_free(svc.port)
            t.add_row(
                str(svc.port),
                svc.label,
                "[green]free[/]" if free else "[red]IN USE[/]",
            )
    console.print(Panel(t, title="[bold]Ports[/]"))

    # Env vars
    t2 = Table("Variable", "Set", "Used for", box=box.SIMPLE_HEAD)
    for name, ok, desc in _env_status():
        t2.add_row(name, "[green]✓[/]" if ok else "[yellow]—[/]", desc)
    console.print(Panel(t2, title="[bold]Environment Variables[/]"))

    # Dependency check
    t3 = Table("Dependency", "Available", box=box.SIMPLE_HEAD)
    for pkg, cmd in [("uvicorn", "uvicorn"), ("streamlit", "streamlit"),
                     ("httpx", None), ("rich", None), ("anthropic", None)]:
        if cmd:
            found = shutil.which(cmd) is not None
        else:
            try:
                __import__(pkg)
                found = True
            except ImportError:
                found = False
        t3.add_row(pkg, "[green]✓[/]" if found else "[red]missing[/]")
    console.print(Panel(t3, title="[bold]Dependencies[/]"))


# ── Rich TUI ──────────────────────────────────────────────────────────────────

STATUS_ICON = {"idle": "⚪", "running": "🟢", "stopped": "🔴"}
STATUS_COLOR = {"idle": "dim", "running": "green", "stopped": "red"}

_ACTIVE_LOG_KEY = "api"  # which service's logs are shown in the big pane


def _build_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="body",    ratio=1),
        Layout(name="footer",  size=3),
    )
    layout["body"].split_row(
        Layout(name="services", size=44),
        Layout(name="logs",     ratio=1),
    )
    return layout


def _render_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    return Panel(
        f"[bold cyan]GeoSupply AI — Service Launcher[/]   [dim]{now}[/]",
        style="bold",
    )


def _render_services(services: list[ServiceDef], selected_key: str) -> Panel:
    t = Table(
        "Service", "Status", "Uptime", "URL",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        expand=True,
    )
    for svc in services:
        status = svc.status
        icon = STATUS_ICON[status]
        color = STATUS_COLOR[status] if status != "running" else svc.color
        sel = "▶ " if svc.key == selected_key else "  "
        t.add_row(
            f"[{color}]{sel}{svc.label}[/]",
            f"[{color}]{icon} {status}[/]",
            svc.uptime,
            f"[link={svc.url}]{svc.url}[/link]" if svc.port else "[dim]stdio[/dim]",
        )
    return Panel(t, title="[bold]Services[/]", border_style="cyan")


def _render_logs(services: list[ServiceDef], selected_key: str, height: int = 30) -> Panel:
    svc = next((s for s in services if s.key == selected_key), services[0])
    lines = list(svc.log_lines)[-height:]
    content = "\n".join(lines) if lines else "[dim]No output yet…[/dim]"
    return Panel(
        content,
        title=f"[bold]{svc.label} — Logs[/]  [dim](Tab to switch)[/dim]",
        border_style=svc.color,
    )


def _render_footer(services: list[ServiceDef]) -> Panel:
    running = sum(1 for s in services if s.status == "running")
    keys = "  [bold]Tab[/] cycle logs  [bold]Ctrl+C[/] stop all"
    return Panel(
        f"[green]{running}/{len(services)} services running[/]  {keys}",
        style="dim",
    )


# ── Main launcher ─────────────────────────────────────────────────────────────

def _launch(svc: ServiceDef, env: dict) -> None:
    cmd = svc.cmd_fn()
    svc.log_lines.append(f"[dim]$ {' '.join(cmd)}[/dim]")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
    )
    svc.process = proc
    svc.started_at = time.time()
    t = threading.Thread(target=_tail_process, args=(svc,), daemon=True)
    t.start()


def _stop_all(services: list[ServiceDef]) -> None:
    for svc in services:
        if svc.process and svc.process.poll() is None:
            if IS_WINDOWS:
                svc.process.terminate()
            else:
                svc.process.send_signal(signal.SIGTERM)
    # Give them 3 seconds then kill
    deadline = time.time() + 3.0
    for svc in services:
        if svc.process and svc.process.poll() is None:
            remaining = max(0.0, deadline - time.time())
            try:
                svc.process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                svc.process.kill()


def run_launcher(services: list[ServiceDef], env: dict) -> None:
    """Launch all services and run the Rich TUI until Ctrl+C."""

    # Pre-flight: warn about occupied ports
    occupied = [s for s in services if s.port and not _port_free(s.port)]
    if occupied and console:
        for s in occupied:
            console.print(f"[yellow]⚠ Port {s.port} already in use — {s.label} may fail[/]")
        time.sleep(1.0)

    # Start all services
    for svc in services:
        _launch(svc, env)
        time.sleep(0.4)   # stagger to avoid thundering herd on SQLite

    if not _RICH:
        # Fallback: no TUI — just wait for Ctrl+C
        if console is None:
            print("Services started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            _stop_all(services)
        return

    selected_idx = 0
    layout = _build_layout()

    def _cycle_log() -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx + 1) % len(services)

    # On Windows we can't use signal in non-main thread; use a flag instead
    _stop_flag = threading.Event()

    def _sigint_handler(sig, frame) -> None:
        _stop_flag.set()

    signal.signal(signal.SIGINT, _sigint_handler)

    with Live(layout, refresh_per_second=2, screen=True) as live:
        try:
            while not _stop_flag.is_set():
                selected_key = services[selected_idx].key

                layout["header"].update(_render_header())
                layout["services"].update(_render_services(services, selected_key))
                layout["logs"].update(_render_logs(services, selected_key))
                layout["footer"].update(_render_footer(services))

                # Non-blocking keyboard input for Tab (best-effort on all platforms)
                time.sleep(0.5)

        except KeyboardInterrupt:
            pass

    console.print("\n[bold yellow]Stopping all services…[/]")
    _stop_all(services)
    console.print("[bold green]All services stopped. Goodbye.[/]")


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="geosupply-start",
        description="GeoSupply AI — Central Service Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--api-port",   type=int, default=int(os.getenv("PORT", "8000")))
    p.add_argument("--dash-port",  type=int, default=int(os.getenv("DASHBOARD_PORT", "8501")))
    p.add_argument("--play-port",  type=int, default=int(os.getenv("PLAYGROUND_PORT", "8502")))
    p.add_argument("--no-dashboard",  action="store_true", help="Skip Admin Dashboard")
    p.add_argument("--no-playground", action="store_true", help="Skip Playground UI")
    p.add_argument("--with-mcp",      action="store_true", help="Also start MCP server")
    p.add_argument("--only",  metavar="KEY",
                   help="Start only this service key (api|dashboard|playground|mcp)")
    p.add_argument("--check", action="store_true",
                   help="Run pre-flight checks only, do not start services")
    p.add_argument("--env-file", default=".env",
                   help="Path to .env file (default: .env in CWD)")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Load .env if present
    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
            if console:
                console.print(f"[dim]Loaded env from {env_file}[/]")
        except ImportError:
            pass  # python-dotenv not installed — silently skip

    # Build env dict for subprocesses
    proc_env = {**os.environ}
    proc_env.setdefault("GEOSUPPLY_API_URL", f"http://localhost:{args.api_port}")
    proc_env.setdefault("ADMIN_API_KEY", "@Shitguy27")

    # Build service list
    all_services = _make_services(
        api_port=args.api_port,
        dash_port=args.dash_port,
        play_port=args.play_port,
        with_mcp=args.with_mcp,
    )

    # Filter by --only or --no-* flags
    if args.only:
        services = [s for s in all_services if s.key == args.only]
        if not services:
            print(f"Unknown service key '{args.only}'. Valid: {[s.key for s in all_services]}")
            sys.exit(1)
    else:
        services = [s for s in all_services if not (
            (s.key == "dashboard"  and args.no_dashboard) or
            (s.key == "playground" and args.no_playground)
        )]

    # --check mode
    if args.check:
        run_check(services)
        return

    # Print startup banner
    if console:
        console.rule("[bold cyan]GeoSupply AI — Starting Services[/]")
        t = Table("Service", "URL", box=box.SIMPLE_HEAD)
        for svc in services:
            t.add_row(f"[{svc.color}]{svc.label}[/]",
                      svc.url if svc.port else "[dim]stdio[/dim]")
        console.print(t)
        console.print(
            f"\n[dim]Docs:[/]  [link=http://localhost:{args.api_port}/docs]"
            f"http://localhost:{args.api_port}/docs[/link]"
            f"\n[dim]Admin:[/] [link=http://localhost:{args.dash_port}]"
            f"http://localhost:{args.dash_port}[/link]"
            f"\n[dim]Play:[/]  [link=http://localhost:{args.play_port}]"
            f"http://localhost:{args.play_port}[/link]"
            f"\n\n[dim]Press Ctrl+C to stop all services[/]\n"
        )
    else:
        print("GeoSupply AI — Starting services (install rich for a better UI)")
        for svc in services:
            print(f"  {svc.label}: {svc.url}")

    run_launcher(services, proc_env)


if __name__ == "__main__":
    main()

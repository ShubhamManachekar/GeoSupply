"""
GeoSupply Admin CLI — Rich-powered interactive command-line control panel.

Usage:
    geosupply-admin [--api URL] [--key KEY] <command> [options]

Commands:
    status               Full swarm snapshot (supervisors, workers, budget, SQLite)
    supervisors          List all supervisors with state table
    supervisor toggle    <name>  Enable/disable a supervisor
    supervisor reset     <name>  Reset circuit breaker
    workers              List all workers with tier and config
    worker patch         <name> [--retries N] [--timeout S] [--tier T]
    worker reset         <name>  Clear worker overrides
    routing              Show full ROUTING_TABLE
    logs                 Tail/query swarm logs (rich table + live stream)
    budget               Budget breakdown with per-agent cost table
    budget reset         Reset daily spend counter
    api-directory        Browse all registered API routes
    cancel               <task_id>  Cancel a pending task

Examples:
    geosupply-admin status
    geosupply-admin supervisor toggle NLPSupervisor
    geosupply-admin worker patch VerifierWorker --retries 2 --timeout 30
    geosupply-admin logs --limit 50 --agent VerifierWorker --follow
    geosupply-admin budget
    geosupply-admin api-directory --tag pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

# ── Rich imports ──────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False

# ── httpx for API calls ───────────────────────────────────────────────────────
try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

console = Console() if _RICH else None

_DEFAULT_API = os.getenv("GEOSUPPLY_API_URL", "http://localhost:8000")
_DEFAULT_KEY = os.getenv("ADMIN_API_KEY", "@Shitguy27")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers(key: str) -> dict[str, str]:
    return {"X-Admin-Key": key, "Content-Type": "application/json"}


def _get(url: str, key: str, **params) -> dict:
    if not _HTTPX:
        _die("httpx not installed — run: pip install httpx")
    with httpx.Client(timeout=15.0) as client:
        r = client.get(url, headers=_headers(key), params=params)
    r.raise_for_status()
    return r.json()


def _post(url: str, key: str, body: dict | None = None) -> dict:
    if not _HTTPX:
        _die("httpx not installed — run: pip install httpx")
    with httpx.Client(timeout=15.0) as client:
        r = client.post(url, headers=_headers(key), json=body or {})
    r.raise_for_status()
    return r.json()


def _patch(url: str, key: str, body: dict) -> dict:
    if not _HTTPX:
        _die("httpx not installed")
    with httpx.Client(timeout=15.0) as client:
        r = client.patch(url, headers=_headers(key), json=body)
    r.raise_for_status()
    return r.json()


def _delete(url: str, key: str) -> dict:
    with httpx.Client(timeout=15.0) as client:
        r = client.delete(url, headers=_headers(key))
    r.raise_for_status()
    return r.json()


def _die(msg: str) -> None:
    if console:
        console.print(f"[bold red]✗ {msg}[/]")
    else:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    if console:
        console.print(f"[bold green]✓[/] {msg}")
    else:
        print(f"OK: {msg}")


def _warn(msg: str) -> None:
    if console:
        console.print(f"[bold yellow]⚠[/] {msg}")
    else:
        print(f"WARN: {msg}")


def _bool_icon(val: bool) -> str:
    return "[green]●[/]" if val else "[red]○[/]"


def _tier_label(tier: int) -> str:
    labels = {0: "[dim]CPU[/]", 1: "[cyan]Tier-1 3B[/]", 2: "[blue]Tier-2 14B[/]", 3: "[magenta]Tier-3 20B[/]"}
    return labels.get(tier, str(tier))


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_status(api: str, key: str, **_) -> None:
    data = _get(f"{api}/admin/status", key)
    if not console:
        print(json.dumps(data, indent=2))
        return

    swarm = data.get("swarm", {})
    env = data.get("env", {})
    budget = data.get("budget", {})

    # Header panel
    ts = data.get("timestamp", "")[:19].replace("T", " ")
    console.print(Panel(
        f"[bold]GeoSupply AI — Admin Status[/]  [dim]{ts} UTC[/]",
        style="blue",
    ))

    # Swarm overview
    t = Table("Component", "Value", box=box.SIMPLE, show_header=False)
    t.add_row("Supervisors", str(swarm.get("supervisor_count", 0)))
    t.add_row("Workers", str(swarm.get("worker_count", 0)))
    t.add_row("Agents", str(swarm.get("agent_count", 0)))
    t.add_row("SQLite", "[green]OK[/]" if data.get("sqlite", {}).get("ok") else "[red]DEGRADED[/]")
    t.add_row("Log entries", str(data.get("sqlite", {}).get("log_count", 0)))
    t.add_row("Anthropic API", "[green]configured[/]" if env.get("anthropic_api") else "[yellow]not set[/]")
    t.add_row("Neo4j", "[green]configured[/]" if env.get("neo4j") else "[dim]not set[/]")
    t.add_row("Supabase", "[green]configured[/]" if env.get("supabase") else "[dim]not set[/]")
    console.print(Panel(t, title="[bold cyan]Swarm Overview[/]", border_style="cyan"))

    # Budget summary
    cap = budget.get("cap_inr", 500.0) or 500.0
    reserved = budget.get("reserved_inr", 0.0) or 0.0
    pct = min(100.0, reserved / cap * 100)
    bar_filled = int(pct / 5)
    bar = "[green]" + "█" * bar_filled + "[/][dim]" + "░" * (20 - bar_filled) + "[/]"
    console.print(Panel(
        f"{bar}  [bold]₹{reserved:.2f}[/] / ₹{cap:.2f}  ({pct:.1f}%)",
        title="[bold cyan]Budget[/]",
        border_style="cyan",
    ))

    # Supervisor state
    supers = data.get("supervisors", {})
    st = Table("Supervisor", "Enabled", "Breaker", "Failures", box=box.SIMPLE_HEAD)
    for name, s in supers.items():
        st.add_row(
            name,
            _bool_icon(s["enabled"]),
            "[red]OPEN[/]" if s["breaker_open"] else "[green]CLOSED[/]",
            str(s["breaker_failures"]),
        )
    console.print(Panel(st, title="[bold cyan]Supervisors[/]", border_style="cyan"))


def cmd_supervisors(api: str, key: str, **_) -> None:
    data = _get(f"{api}/admin/supervisors", key)
    if not console:
        print(json.dumps(data, indent=2))
        return
    t = Table("Supervisor", "Enabled", "Breaker", "Failures", "Agents", box=box.SIMPLE_HEAD)
    for s in data.get("supervisors", []):
        t.add_row(
            s["name"],
            _bool_icon(s["enabled"]),
            "[red]OPEN[/]" if s["breaker_open"] else "[green]CLOSED[/]",
            str(s["breaker_failures"]),
            str(s["agent_count"]),
        )
    console.print(Panel(t, title=f"[bold cyan]Supervisors ({data['count']})[/]", border_style="cyan"))


def cmd_supervisor_toggle(api: str, key: str, name: str, **_) -> None:
    data = _post(f"{api}/admin/supervisors/{name}/toggle", key)
    action = "enabled" if data.get("enabled") else "disabled"
    _ok(f"Supervisor [bold]{name}[/] {action}")


def cmd_supervisor_reset(api: str, key: str, name: str, **_) -> None:
    data = _post(f"{api}/admin/supervisors/{name}/circuit-breaker/reset", key)
    _ok(
        f"Circuit breaker reset for [bold]{name}[/] "
        f"(was {data.get('previous_failures', 0)} failures)"
    )


def cmd_workers(api: str, key: str, **_) -> None:
    data = _get(f"{api}/admin/workers", key)
    if not console:
        print(json.dumps(data, indent=2))
        return
    t = Table("Worker", "Tier", "Retries", "Timeout", "Overrides", "Capabilities", box=box.SIMPLE_HEAD)
    for w in data.get("workers", []):
        caps = ", ".join(w["capabilities"][:3])
        if len(w["capabilities"]) > 3:
            caps += f" +{len(w['capabilities'])-3}"
        t.add_row(
            w["name"],
            _tier_label(w["tier"]),
            str(w["max_retries"]),
            f"{w['timeout_seconds']}s",
            "[yellow]active[/]" if w["overrides_active"] else "[dim]none[/]",
            caps,
        )
    console.print(Panel(t, title=f"[bold cyan]Workers ({data['count']})[/]", border_style="cyan"))


def cmd_worker_patch(api: str, key: str, name: str, retries: int | None,
                     timeout: int | None, tier: int | None, **_) -> None:
    body: dict[str, Any] = {}
    if retries is not None:
        body["max_retries"] = retries
    if timeout is not None:
        body["timeout_seconds"] = timeout
    if tier is not None:
        body["tier_override"] = tier
    if not body:
        _warn("No changes specified — use --retries, --timeout, or --tier")
        return
    data = _patch(f"{api}/admin/workers/{name}", key, body)
    _ok(f"Worker [bold]{name}[/] patched: {data.get('applied', {})}")


def cmd_worker_reset(api: str, key: str, name: str, **_) -> None:
    data = _delete(f"{api}/admin/workers/{name}/overrides", key)
    _ok(f"Worker [bold]{name}[/] overrides cleared: {data.get('cleared', {})}")


def cmd_routing(api: str, key: str, supervisor_filter: str = "", **_) -> None:
    data = _get(f"{api}/admin/routing-table", key)
    if not console:
        print(json.dumps(data, indent=2))
        return
    t = Table("Task Type", "Supervisor", "LLM Tier", "Static", box=box.SIMPLE_HEAD)
    for row in data.get("routing_table", []):
        if supervisor_filter and supervisor_filter.lower() not in row["supervisor"].lower():
            continue
        t.add_row(
            row["task_type"],
            row["supervisor"],
            _tier_label(row["llm_tier"]),
            "[yellow]yes[/]" if row["use_static_decoder"] else "[dim]no[/]",
        )
    console.print(Panel(t, title="[bold cyan]Routing Table[/]", border_style="cyan"))


def cmd_logs(api: str, key: str, limit: int = 50, agent: str = "",
             follow: bool = False, level: str = "", since: int = 0, **_) -> None:
    if follow:
        _stream_logs(api, key, agent)
        return

    params: dict[str, Any] = {"limit": limit}
    if agent:
        params["agent_name"] = agent
    if level:
        params["level"] = level
    if since:
        params["since_minutes"] = since

    data = _get(f"{api}/admin/logs", key, **params)
    if not console:
        print(json.dumps(data, indent=2))
        return

    t = Table("Timestamp", "Agent", "Level", "Message", "Cost ₹", box=box.SIMPLE_HEAD)
    for entry in data.get("entries", []):
        ts = (entry.get("timestamp") or "")[:19].replace("T", " ")
        lvl = entry.get("level", "INFO")
        lvl_style = {"ERROR": "bold red", "WARNING": "yellow", "INFO": "green", "DEBUG": "dim"}.get(lvl, "white")
        cost = entry.get("cost_inr", 0.0)
        t.add_row(
            ts,
            entry.get("agent", ""),
            f"[{lvl_style}]{lvl}[/]",
            (entry.get("message") or "")[:80],
            f"{cost:.4f}" if cost else "[dim]0[/]",
        )
    total = data.get("total", 0)
    console.print(Panel(
        t,
        title=f"[bold cyan]Logs — {len(data.get('entries', []))} of {total}[/]",
        border_style="cyan",
    ))


def _stream_logs(api: str, key: str, agent: str = "") -> None:
    """Live SSE log tail."""
    if not _HTTPX:
        _die("httpx required for --follow")

    _warn("Streaming logs — press Ctrl+C to stop")
    url = f"{api}/admin/logs/stream"
    params: dict[str, Any] = {"poll_interval": 1.5}
    if agent:
        params["agent_name"] = agent

    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("GET", url, headers=_headers(key), params=params) as r:
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        entry = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    ts = (entry.get("timestamp") or "")[:19].replace("T", " ")
                    agent_name = entry.get("agent", "")
                    msg = entry.get("message", "")
                    cost = entry.get("cost_inr", 0.0)
                    cost_str = f" [dim]₹{cost:.4f}[/]" if cost else ""
                    if console:
                        console.print(f"[dim]{ts}[/] [cyan]{agent_name}[/] {msg}{cost_str}")
                    else:
                        print(f"{ts} {agent_name} {msg}")
    except KeyboardInterrupt:
        _ok("Stream closed")


def cmd_budget(api: str, key: str, **_) -> None:
    data = _get(f"{api}/admin/budget", key)
    if not console:
        print(json.dumps(data, indent=2))
        return

    summary = data.get("summary", {})
    cap = data.get("cap_inr", 500.0)
    reserved = summary.get("reserved_inr", 0.0) or 0.0
    remaining = summary.get("remaining_inr", cap) or cap
    pct = min(100.0, reserved / cap * 100) if cap else 0.0

    bar_filled = int(pct / 5)
    bar_color = "green" if pct < 60 else "yellow" if pct < 85 else "red"
    bar = f"[{bar_color}]" + "█" * bar_filled + "[/][dim]" + "░" * (20 - bar_filled) + "[/]"
    console.print(Panel(
        f"{bar}  [bold]₹{reserved:.2f}[/] spent / [bold]₹{remaining:.2f}[/] remaining  (cap: ₹{cap:.2f})",
        title="[bold cyan]Budget Overview[/]",
        border_style=bar_color,
    ))

    # Per-agent table
    per_agent = data.get("per_agent", [])
    if per_agent:
        t = Table("Agent", "Total Cost ₹", "Calls", box=box.SIMPLE_HEAD)
        for row in per_agent[:15]:
            cost = row.get("total_cost_inr", 0.0)
            t.add_row(
                row["agent"],
                f"₹{cost:.4f}",
                str(row["call_count"]),
            )
        console.print(Panel(t, title="[bold cyan]Cost by Agent (top 15)[/]", border_style="cyan"))

    # Daily series
    daily = data.get("daily_series", [])
    if daily:
        t2 = Table("Date", "Daily Spend ₹", box=box.SIMPLE_HEAD)
        for row in daily[:7]:
            t2.add_row(row["date"], f"₹{row['cost_inr']:.4f}")
        console.print(Panel(t2, title="[bold cyan]Daily Spend (last 7 days)[/]", border_style="cyan"))


def cmd_budget_reset(api: str, key: str, **_) -> None:
    data = _post(f"{api}/admin/budget/reset", key)
    _ok(f"Budget daily counter reset: {data.get('message', '')}")


def cmd_api_directory(api: str, key: str, tag: str = "", **_) -> None:
    data = _get(f"{api}/admin/api-directory", key)
    if not console:
        print(json.dumps(data, indent=2))
        return
    t = Table("Method", "Path", "Tags", "Summary", box=box.SIMPLE_HEAD)
    for route in data.get("routes", []):
        tags = ", ".join(route.get("tags", []))
        if tag and tag.lower() not in tags.lower():
            continue
        methods = " ".join(route.get("methods", []))
        method_style = {
            "GET": "[green]GET[/]", "POST": "[blue]POST[/]",
            "PATCH": "[yellow]PATCH[/]", "DELETE": "[red]DELETE[/]",
        }.get(methods, methods)
        t.add_row(
            method_style,
            route["path"],
            f"[dim]{tags}[/]" if tags else "",
            (route.get("summary") or "")[:60],
        )
    total = data.get("total", 0)
    console.print(Panel(
        t,
        title=f"[bold cyan]API Directory — {total} routes[/] [dim](base: {data.get('base_url', '')})[/]",
        border_style="cyan",
    ))


def cmd_cancel(api: str, key: str, task_id: str, **_) -> None:
    data = _post(f"{api}/admin/task/{task_id}/cancel", key)
    if data.get("cancelled"):
        _ok(f"Task [bold]{task_id}[/] cancelled")
    else:
        _warn(f"Task [bold]{task_id}[/] not found or already complete")


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="geosupply-admin",
        description="GeoSupply AI — Admin Control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--api", default=_DEFAULT_API, metavar="URL",
                   help=f"API base URL (default: {_DEFAULT_API})")
    p.add_argument("--key", default=_DEFAULT_KEY, metavar="KEY",
                   help="Admin API key (default: $ADMIN_API_KEY or 'dev-key')")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # status
    sub.add_parser("status", help="Full swarm snapshot")

    # supervisors
    sp = sub.add_parser("supervisors", help="List all supervisors")
    sp_sub = sp.add_subparsers(dest="supervisor_action")
    toggle_p = sp_sub.add_parser("toggle", help="Toggle supervisor on/off")
    toggle_p.add_argument("name", help="Supervisor name")
    reset_p = sp_sub.add_parser("reset", help="Reset circuit breaker")
    reset_p.add_argument("name", help="Supervisor name")

    # workers
    wp = sub.add_parser("workers", help="List all workers")
    wp_sub = wp.add_subparsers(dest="worker_action")
    patch_p = wp_sub.add_parser("patch", help="Update worker config")
    patch_p.add_argument("name", help="Worker name")
    patch_p.add_argument("--retries", type=int, default=None, metavar="N")
    patch_p.add_argument("--timeout", type=int, default=None, metavar="SECONDS")
    patch_p.add_argument("--tier", type=int, default=None, choices=[0, 1, 2, 3])
    reset_w = wp_sub.add_parser("reset", help="Clear worker overrides")
    reset_w.add_argument("name", help="Worker name")

    # routing
    rp = sub.add_parser("routing", help="Show routing table")
    rp.add_argument("--supervisor", default="", metavar="NAME", help="Filter by supervisor")

    # logs
    lp = sub.add_parser("logs", help="Query/stream logs")
    lp.add_argument("--limit", type=int, default=50)
    lp.add_argument("--agent", default="", help="Filter by agent name")
    lp.add_argument("--level", default="", help="Filter by log level")
    lp.add_argument("--since", type=int, default=0, metavar="MINUTES")
    lp.add_argument("--follow", "-f", action="store_true", help="Live stream (SSE)")

    # budget
    bp = sub.add_parser("budget", help="Budget breakdown")
    bp_sub = bp.add_subparsers(dest="budget_action")
    bp_sub.add_parser("reset", help="Reset daily spend counter")

    # api-directory
    ap = sub.add_parser("api-directory", help="Browse all API routes")
    ap.add_argument("--tag", default="", help="Filter by tag")

    # cancel
    cp = sub.add_parser("cancel", help="Cancel a pending task")
    cp.add_argument("task_id", help="Task ID to cancel")

    return p


def main() -> None:
    if not _RICH:
        print("WARNING: rich not installed — output will be plain text. Run: pip install rich")
    if not _HTTPX:
        print("ERROR: httpx not installed — run: pip install httpx", file=sys.stderr)
        sys.exit(1)

    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    api = args.api.rstrip("/")
    key = args.key

    try:
        if args.command == "status":
            cmd_status(api, key)

        elif args.command == "supervisors":
            if not hasattr(args, "supervisor_action") or not args.supervisor_action:
                cmd_supervisors(api, key)
            elif args.supervisor_action == "toggle":
                cmd_supervisor_toggle(api, key, name=args.name)
            elif args.supervisor_action == "reset":
                cmd_supervisor_reset(api, key, name=args.name)

        elif args.command == "workers":
            if not hasattr(args, "worker_action") or not args.worker_action:
                cmd_workers(api, key)
            elif args.worker_action == "patch":
                cmd_worker_patch(api, key, name=args.name,
                                 retries=args.retries, timeout=args.timeout, tier=args.tier)
            elif args.worker_action == "reset":
                cmd_worker_reset(api, key, name=args.name)

        elif args.command == "routing":
            cmd_routing(api, key, supervisor_filter=args.supervisor)

        elif args.command == "logs":
            cmd_logs(api, key, limit=args.limit, agent=args.agent,
                     follow=args.follow, level=args.level, since=args.since)

        elif args.command == "budget":
            if hasattr(args, "budget_action") and args.budget_action == "reset":
                cmd_budget_reset(api, key)
            else:
                cmd_budget(api, key)

        elif args.command == "api-directory":
            cmd_api_directory(api, key, tag=args.tag)

        elif args.command == "cancel":
            cmd_cancel(api, key, task_id=args.task_id)

        else:
            parser.print_help()

    except httpx.HTTPStatusError as exc:
        _die(f"API error {exc.response.status_code}: {exc.response.text[:200]}")
    except httpx.ConnectError:
        _die(f"Cannot connect to API at {api} — is the server running?")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

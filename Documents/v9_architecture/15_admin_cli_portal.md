# Chapter 15: Admin CLI Manager & Web Portal

## Design Philosophy

> **Mostly autonomous. Always observable. Manual override for everything.**
> The admin doesn't babysit the swarm — but can take the wheel anytime.

---

## Admin CLI Manager — `geosupply` Command

### Architecture

```
geosupply CLI
├── geosupply status          # System health at a glance
├── geosupply pipeline        # Pipeline control
│   ├── run                   # Trigger immediate pipeline run
│   ├── pause                 # Pause 6-hour cycle
│   ├── resume                # Resume cycle
│   ├── history               # Last N pipeline runs
│   └── logs [--tail N]       # Stream pipeline logs
├── geosupply agents          # Agent management
│   ├── list                  # All agents + state + health
│   ├── inspect <name>        # Deep dive into one agent
│   ├── restart <name>        # Restart a specific agent
│   ├── pause <name>          # Pause agent (won't accept tasks)
│   ├── resume <name>         # Resume paused agent
│   └── kill <name>           # Force-stop agent
├── geosupply supervisor      # Supervisor control
│   ├── list                  # All supervisors + queue depth
│   ├── budget [--reset]      # View/reset INR budgets
│   ├── queue <name>          # View supervisor task queue
│   └── drain <name>          # Drain queue (finish + no new tasks)
├── geosupply model           # Model management
│   ├── list                  # Available models + status
│   ├── fallback              # Current fallback chain state
│   ├── switch <task> <model> # Override model for task type
│   └── benchmark <model>     # Quick latency/quality benchmark
├── geosupply knowledge       # Knowledge graph
│   ├── stats                 # Graph size, growth rate
│   ├── query <topic>         # Ask the knowledge graph
│   ├── export                # Export graph as JSON
│   └── insights [--last N]   # Recent learning insights
├── geosupply cost            # INR cost tracking
│   ├── today                 # Today's spend
│   ├── week                  # This week's spend
│   ├── month                 # This month's spend
│   ├── breakdown             # Cost per agent/model
│   └── budget [set <INR>]    # View/set budget caps
├── geosupply security        # Security operations
│   ├── keys                  # Key status + rotation schedule
│   ├── rotate <keyname>      # Force key rotation
│   ├── ofac update           # Force OFAC list update
│   ├── audit                 # Security audit report
│   └── threats               # Active cyber threat summary
├── geosupply override        # Manual override commands
│   ├── halt                  # EMERGENCY HALT all operations
│   ├── degraded [level 1-4]  # Force degraded mode level
│   ├── approve <brief_id>    # Manually approve quarantined brief
│   ├── reject <brief_id>     # Manually reject brief
│   ├── source-score <id> <n> # Manually set source credibility
│   └── release               # Release from HALT/DEGRADED
└── geosupply config          # Configuration
    ├── show                  # Current running config
    ├── set <key> <value>     # Update config value
    ├── validate              # Validate current config
    └── diff                  # Show changes from default
```

### CLI Implementation

```python
import click
import rich
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

@click.group()
def cli():
    """GeoSupply AI v9.0 — Swarm Administration CLI"""
    pass

@cli.command()
def status():
    """System health at a glance."""
    table = Table(title="🌍 GeoSupply AI v9.0 — System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Cost (INR)", style="yellow")
    table.add_column("Queue", style="magenta")

    # Query all supervisors
    for sup in SwarmMaster.get_supervisors():
        status_emoji = "🟢" if sup.state == "active" else "🟡" if sup.state == "degraded" else "🔴"
        table.add_row(
            sup.name,
            f"{status_emoji} {sup.state}",
            f"₹{sup.budget.current_day_inr:.2f}",
            str(len(sup._task_queue))
        )

    console.print(table)
    console.print(f"\n📊 Pipeline: {'RUNNING' if is_running else 'IDLE'}")
    console.print(f"🧠 Knowledge Graph: {kg.graph.number_of_nodes()} entities, {kg.graph.number_of_edges()} relationships")
    console.print(f"💰 Today's spend: ₹{cost_today:.2f} / ₹300.00 limit")

@cli.group()
def override():
    """Manual override commands — use with caution."""
    pass

@override.command()
def halt():
    """🚨 EMERGENCY HALT — stops all operations immediately."""
    if click.confirm("⚠️  EMERGENCY HALT will stop ALL swarm operations. Continue?"):
        SwarmMaster.emergency_halt()
        console.print("[bold red]🛑 EMERGENCY HALT ACTIVATED[/bold red]")
        console.print("Use 'geosupply override release' to resume.")

@override.command()
@click.argument('level', type=click.IntRange(1, 4))
def degraded(level):
    """Force degraded mode at specified level (1-4)."""
    SwarmMaster.force_degraded_mode(level)
    console.print(f"[yellow]⚠️  DEGRADED_MODE Level {level} activated[/yellow]")

@override.command()
@click.argument('brief_id')
def approve(brief_id):
    """Manually approve a quarantined brief."""
    QualitySupervisor.manual_approve(brief_id)
    console.print(f"[green]✅ Brief {brief_id} manually approved[/green]")
```

---

## Admin Web Portal — Streamlit Dashboard

### Portal Architecture

```
Admin Portal (Streamlit — Page 10: Admin)
├── 📊 System Overview
│   ├── Real-time swarm topology (interactive graph)
│   ├── Agent state heatmap (healthy/degraded/error)
│   ├── Pipeline timeline (Gantt chart of current run)
│   └── INR cost waterfall (per-agent, per-model)
├── 🤖 Agent Manager
│   ├── Agent cards with state, health, queue depth
│   ├── Start/Stop/Restart buttons per agent
│   ├── Live log stream per agent
│   └── Performance sparklines (latency, quality, cost)
├── 📡 Pipeline Control
│   ├── Run Now / Pause / Resume buttons
│   ├── Pipeline stage progress bar
│   ├── Stage-by-stage results with expand/collapse
│   └── Quarantine queue (approve/reject buttons)
├── 🧠 Intelligence Dashboard
│   ├── Knowledge graph 3D visualization
│   ├── Learning insights feed (what the system learned today)
│   ├── Prediction accuracy tracker (XGBoost F1 over time)
│   └── Entity relationship explorer
├── 🛡️ Security & Threats
│   ├── Active cyber threats tracked
│   ├── API key rotation status
│   ├── OFAC sanctions list freshness
│   └── Anomaly detection alerts
├── 💰 Cost Centre
│   ├── INR spend charts (hourly/daily/monthly)
│   ├── Budget allocation sliders
│   ├── Cost per brief analysis
│   └── Model cost efficiency rankings
├── ⚙️ Configuration
│   ├── Live config editor with validation
│   ├── MoE routing table editor
│   ├── Threshold adjustments (with guardrails)
│   └── Feature flags
└── 🔴 Override Panel
    ├── EMERGENCY HALT button (requires confirmation)
    ├── Degraded mode level selector
    ├── Manual brief approval queue
    └── Source credibility override editor
```

### Portal Access Control

```
ROLES:
    ADMIN     — full access, all overrides, config changes
    OPERATOR  — view + pipeline control + brief approval
    VIEWER    — read-only dashboards
    API       — programmatic access (CLI uses this)

AUTHENTICATION:
    Local: password-based (single admin user)
    Session: JWT token, 8-hour expiry
    Audit: every admin action logged to Supabase

GUARDRAILS (even for ADMIN):
    HALLUCINATION_FLOOR cannot be changed (LOCKED at 0.70)
    Phase build order cannot be violated
    Monthly budget cap requires 2x confirmation
    EMERGENCY HALT cannot be auto-released (requires manual 'release')
```

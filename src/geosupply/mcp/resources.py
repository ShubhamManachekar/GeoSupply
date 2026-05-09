"""
GeoSupply MCP — Resource definitions.

7 resources exposed to MCP clients as readable URIs:

  geosupply://health          — Live health snapshot (JSON)
  geosupply://budget          — Current budget consumption (JSON)
  geosupply://supervisors     — Registry of all 14 supervisors (JSON)
  geosupply://workers         — Registry of all 19 workers + capabilities (JSON)
  geosupply://agents          — Registry of all 57 agents (JSON)
  geosupply://config          — Sanitised runtime configuration (JSON)
  geosupply://task/{task_id}  — Individual task status from SQLite (JSON)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def register_resources(mcp_instance: Any) -> None:

    # ── geosupply://health ────────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://health")
    async def health_resource() -> str:
        """Live health snapshot of all GeoSupply swarm layers."""
        from geosupply.mcp._context import get_swarm
        from geosupply.config import SQLITE_PATH

        swarm = get_swarm()
        supervisor_count = len(swarm._supervisor_registry)

        sqlite_ok = False
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=2.0) as conn:
                conn.execute("SELECT 1").fetchone()
            sqlite_ok = True
        except sqlite3.OperationalError:
            pass

        data = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supervisors": supervisor_count,
            "sqlite": "ok" if sqlite_ok else "degraded",
            "anthropic_api": bool(os.getenv("ANTHROPIC_API_KEY")),
            "neo4j": bool(os.getenv("NEO4J_URI")),
            "supabase": bool(os.getenv("SUPABASE_URL")),
        }
        return json.dumps(data, indent=2)

    # ── geosupply://budget ────────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://budget")
    async def budget_resource() -> str:
        """Current INR budget consumption for this session."""
        from geosupply.mcp._context import get_budget

        budget_agent = get_budget()
        result = await budget_agent.execute({"action": "status", "trace_id": "mcp-resource"})
        return json.dumps(result.get("result", {}), indent=2)

    # ── geosupply://supervisors ────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://supervisors")
    async def supervisors_resource() -> str:
        """Registry of all 14 supervisors and their registered agents."""
        from geosupply.mcp._context import get_swarm

        swarm = get_swarm()
        data: dict = {}
        for name, supervisor in swarm._supervisor_registry.items():
            agent_names = []
            if hasattr(supervisor, "_agents"):
                agent_names = list(supervisor._agents.keys())
            elif hasattr(supervisor, "agents"):
                agent_names = [
                    getattr(a, "name", str(a))
                    for a in (supervisor.agents.values()
                               if isinstance(supervisor.agents, dict)
                               else supervisor.agents)
                ]
            data[name] = {"agent_count": len(agent_names), "agents": agent_names}
        return json.dumps(data, indent=2)

    # ── geosupply://workers ───────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://workers")
    async def workers_resource() -> str:
        """Registry of all 19 workers with tier and capability information."""
        import geosupply.workers  # noqa: F401
        from geosupply.core.base_worker import BaseWorker

        registry = []
        for cls in BaseWorker.__subclasses__():
            registry.append({
                "name": getattr(cls, "name", cls.__name__),
                "tier": getattr(cls, "tier", 0),
                "capabilities": sorted(getattr(cls, "capabilities", set())),
                "use_static": getattr(cls, "use_static", False),
                "max_retries": getattr(cls, "max_retries", 3),
                "timeout_seconds": getattr(cls, "timeout_seconds", 60),
            })
        registry.sort(key=lambda w: (w["tier"], w["name"]))
        return json.dumps({"count": len(registry), "workers": registry}, indent=2)

    # ── geosupply://agents ────────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://agents")
    async def agents_resource() -> str:
        """Registry of all 57 agents with domain and capability information."""
        import geosupply.agents  # noqa: F401
        from geosupply.core.base_agent import BaseAgent

        registry = []
        for cls in BaseAgent.__subclasses__():
            registry.append({
                "name": getattr(cls, "name", cls.__name__),
                "domain": getattr(cls, "domain", "unknown"),
                "capabilities": sorted(getattr(cls, "capabilities", set())),
            })
        registry.sort(key=lambda a: (a["domain"], a["name"]))
        return json.dumps({"count": len(registry), "agents": registry}, indent=2)

    # ── geosupply://config ────────────────────────────────────────────────────

    @mcp_instance.resource("geosupply://config")
    async def config_resource() -> str:
        """Sanitised runtime configuration (no secrets, keys redacted)."""
        from geosupply.config import (
            HALLUCINATION_FLOOR,
            INTERNAL_BREAKER_MAX_FAILURES,
            MOA_ESCALATE_THRESHOLD,
            SQLITE_PATH,
        )

        def _masked(key: str) -> str:
            val = os.getenv(key, "")
            return "***set***" if val else "not_set"

        data = {
            "version": "0.1.0",
            "sqlite_path": str(SQLITE_PATH),
            "hallucination_floor": HALLUCINATION_FLOOR,
            "internal_breaker_max_failures": INTERNAL_BREAKER_MAX_FAILURES,
            "moa_escalate_threshold": MOA_ESCALATE_THRESHOLD,
            "env": {
                "ANTHROPIC_API_KEY": _masked("ANTHROPIC_API_KEY"),
                "SUPABASE_URL": _masked("SUPABASE_URL"),
                "NEO4J_URI": _masked("NEO4J_URI"),
                "NEWS_API_KEY": _masked("NEWS_API_KEY"),
                "ACLED_API_KEY": _masked("ACLED_API_KEY"),
                "TELEGRAM_BOT_TOKEN": _masked("TELEGRAM_BOT_TOKEN"),
                "JWT_SECRET_KEY": _masked("JWT_SECRET_KEY"),
                "PORT": os.getenv("PORT", "8000"),
            },
        }
        return json.dumps(data, indent=2)

    # ── geosupply://task/{task_id} ─────────────────────────────────────────────

    @mcp_instance.resource("geosupply://task/{task_id}")
    async def task_resource(task_id: str) -> str:
        """Individual task status and result from the SQLite audit store."""
        from geosupply.config import SQLITE_PATH

        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                row = conn.execute(
                    "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
        except sqlite3.OperationalError as exc:
            return json.dumps({"error": str(exc), "task_id": task_id})

        if row:
            return json.dumps({"task_id": task_id, "found": True, "data": json.loads(row[0])}, indent=2)
        return json.dumps({"task_id": task_id, "found": False}, indent=2)

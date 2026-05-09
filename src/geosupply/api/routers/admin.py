"""
GeoSupply AI — Admin REST API Router

Granular control plane for the swarm: supervisors, workers, circuit breakers,
routing table, budget overrides, log queries, and live SSE log streaming.

All endpoints are prefixed /admin and require the X-Admin-Key header
(matches ADMIN_API_KEY env var, falls back to "dev-key" in local mode).

Endpoints
---------
GET  /admin/status               — Full swarm state snapshot
GET  /admin/supervisors          — List all supervisors with enabled/breaker status
POST /admin/supervisors/{name}/toggle          — Enable or disable a supervisor
POST /admin/supervisors/{name}/circuit-breaker/reset — Reset breaker failure count
GET  /admin/workers              — List all workers with tier, config, capabilities
PATCH /admin/workers/{name}      — Update worker runtime config (retries, timeout, tier)
GET  /admin/routing-table        — Full ROUTING_TABLE dump
GET  /admin/logs                 — Query swarm_logs (filter, paginate, aggregate)
GET  /admin/logs/stream          — SSE real-time log tail
GET  /admin/budget               — Detailed budget breakdown
POST /admin/budget/override      — Override budget cap (requires elevated key)
POST /admin/budget/reset         — Reset daily spend counter
GET  /admin/api-directory        — Machine-readable list of all API routes
POST /admin/task/{task_id}/cancel — Cancel a pending task
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from geosupply.api.dependencies import swarm_master_dep, budget_dep
from geosupply.config import SQLITE_PATH, BUDGET_CAP_INR

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Auth ──────────────────────────────────────────────────────────────────────

_ADMIN_KEY_HEADER = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def _require_admin(key: str | None = Security(_ADMIN_KEY_HEADER)) -> str:
    expected = os.getenv("ADMIN_API_KEY", "@Shitguy27")
    if not key or key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Key header",
        )
    return key


def _require_elevated(key: str | None = Security(_ADMIN_KEY_HEADER)) -> str:
    """Elevated key required for destructive ops (budget override, breaker reset)."""
    expected = os.getenv("ADMIN_ELEVATED_KEY", os.getenv("ADMIN_API_KEY", "@Shitguy27"))
    if not key or key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Elevated admin key required for this operation",
        )
    return key


# ── In-process supervisor state store ─────────────────────────────────────────
# Maps supervisor_name → {enabled: bool, breaker_failures: int, breaker_open: bool}
_SUPERVISOR_STATE: dict[str, dict] = {}
# Worker runtime overrides: worker_name → {max_retries, timeout_seconds}
_WORKER_OVERRIDES: dict[str, dict] = {}


def _supervisor_state(name: str) -> dict:
    if name not in _SUPERVISOR_STATE:
        _SUPERVISOR_STATE[name] = {"enabled": True, "breaker_failures": 0, "breaker_open": False}
    return _SUPERVISOR_STATE[name]


# ── Request / Response models ─────────────────────────────────────────────────

class WorkerPatch(BaseModel):
    max_retries: int | None = Field(None, ge=0, le=10)
    timeout_seconds: int | None = Field(None, ge=5, le=300)
    tier_override: int | None = Field(None, ge=0, le=3)


class BudgetOverride(BaseModel):
    new_cap_inr: float = Field(..., gt=0, le=50_000)
    reason: str = Field(..., min_length=5)


# ── GET /admin/status ─────────────────────────────────────────────────────────

@router.get("/status", dependencies=[Depends(_require_admin)])
async def admin_status(sm=Depends(swarm_master_dep), budget=Depends(budget_dep)):
    """Full swarm state snapshot — supervisors, workers, budget, SQLite health."""
    from geosupply.core.base_worker import BaseWorker
    from geosupply.core.base_agent import BaseAgent

    budget_r = await budget.execute({"action": "STATUS"})
    budget_data = budget_r.get("result", {})

    sqlite_ok = False
    log_count = 0
    try:
        with sqlite3.connect(str(SQLITE_PATH), timeout=2.0) as conn:
            conn.execute("SELECT 1")
            row = conn.execute("SELECT COUNT(*) FROM swarm_logs").fetchone()
            log_count = row[0] if row else 0
            sqlite_ok = True
    except sqlite3.OperationalError:
        pass

    supervisors = {}
    for name in sm._supervisor_registry:
        st = _supervisor_state(name)
        supervisors[name] = {
            "enabled": st["enabled"],
            "breaker_open": st["breaker_open"],
            "breaker_failures": st["breaker_failures"],
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "swarm": {
            "supervisor_count": len(sm._supervisor_registry),
            "worker_count": len(BaseWorker.__subclasses__()),
            "agent_count": len(BaseAgent.__subclasses__()),
        },
        "supervisors": supervisors,
        "budget": budget_data,
        "sqlite": {"ok": sqlite_ok, "log_count": log_count},
        "env": {
            "anthropic_api": bool(os.getenv("ANTHROPIC_API_KEY")),
            "neo4j": bool(os.getenv("NEO4J_URI")),
            "supabase": bool(os.getenv("SUPABASE_URL")),
            "admin_key_set": os.getenv("ADMIN_API_KEY", "") != "",
        },
    }


# ── GET /admin/supervisors ────────────────────────────────────────────────────

@router.get("/supervisors", dependencies=[Depends(_require_admin)])
async def list_supervisors(sm=Depends(swarm_master_dep)):
    """List all 14 supervisors with runtime state."""
    result = []
    for name, supervisor in sm._supervisor_registry.items():
        st = _supervisor_state(name)
        agent_names: list[str] = []
        if hasattr(supervisor, "_agents"):
            agent_names = list(supervisor._agents.keys())
        result.append({
            "name": name,
            "enabled": st["enabled"],
            "breaker_open": st["breaker_open"],
            "breaker_failures": st["breaker_failures"],
            "agent_count": len(agent_names),
            "agents": agent_names,
        })
    return {"count": len(result), "supervisors": result}


# ── POST /admin/supervisors/{name}/toggle ──────────────────────────────────────

@router.post("/supervisors/{name}/toggle", dependencies=[Depends(_require_admin)])
async def toggle_supervisor(name: str, sm=Depends(swarm_master_dep)):
    """Enable or disable a supervisor by name."""
    if name not in sm._supervisor_registry:
        raise HTTPException(status_code=404, detail=f"Supervisor '{name}' not found")
    st = _supervisor_state(name)
    st["enabled"] = not st["enabled"]
    action = "enabled" if st["enabled"] else "disabled"
    logger.warning("Admin: supervisor %s %s", name, action)
    return {"supervisor": name, "enabled": st["enabled"], "action": action}


# ── POST /admin/supervisors/{name}/circuit-breaker/reset ──────────────────────

@router.post(
    "/supervisors/{name}/circuit-breaker/reset",
    dependencies=[Depends(_require_elevated)],
)
async def reset_circuit_breaker(name: str, sm=Depends(swarm_master_dep)):
    """Reset circuit breaker failure count and open state for a supervisor."""
    if name not in sm._supervisor_registry:
        raise HTTPException(status_code=404, detail=f"Supervisor '{name}' not found")
    st = _supervisor_state(name)
    prev_failures = st["breaker_failures"]
    st["breaker_failures"] = 0
    st["breaker_open"] = False
    logger.warning("Admin: circuit breaker reset for %s (was %d failures)", name, prev_failures)
    return {
        "supervisor": name,
        "previous_failures": prev_failures,
        "breaker_open": False,
        "message": "Circuit breaker reset successfully",
    }


# ── GET /admin/workers ────────────────────────────────────────────────────────

@router.get("/workers", dependencies=[Depends(_require_admin)])
async def list_workers():
    """List all workers with tier, capabilities, and any runtime overrides."""
    import geosupply.workers  # noqa: F401 — force registration
    from geosupply.core.base_worker import BaseWorker

    workers = []
    for cls in BaseWorker.__subclasses__():
        name = getattr(cls, "name", cls.__name__)
        overrides = _WORKER_OVERRIDES.get(name, {})
        workers.append({
            "name": name,
            "tier": overrides.get("tier_override", getattr(cls, "tier", 0)),
            "tier_original": getattr(cls, "tier", 0),
            "capabilities": sorted(getattr(cls, "capabilities", set())),
            "max_retries": overrides.get("max_retries", getattr(cls, "max_retries", 3)),
            "timeout_seconds": overrides.get("timeout_seconds", getattr(cls, "timeout_seconds", 60)),
            "use_static": getattr(cls, "use_static", False),
            "overrides_active": bool(overrides),
        })
    workers.sort(key=lambda w: (w["tier"], w["name"]))
    return {"count": len(workers), "workers": workers}


# ── PATCH /admin/workers/{name} ────────────────────────────────────────────────

@router.patch("/workers/{name}", dependencies=[Depends(_require_admin)])
async def patch_worker(name: str, patch: WorkerPatch):
    """Update runtime config for a worker (retries, timeout, tier override)."""
    import geosupply.workers  # noqa: F401
    from geosupply.core.base_worker import BaseWorker

    worker_names = {getattr(cls, "name", cls.__name__) for cls in BaseWorker.__subclasses__()}
    if name not in worker_names:
        raise HTTPException(status_code=404, detail=f"Worker '{name}' not found")

    overrides = _WORKER_OVERRIDES.setdefault(name, {})
    updates = patch.model_dump(exclude_none=True)
    overrides.update(updates)
    logger.warning("Admin: worker %s patched — %s", name, updates)
    return {"worker": name, "overrides": overrides, "applied": updates}


# ── DELETE /admin/workers/{name}/overrides ─────────────────────────────────────

@router.delete("/workers/{name}/overrides", dependencies=[Depends(_require_admin)])
async def reset_worker_overrides(name: str):
    """Clear all runtime overrides for a worker, restoring class defaults."""
    removed = _WORKER_OVERRIDES.pop(name, {})
    return {"worker": name, "cleared": removed, "message": "Overrides removed — class defaults restored"}


# ── GET /admin/routing-table ──────────────────────────────────────────────────

@router.get("/routing-table", dependencies=[Depends(_require_admin)])
async def get_routing_table():
    """Return the full ROUTING_TABLE with supervisor, tier, and static decoder info."""
    from geosupply.orchestrator.swarm_master import ROUTING_TABLE

    rows = []
    for task_type, (supervisor, tier, use_static) in ROUTING_TABLE.items():
        rows.append({
            "task_type": task_type,
            "supervisor": supervisor,
            "llm_tier": tier,
            "use_static_decoder": use_static,
        })
    rows.sort(key=lambda r: (r["supervisor"], r["task_type"]))
    return {"count": len(rows), "routing_table": rows}


# ── GET /admin/logs ────────────────────────────────────────────────────────────

@router.get("/logs", dependencies=[Depends(_require_admin)])
async def query_logs(
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    agent_name: str = Query("", description="Filter by agent name (substring match)"),
    level: str = Query("", description="Filter by log level substring"),
    since_minutes: int = Query(0, ge=0, description="Only show logs from last N minutes (0=all)"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Query swarm audit logs with filtering, pagination, and ordering."""
    direction = "DESC" if order == "desc" else "ASC"
    clauses: list[str] = []
    params: list[Any] = []

    if agent_name:
        clauses.append("agent_name LIKE ?")
        params.append(f"%{agent_name}%")
    if level:
        clauses.append("level LIKE ?")
        params.append(f"%{level.upper()}%")
    if since_minutes > 0:
        clauses.append("timestamp >= datetime('now', ?)")
        params.append(f"-{since_minutes} minutes")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    total_sql = f"SELECT COUNT(*) FROM swarm_logs {where}"
    rows_sql = (
        f"SELECT id, timestamp, agent_name, level, message, cost_inr, trace_id "
        f"FROM swarm_logs {where} "
        f"ORDER BY timestamp {direction} LIMIT ? OFFSET ?"
    )

    entries = []
    total = 0
    try:
        with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
            # Ensure level column exists (may not in older DBs)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(swarm_logs)").fetchall()}
            has_level = "level" in cols
            has_trace = "trace_id" in cols

            if not has_level and level:
                return {"total": 0, "offset": offset, "entries": [], "note": "level column not in schema"}

            total_row = conn.execute(total_sql, params).fetchone()
            total = total_row[0] if total_row else 0

            select_cols = "id, timestamp, agent_name"
            select_cols += ", level" if has_level else ", 'INFO' as level"
            select_cols += ", message"
            select_cols += ", cost_inr"
            select_cols += ", trace_id" if has_trace else ", '' as trace_id"

            rows_sql = (
                f"SELECT {select_cols} FROM swarm_logs {where} "
                f"ORDER BY timestamp {direction} LIMIT ? OFFSET ?"
            )
            rows = conn.execute(rows_sql, params + [limit, offset]).fetchall()
            entries = [
                {
                    "id": r[0], "timestamp": r[1], "agent": r[2],
                    "level": r[3], "message": r[4],
                    "cost_inr": round(r[5] or 0.0, 6), "trace_id": r[6],
                }
                for r in rows
            ]
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite error: {exc}")

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(entries),
        "entries": entries,
    }


# ── GET /admin/logs/stream ────────────────────────────────────────────────────

@router.get("/logs/stream", dependencies=[Depends(_require_admin)])
async def stream_logs(
    request: Request,
    poll_interval: float = Query(2.0, ge=0.5, le=30.0),
    agent_name: str = Query(""),
):
    """Server-Sent Events stream of new log entries (tail -f style).

    Connect with: curl -N -H "X-Admin-Key: dev-key" http://localhost:8000/admin/logs/stream
    """
    async def _event_generator() -> AsyncGenerator[str, None]:
        last_id = 0
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=2.0) as conn:
                row = conn.execute("SELECT MAX(id) FROM swarm_logs").fetchone()
                last_id = row[0] or 0
        except sqlite3.OperationalError:
            pass

        while True:
            if await request.is_disconnected():
                break

            try:
                with sqlite3.connect(str(SQLITE_PATH), timeout=2.0) as conn:
                    q = "SELECT id, timestamp, agent_name, message, cost_inr FROM swarm_logs WHERE id > ?"
                    params: list[Any] = [last_id]
                    if agent_name:
                        q += " AND agent_name LIKE ?"
                        params.append(f"%{agent_name}%")
                    q += " ORDER BY id ASC LIMIT 50"
                    rows = conn.execute(q, params).fetchall()

                for r in rows:
                    payload = json.dumps({
                        "id": r[0], "timestamp": r[1], "agent": r[2],
                        "message": r[3], "cost_inr": round(r[4] or 0.0, 6),
                    })
                    yield f"data: {payload}\n\n"
                    last_id = max(last_id, r[0])

            except sqlite3.OperationalError:
                yield "data: {\"error\": \"sqlite_unavailable\"}\n\n"

            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── GET /admin/budget ─────────────────────────────────────────────────────────

@router.get("/budget", dependencies=[Depends(_require_admin)])
async def admin_budget_detail(budget=Depends(budget_dep)):
    """Detailed budget breakdown with per-agent costs from SQLite."""
    budget_r = await budget.execute({"action": "STATUS"})
    budget_data = budget_r.get("result", {})

    per_agent: list[dict] = []
    daily_series: list[dict] = []
    try:
        with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
            rows = conn.execute(
                "SELECT agent_name, SUM(cost_inr), COUNT(*) "
                "FROM swarm_logs GROUP BY agent_name "
                "ORDER BY SUM(cost_inr) DESC LIMIT 20"
            ).fetchall()
            per_agent = [
                {"agent": r[0], "total_cost_inr": round(r[1] or 0.0, 4), "call_count": r[2]}
                for r in rows
            ]

            rows2 = conn.execute(
                "SELECT date(timestamp), SUM(cost_inr) "
                "FROM swarm_logs GROUP BY date(timestamp) "
                "ORDER BY date(timestamp) DESC LIMIT 30"
            ).fetchall()
            daily_series = [
                {"date": r[0], "cost_inr": round(r[1] or 0.0, 4)} for r in rows2
            ]
    except sqlite3.OperationalError:
        pass

    return {
        "summary": budget_data,
        "cap_inr": BUDGET_CAP_INR,
        "per_agent": per_agent,
        "daily_series": daily_series,
    }


# ── POST /admin/budget/override ───────────────────────────────────────────────

_budget_cap_override: float | None = None


@router.post("/budget/override", dependencies=[Depends(_require_elevated)])
async def override_budget(body: BudgetOverride):
    """Override the budget cap (requires elevated admin key). Persists in-process only."""
    global _budget_cap_override
    prev = _budget_cap_override or BUDGET_CAP_INR
    _budget_cap_override = body.new_cap_inr
    logger.warning(
        "Admin: budget cap overridden ₹%.2f → ₹%.2f — reason: %s",
        prev, body.new_cap_inr, body.reason,
    )
    return {
        "previous_cap_inr": prev,
        "new_cap_inr": body.new_cap_inr,
        "reason": body.reason,
        "warning": "Override is in-process only and resets on server restart",
    }


# ── POST /admin/budget/reset ──────────────────────────────────────────────────

@router.post("/budget/reset", dependencies=[Depends(_require_elevated)])
async def reset_budget_counter(budget=Depends(budget_dep)):
    """Reset the daily spend counter in the BudgetManagerAgent."""
    result = await budget.execute({"action": "RESET"})
    logger.warning("Admin: budget daily counter reset")
    return {"message": "Budget daily counter reset", "result": result.get("result", {})}


# ── POST /admin/task/{task_id}/cancel ──────────────────────────────────────────

@router.post("/task/{task_id}/cancel", dependencies=[Depends(_require_admin)])
async def cancel_task(task_id: str):
    """Mark a pending task as cancelled in the SQLite task store."""
    try:
        with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
            conn.execute(
                "UPDATE tasks SET payload = json_patch(payload, ?) WHERE task_id = ?",
                (json.dumps({"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}), task_id),
            )
            affected = conn.execute("SELECT changes()").fetchone()[0]
        if affected:
            return {"task_id": task_id, "cancelled": True}
        return {"task_id": task_id, "cancelled": False, "reason": "task_not_found"}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite error: {exc}")


# ── GET /admin/api-directory ──────────────────────────────────────────────────

@router.get("/api-directory", dependencies=[Depends(_require_admin)])
async def api_directory(request: Request):
    """Machine-readable directory of all registered API routes."""
    app = request.app
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "methods": sorted(route.methods or []),
                "name": getattr(route, "name", ""),
                "summary": getattr(route, "summary", "") or (
                    route.endpoint.__doc__.strip().split("\n")[0]
                    if route.endpoint.__doc__ else ""
                ),
                "tags": list(getattr(route, "tags", []) or []),
                "deprecated": getattr(route, "deprecated", False),
            })
    routes.sort(key=lambda r: (r["tags"][0] if r["tags"] else "z", r["path"]))
    return {
        "total": len(routes),
        "base_url": str(request.base_url).rstrip("/"),
        "routes": routes,
    }

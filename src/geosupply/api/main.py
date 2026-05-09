"""
GeoSupply AI — FastAPI Application (Phase 9)

REST API server for the GeoSupply AI swarm intelligence platform.

Start: uvicorn geosupply.api.main:app --host 0.0.0.0 --port 8000 --reload
Docs:  http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from geosupply.api.routers import health, tasks, pipeline, brief, workers, budget, kg, audit, admin, playground

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: warm up singletons and force all subclass registrations.
    Imports all worker/agent/supervisor/subagent modules so __subclasses__() is populated
    before the first request.
    """
    from geosupply.api.dependencies import get_swarm_master, get_budget_agent
    import geosupply.workers    # noqa: F401
    import geosupply.agents     # noqa: F401
    import geosupply.supervisors  # noqa: F401
    import geosupply.subagents  # noqa: F401
    get_swarm_master()
    get_budget_agent()
    from geosupply.bootstrap import wire_all_supervisors
    _log.info("Bootstrap: wiring agents to supervisors...")
    summary = wire_all_supervisors()
    _log.info("Bootstrap complete: %d supervisors wired", len(summary))
    # Install non-invasive tracer — instruments all layers for the Playground
    from geosupply.core.tracer import install_tracer
    installed = install_tracer()
    _log.info("Tracer: %s", "installed" if installed else "already active")

    yield

    # Graceful shutdown: clear singleton caches so resources are released
    _log.info("Shutdown: clearing singleton caches")
    get_swarm_master.cache_clear()
    get_budget_agent.cache_clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GeoSupply AI API",
        version="0.1.0",
        description="India-centric geopolitical supply chain intelligence REST API",
        lifespan=lifespan,
    )
    app.include_router(health.router,    prefix="/health",    tags=["health"])
    app.include_router(tasks.router,     prefix="/tasks",     tags=["tasks"])
    app.include_router(pipeline.router,  prefix="/pipeline",  tags=["pipeline"])
    app.include_router(brief.router,     prefix="/brief",     tags=["brief"])
    app.include_router(workers.router,   prefix="",           tags=["registry"])
    app.include_router(budget.router,    prefix="/budget",    tags=["budget"])
    app.include_router(kg.router,        prefix="/kg",        tags=["knowledge-graph"])
    app.include_router(audit.router,      prefix="/audit",      tags=["audit"])
    app.include_router(admin.router,      prefix="/admin",      tags=["admin"])
    app.include_router(playground.router, prefix="/playground", tags=["playground"])
    return app


app = create_app()


def main() -> None:
    """Console entrypoint for local API execution."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("geosupply.api.main:app", host="0.0.0.0", port=port, reload=False)

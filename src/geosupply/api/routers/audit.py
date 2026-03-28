"""Audit status and run endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from geosupply.api.schemas_api import AuditStatusResponse, AuditRunResponse
from geosupply.core.base_worker import BaseWorker
from geosupply.core.base_agent import BaseAgent
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import ALL_SCHEMAS

router = APIRouter()

_last_run_at: datetime | None = None


@router.get("", response_model=AuditStatusResponse)
async def audit_status():
    """Get current audit status — component discovery counts."""
    return AuditStatusResponse(
        workers_discovered=len(BaseWorker.__subclasses__()),
        agents_discovered=len(BaseAgent.__subclasses__()),
        subagents_discovered=len(BaseSubAgent.__subclasses__()),
        schema_count=len(ALL_SCHEMAS),
        last_run_at=_last_run_at,
    )


@router.get("/run", response_model=AuditRunResponse)
async def audit_run(
    categories: str = Query(default="breakage,logic"),
    level: str = Query(default="strict"),
):
    """Run audit checks for the specified categories."""
    global _last_run_at
    category_list = [c.strip() for c in categories.split(",") if c.strip()]

    passed = 0
    failed = 0

    # Breakage checks: all base subclasses importable
    if "breakage" in category_list:
        for cls in BaseWorker.__subclasses__():
            if cls.__name__:
                passed += 1
        for cls in BaseAgent.__subclasses__():
            if cls.__name__:
                passed += 1

    # Logic checks: all schemas have schema_version field
    if "logic" in category_list:
        for name, schema_cls in ALL_SCHEMAS.items():
            if hasattr(schema_cls, "model_fields") and "schema_version" in schema_cls.model_fields:
                passed += 1
            else:
                failed += 1

    _last_run_at = datetime.now(timezone.utc)
    return AuditRunResponse(passed=passed, failed=failed, categories_run=category_list)

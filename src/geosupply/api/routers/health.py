"""Health check endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from geosupply.api.schemas_api import HealthResponse, DeepHealthResponse
from geosupply.api.dependencies import swarm_master_dep, budget_dep
from geosupply.config import get_env
from geosupply.core.base_worker import BaseWorker
from geosupply.core.base_agent import BaseAgent

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_liveness():
    """Liveness probe — returns ok if server is running."""
    return HealthResponse(status="ok", environment=get_env())


@router.get("/deep", response_model=DeepHealthResponse)
async def health_deep(
    sm=Depends(swarm_master_dep),
    budget=Depends(budget_dep),
):
    """Deep health check — verifies supervisors, budget, workers, agents."""
    budget_result = await budget.execute({"action": "STATUS"})
    remaining = budget_result.get("result", {}).get("remaining_inr", 0.0)
    workers = [c.__name__ for c in BaseWorker.__subclasses__()]
    agents = [c.__name__ for c in BaseAgent.__subclasses__()]
    return DeepHealthResponse(
        status="ok",
        environment=get_env(),
        supervisors_registered=len(sm.registered_supervisors),
        budget_remaining_inr=remaining,
        workers_count=len(workers),
        agents_count=len(agents),
    )

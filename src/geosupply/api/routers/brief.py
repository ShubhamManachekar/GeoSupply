"""SUPPLY_BRIEF full DAG execution endpoint."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from geosupply.api.schemas_api import BriefRequest, BriefResponse
from geosupply.api.dependencies import swarm_master_dep

router = APIRouter()

_BRIEF_TIMEOUT_S = 120


@router.post("", response_model=BriefResponse, status_code=200)
async def generate_brief(
    body: BriefRequest,
    sm=Depends(swarm_master_dep),
):
    """Execute the full SUPPLY_BRIEF 10-task DAG pipeline."""
    try:
        result = await asyncio.wait_for(
            sm.run_supply_brief(body.payload, body.plan_id),
            timeout=_BRIEF_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="SUPPLY_BRIEF DAG timed out (120s limit)")
    return BriefResponse(
        plan_id=result["plan_id"],
        task_results=result["task_results"],
        total_cost_inr=result["total_cost_inr"],
    )

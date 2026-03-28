"""Budget status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from geosupply.api.schemas_api import BudgetStatusResponse
from geosupply.api.dependencies import budget_dep
from geosupply.config import (
    BUDGET_CAP_INR,
    COST_ALERT_WARN_MONTHLY_INR,
    COST_ALERT_CRITICAL_MONTHLY_INR,
)

router = APIRouter()


def _alert_level(reserved: float) -> str:
    if reserved >= COST_ALERT_CRITICAL_MONTHLY_INR:
        return "CRITICAL"
    if reserved >= COST_ALERT_WARN_MONTHLY_INR:
        return "WARN"
    if reserved >= BUDGET_CAP_INR * 0.5:
        return "ALERT"
    return "NORMAL"


@router.get("", response_model=BudgetStatusResponse)
async def budget_status(budget=Depends(budget_dep)):
    """Get current budget status."""
    result = await budget.execute({"action": "STATUS"})
    data = result.get("result", {})
    reserved = data.get("reserved_inr", 0.0)
    remaining = data.get("remaining_inr", BUDGET_CAP_INR)
    return BudgetStatusResponse(
        cap_inr=BUDGET_CAP_INR,
        reserved_inr=reserved,
        remaining_inr=remaining,
        alert_level=_alert_level(reserved),
    )


@router.get("/history")
async def budget_history(budget=Depends(budget_dep)):
    """Get budget spend history."""
    result = await budget.execute({"action": "STATUS"})
    history = result.get("result", {}).get("history", [])
    return {"history": history, "count": len(history)}

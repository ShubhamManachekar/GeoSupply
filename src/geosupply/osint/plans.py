"""
GeoSupply AI — Freemium plan gating (FREE / PRO / ENTERPRISE).

Monetisation model for the OSINT platform. All amounts INR (never USD).

  FREE        ₹0/month        Live OSINT dashboard: map, wire, risk index,
                              chokepoints, war zones, India ports, markets,
                              streams, focus mode, WebSocket live link.
  PRO         ₹499/month      + Advanced intelligence: agentic RAG (/ask),
                              RAG feedback learning, knowledge graph,
                              source-trust profiles, risk projections API.
  ENTERPRISE  ₹4,999/month    + Full swarm: pipeline/brief/KG/budget/audit,
                              admin console, playground, MCP server,
                              custom sources & SLAs.

Deployment semantics:
  - Self-hosted (default): GEOSUPPLY_PLAN unset → ENTERPRISE. An
    open-source install is never crippled on the user's own machine.
  - Hosted/SaaS: the operator sets GEOSUPPLY_PLAN per deployment (or
    fronts the API with a billing proxy that sets it) and the gates below
    return 403 with an upgrade hint instead of data.

The gate is a FastAPI dependency, so gated endpoints stay declarative:

    @router.get("/ask", dependencies=[require_feature("advanced_intel")])
"""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

PLAN_ORDER = ("FREE", "PRO", "ENTERPRISE")

PLAN_PRICES_INR: dict[str, int] = {"FREE": 0, "PRO": 499, "ENTERPRISE": 4999}

# feature key → minimum plan that unlocks it
FEATURE_MIN_PLAN: dict[str, str] = {
    "dashboard": "FREE",          # map + panels + WS + streams + focus
    "advanced_intel": "PRO",      # /ask, /ask/feedback, /graph, /sources/bias
    "swarm": "ENTERPRISE",        # pipeline/brief/kg/budget/audit/admin/playground
}


class PlanInfo(BaseModel):
    """Response shape for GET /osint/plan (frontend badge + lock states)."""
    plan: str
    price_inr: int
    features: list[str] = Field(default_factory=list)
    locked: list[str] = Field(default_factory=list)
    upgrade_hint: str = ""


def current_plan() -> str:
    """Active plan from env; unset/invalid → ENTERPRISE (self-hosted full)."""
    plan = os.getenv("GEOSUPPLY_PLAN", "").strip().upper()
    return plan if plan in PLAN_ORDER else "ENTERPRISE"


def has_feature(feature: str, plan: str | None = None) -> bool:
    """True when `plan` (default: current) meets the feature's minimum plan."""
    required = FEATURE_MIN_PLAN.get(feature)
    if required is None:
        return False          # unknown features are locked, never open
    active = plan if plan is not None else current_plan()
    return PLAN_ORDER.index(active) >= PLAN_ORDER.index(required)


def plan_info() -> PlanInfo:
    plan = current_plan()
    features = sorted(f for f in FEATURE_MIN_PLAN if has_feature(f, plan))
    locked = sorted(f for f in FEATURE_MIN_PLAN if not has_feature(f, plan))
    idx = PLAN_ORDER.index(plan)
    hint = ""
    if locked and idx + 1 < len(PLAN_ORDER):
        nxt = PLAN_ORDER[idx + 1]
        hint = (f"Upgrade to {nxt} (₹{PLAN_PRICES_INR[nxt]}/month) to unlock: "
                + ", ".join(locked))
    return PlanInfo(plan=plan, price_inr=PLAN_PRICES_INR[plan],
                    features=features, locked=locked, upgrade_hint=hint)


def require_feature(feature: str):
    """FastAPI dependency: 403 with an upgrade hint when the plan lacks it."""
    async def _gate() -> None:
        if not has_feature(feature):
            required = FEATURE_MIN_PLAN.get(feature, "ENTERPRISE")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "plan_required",
                    "feature": feature,
                    "current_plan": current_plan(),
                    "required_plan": required,
                    "price_inr": PLAN_PRICES_INR.get(required, 0),
                    "message": f"'{feature}' requires the {required} plan "
                               f"(₹{PLAN_PRICES_INR.get(required, 0)}/month).",
                },
            )
    return Depends(_gate)

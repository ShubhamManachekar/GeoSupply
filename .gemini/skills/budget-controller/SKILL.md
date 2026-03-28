---
name: budget-controller
description: Real-time INR budget enforcement for GeoSupply — BudgetManagerAgent implementation, daily/monthly tracking, tier-based cost accounting, alert escalation, and Tier-3 hard-stop logic.
---

# Budget Controller — GeoSupply INR Enforcement

> Custom GeoSupply skill — ₹500/month cap enforcement

## Budget Architecture

```
BudgetManagerAgent (Layer 3)
  ├── Tracks spend per: tier, agent, worker, day, month
  ├── Enforces: BUDGET_CAP_INR = ₹500/month (LOCKED)
  ├── Alerts at: COST_ALERT_WARN_DAILY_INR = ₹250
  │             COST_ALERT_CRITICAL_DAILY_INR = ₹270
  └── Hard stop: Blocks Tier-3 calls when daily critical exceeded

CostWorker (v10, Layer 5)
  └── Aggregates costs from all tiers → publishes to BudgetManagerAgent

CostProjection (Schema #24)
  └── Forward-looking burn-rate estimates
```

---

## 1. BudgetManagerAgent Full Implementation

```python
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, date
from collections import defaultdict
from geosupply.core.base_agent import BaseAgent
from geosupply.schemas import AgentMessage, CostProjection, WorkerError
from geosupply.config import (
    BUDGET_CAP_INR, COST_ALERT_WARN_DAILY_INR,
    COST_ALERT_CRITICAL_DAILY_INR, LLMTier
)


class BudgetManagerAgent(BaseAgent):
    """
    INR budget enforcer for the GeoSupply swarm.
    Tracks all costs, fires alerts, hard-blocks Tier-3 when critical.
    """
    name = "budget_manager"
    tier = LLMTier.CPU_ONLY   # Pure computation — no LLM needed

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._daily_spend: dict[date, float] = defaultdict(float)
        self._monthly_spend: float = 0.0
        self._tier_spend: dict[str, float] = defaultdict(float)
        self._agent_spend: dict[str, float] = defaultdict(float)
        self._tier3_blocked: bool = False
        self._lock = asyncio.Lock()

    async def execute(self, action: str, payload: dict) -> dict:
        handlers = {
            "approve_spend":    self._approve_spend,
            "record_spend":     self._record_spend,
            "get_status":       self._get_status,
            "get_projection":   self._get_projection,
            "reset_daily":      self._reset_daily,
        }
        if action not in handlers:
            return {"error": f"Unknown action: {action}", "meta": {"cost_inr": 0.0}}
        return await handlers[action](payload)

    async def _approve_spend(self, payload: dict) -> dict:
        """Gate check before any LLM or API call."""
        amount_inr = float(payload.get("amount_inr", 0.0))
        tier = payload.get("tier", "UNKNOWN")

        async with self._lock:
            today = datetime.now(timezone.utc).date()
            daily_total = self._daily_spend[today] + amount_inr
            monthly_total = self._monthly_spend + amount_inr

            # Hard stop: monthly cap
            if monthly_total > BUDGET_CAP_INR:
                await self._alert("MONTHLY_CAP_EXCEEDED", amount_inr, tier)
                return {"approved": False, "reason": "monthly_cap", "meta": {"cost_inr": 0.0}}

            # Hard stop: Tier-3 blocked after critical daily threshold
            if tier == LLMTier.LARGE_20B.value and self._tier3_blocked:
                return {"approved": False, "reason": "tier3_blocked_daily_critical", "meta": {"cost_inr": 0.0}}

            # Alert thresholds
            if daily_total >= COST_ALERT_CRITICAL_DAILY_INR:
                self._tier3_blocked = True
                await self._alert("DAILY_CRITICAL", amount_inr, tier)
            elif daily_total >= COST_ALERT_WARN_DAILY_INR:
                await self._alert("DAILY_WARN", amount_inr, tier)

            return {"approved": True, "meta": {"cost_inr": 0.0}}

    async def _record_spend(self, payload: dict) -> dict:
        """Record actual spend after a task completes."""
        amount_inr = float(payload.get("cost_inr", 0.0))
        tier = payload.get("tier", "UNKNOWN")
        agent_name = payload.get("agent_name", "unknown")

        async with self._lock:
            today = datetime.now(timezone.utc).date()
            self._daily_spend[today] += amount_inr
            self._monthly_spend += amount_inr
            self._tier_spend[tier] += amount_inr
            self._agent_spend[agent_name] += amount_inr

        return {"recorded": True, "meta": {"cost_inr": 0.0}}

    async def _get_status(self, _: dict) -> dict:
        today = datetime.now(timezone.utc).date()
        return {
            "result": {
                "daily_spend_inr": self._daily_spend[today],
                "monthly_spend_inr": self._monthly_spend,
                "monthly_cap_inr": BUDGET_CAP_INR,
                "monthly_remaining_inr": BUDGET_CAP_INR - self._monthly_spend,
                "tier3_blocked": self._tier3_blocked,
                "spend_by_tier": dict(self._tier_spend),
                "spend_by_agent": dict(sorted(
                    self._agent_spend.items(), key=lambda x: -x[1]
                )[:10]),   # Top 10 spenders
            },
            "meta": {"cost_inr": 0.0}
        }

    async def _get_projection(self, _: dict) -> dict:
        today = datetime.now(timezone.utc).date()
        days_elapsed = (today - self._month_start).days + 1
        burn_rate = self._monthly_spend / max(days_elapsed, 1)
        projected_monthly = burn_rate * 30
        days_until_exhaustion = (
            (BUDGET_CAP_INR - self._monthly_spend) / burn_rate
            if burn_rate > 0 else None
        )
        return {
            "result": CostProjection(
                period_days=30,
                burn_rate_inr_per_day=burn_rate,
                total_projected_inr=projected_monthly,
                budget_remaining_inr=BUDGET_CAP_INR - self._monthly_spend,
                days_until_exhaustion=days_until_exhaustion,
                confidence=0.85,
                generated_at=datetime.now(timezone.utc),
                tier_breakdown=dict(self._tier_spend),
                projection_id=str(uuid.uuid4()),
            ).model_dump(),
            "meta": {"cost_inr": 0.0}
        }

    async def _alert(self, alert_type: str, amount: float, tier: str) -> None:
        await self.event_bus.publish("budget.alert", AgentMessage(
            sender_id=self.id,
            payload={
                "alert_type": alert_type,
                "amount_inr": amount,
                "tier": tier,
                "daily_total": self._daily_spend[datetime.now(timezone.utc).date()],
                "monthly_total": self._monthly_spend,
            }
        ))
```

---

## 2. Cost Recording Pattern (All Workers)

```python
# Pattern: Every worker/agent MUST call record_spend after process()
# This is enforced by the @cost_tracker decorator:

def cost_tracker(func):
    async def wrapper(self, *args, **kwargs):
        result = await func(self, *args, **kwargs)
        cost = result.get("meta", {}).get("cost_inr", 0.0)
        if cost > 0 and hasattr(self, "budget_agent"):
            await self.budget_agent.execute("record_spend", {
                "cost_inr": cost,
                "tier": self.tier.value,
                "agent_name": self.name,
            })
        return result
    return wrapper
```

---

## 3. Monthly Reset Logic

```python
# BudgetManagerAgent resets daily at midnight UTC
# Monthly spend resets on the 1st of each month
# Manual reset available via execute("reset_daily", {})

async def _auto_reset_loop(self) -> None:
    while True:
        now = datetime.now(timezone.utc)
        # Reset tier3_blocked at midnight
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((midnight - now).total_seconds())
        async with self._lock:
            self._tier3_blocked = False
        logger.info("Daily budget reset — Tier-3 unblocked")
```

---

## 4. Budget Dashboard Data

```python
# For Streamlit portal (portal-designer skill)
BUDGET_DASHBOARD_METRICS = {
    "gauge_monthly_burn":   "₹X of ₹500 used (X%)",
    "bar_spend_by_tier":    "Tier-1/2/3/External breakdown",
    "line_daily_spend":     "30-day daily spend history",
    "table_top_spenders":   "Top 10 agents/workers by spend",
    "alert_banner":         "WARN/CRITICAL/BLOCKED status",
    "projection_card":      "Days until budget exhaustion",
}
```

---

## 5. Budget Test Requirements

```python
# tests/unit/test_budget_manager_agent.py must cover:
class TestBudgetApproval:
    async def test_approves_within_budget(self, agent): ...
    async def test_blocks_at_monthly_cap(self, agent): ...
    async def test_blocks_tier3_at_daily_critical(self, agent): ...
    async def test_allows_tier1_when_tier3_blocked(self, agent): ...

class TestCostRecording:
    async def test_records_cost_per_tier(self, agent): ...
    async def test_daily_total_accumulates(self, agent): ...
    async def test_monthly_total_accumulates(self, agent): ...

class TestAlerts:
    async def test_publishes_warn_alert(self, agent, mock_bus): ...
    async def test_publishes_critical_alert(self, agent, mock_bus): ...

class TestProjection:
    async def test_burn_rate_calculation(self, agent): ...
    async def test_days_until_exhaustion(self, agent): ...
    async def test_zero_spend_projection(self, agent): ...   # Edge: no division by zero
```

---

## Related Skills
- `financial-analyst` — Cost projections, ROI, pricing
- `swarm-orchestrator` — SwarmMaster uses budget gate per task
- `supervisor-designer` — Supervisors have domain budget sub-caps
- `portal-designer` — Budget dashboard visualization

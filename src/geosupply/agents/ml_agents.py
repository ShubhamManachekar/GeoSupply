"""ML domain agents — Layer 3 wrappers for MLSupervisor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class StressScoreAgent(BaseAgent):
    name = "StressScoreAgent"
    domain = "ml"
    capabilities = {"ML_STRESS_SCORE"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.supplier_worker import SupplierWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SupplierWorker().process({**payload, "trace_id": trace_id})
        r = result.get("result", {})
        vendor_score: float = float(r.get("vendor_score", 0.5))
        sanctioned: bool = bool(r.get("sanctioned", False))
        stress_score = round((1 - vendor_score) * 0.7 + (0.3 if sanctioned else 0.0), 4)
        return {
            "result": {
                "stress_score": stress_score,
                "vendor_score": vendor_score,
                "sanctioned": sanctioned,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class ConflictPredictAgent(BaseAgent):
    name = "ConflictPredictAgent"
    domain = "ml"
    capabilities = {"ML_CONFLICT_PREDICT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.supplier_worker import SupplierWorker
        from geosupply.workers.sanctions_worker import SanctionsWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        supplier_r, sanctions_r = await asyncio.gather(
            SupplierWorker().process({**payload, "trace_id": trace_id}),
            SanctionsWorker().process({**payload, "trace_id": trace_id}),
        )
        vendor_score: float = float(supplier_r.get("result", {}).get("vendor_score", 0.5))
        sanctions_count: int = int(sanctions_r.get("result", {}).get("matches", 0))
        conflict_risk = round(
            (1 - vendor_score) * 0.6 + min(1.0, sanctions_count * 0.1) * 0.4, 4
        )
        cost = (
            supplier_r.get("meta", {}).get("cost_inr", 0.0)
            + sanctions_r.get("meta", {}).get("cost_inr", 0.0)
        )
        return {
            "result": {
                "conflict_risk": conflict_risk,
                "vendor_score": vendor_score,
                "sanctions_count": sanctions_count,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": round(cost, 6),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class SupplierRankAgent(BaseAgent):
    name = "SupplierRankAgent"
    domain = "ml"
    capabilities = {"ML_SUPPLIER_RANK"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.supplier_worker import SupplierWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SupplierWorker().process({**payload, "task": "rank", "trace_id": trace_id})
        r = result.get("result", {})
        vendors = r.get("vendors", [])
        if not vendors:
            # Build from single vendor_score if no list
            vendor_score = r.get("vendor_score", 0.5)
            vendor_name = payload.get("vendor", "unknown")
            vendors = [{"name": vendor_name, "score": vendor_score}]
        ranked = sorted(vendors, key=lambda v: v.get("score", 0.0), reverse=True)
        return {
            "result": {"ranked_vendors": ranked},
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class SanctionClassifyAgent(BaseAgent):
    name = "SanctionClassifyAgent"
    domain = "ml"
    capabilities = {"ML_SANCTION_CLASSIFY"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.sanctions_worker import SanctionsWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SanctionsWorker().process({**payload, "trace_id": trace_id})
        r = result.get("result", {})
        matches: int = int(r.get("matches", 0))
        severity: str = str(r.get("severity", "low"))
        if matches > 0 and severity == "high":
            classification = "BLOCKED"
        elif matches > 0:
            classification = "WATCHLIST"
        else:
            classification = "CLEAR"
        return {
            "result": {
                "classification": classification,
                "matches": matches,
                "severity": severity,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

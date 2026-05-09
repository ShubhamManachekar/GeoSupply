"""Intel domain agents — Layer 3 wrappers for IntelSupervisor."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SupplierAgent(BaseAgent):
    name = "SupplierAgent"
    domain = "intel"
    capabilities = {"SUPPLY_CHAIN_RISK", "DEPENDENCY_MAP", "VENDOR_SCORE"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.supplier_worker import SupplierWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SupplierWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class SanctionsAgent(BaseAgent):
    name = "SanctionsAgent"
    domain = "intel"
    capabilities = {"SANCTIONS_CHECK", "ENTITY_SCREEN", "OFAC_LOOKUP"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.sanctions_worker import SanctionsWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SanctionsWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class CyberAgent(BaseAgent):
    name = "CyberAgent"
    domain = "intel"
    capabilities = {"CYBER_THREAT", "MITRE_CLASSIFY", "APT_DETECT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.cyber_threat_worker import CyberThreatWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await CyberThreatWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class VerifierAgent(BaseAgent):
    name = "VerifierAgent"
    domain = "intel"
    capabilities = {"CLAIM_VERIFY", "EVIDENCE_CHECK", "CONTRADICTION_DETECT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.verifier_worker import VerifierWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await VerifierWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class AuthorAgent(BaseAgent):
    name = "AuthorAgent"
    domain = "intel"
    capabilities = {"AUTHOR_CLASSIFY", "BOT_DETECT", "PROPAGANDA_FLAG"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.author_worker import AuthorWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await AuthorWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

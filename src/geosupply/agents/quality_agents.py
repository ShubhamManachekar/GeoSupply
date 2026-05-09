"""Quality domain agents — Layer 3 wrappers for QualitySupervisor."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class NLPAgent(BaseAgent):
    name = "NLPAgent"
    domain = "quality"
    capabilities = {"NLP_PIPELINE"}

    async def execute(self, task: dict) -> dict:
        from geosupply.subagents.nlp_pipeline_subagent import NLPPipelineSubAgent
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await NLPPipelineSubAgent().run({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class HallucinationAgent(BaseAgent):
    name = "HallucinationAgent"
    domain = "quality"
    capabilities = {"HALLUCINATION_CHECK"}

    async def execute(self, task: dict) -> dict:
        from geosupply.subagents.hallucination_check_subagent import HallucinationCheckSubAgent
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await HallucinationCheckSubAgent().run({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class SourceCredAgent(BaseAgent):
    name = "SourceCredAgent"
    domain = "quality"
    capabilities = {"SOURCE_CRED", "DOMAIN_TRUST", "STRIKE_REGISTRY"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.source_cred_worker import SourceCredWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await SourceCredWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

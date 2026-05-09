"""India domain agents — Layer 3 wrappers for IndiaSupervisor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class IndiaPortAgent(BaseAgent):
    name = "IndiaPortAgent"
    domain = "india"
    capabilities = {"INDIA_PORT_STATUS"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.india_api_worker import IndiaAPIWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await IndiaAPIWorker().process(
            {**payload, "query_type": "port_status", "trace_id": trace_id}
        )
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class IndiaMonsoonAgent(BaseAgent):
    name = "IndiaMonsoonAgent"
    domain = "india"
    capabilities = {"INDIA_MONSOON_IMPACT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.india_api_worker import IndiaAPIWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await IndiaAPIWorker().process(
            {**payload, "query_type": "monsoon_impact", "trace_id": trace_id}
        )
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class IndiaULIPAgent(BaseAgent):
    name = "IndiaULIPAgent"
    domain = "india"
    capabilities = {"INDIA_ULIP_QUERY"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.india_api_worker import IndiaAPIWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await IndiaAPIWorker().process(
            {**payload, "query_type": "ulip_query", "trace_id": trace_id}
        )
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class IndiaPoliticalAgent(BaseAgent):
    name = "IndiaPoliticalAgent"
    domain = "india"
    capabilities = {"INDIA_POLITICAL_RISK"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.sentiment_worker import SentimentWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        ner_r, sentiment_r = await asyncio.gather(
            NERWorker().process({"text": text, "trace_id": trace_id}),
            SentimentWorker().process({"text": text, "trace_id": trace_id}),
        )
        entities = ner_r.get("result", {}).get("entities", [])
        political_entities = [
            e for e in entities
            if e.get("type", "") in {"PERSON", "ORG", "GPE"}
        ]
        polarity: float = sentiment_r.get("result", {}).get("polarity", 0.0)
        political_risk = round(
            max(0.0, -polarity) * min(1.0, len(political_entities) * 0.2 + 0.3), 4
        )
        cost = (
            ner_r.get("meta", {}).get("cost_inr", 0.0)
            + sentiment_r.get("meta", {}).get("cost_inr", 0.0)
        )
        return {
            "result": {
                "political_risk": political_risk,
                "polarity": polarity,
                "political_entities": [e.get("text", "") for e in political_entities],
            },
            "meta": {
                "agent": self.name,
                "cost_inr": round(cost, 6),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

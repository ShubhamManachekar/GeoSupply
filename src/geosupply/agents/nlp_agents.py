"""NLP domain agents — Layer 3 wrappers for NLPSupervisor."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SentimentAgent(BaseAgent):
    name = "SentimentAgent"
    domain = "nlp"
    capabilities = {"NLP_SENTIMENT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.sentiment_worker import SentimentWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        result = await SentimentWorker().process({"text": text, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class NERAgent(BaseAgent):
    name = "NERAgent"
    domain = "nlp"
    capabilities = {"NLP_NER"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.ner_worker import NERWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        result = await NERWorker().process({"text": text, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class ClaimAgent(BaseAgent):
    name = "ClaimAgent"
    domain = "nlp"
    capabilities = {"NLP_CLAIM"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.claim_worker import ClaimWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        result = await ClaimWorker().process({"text": text, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class TranslationAgent(BaseAgent):
    name = "TranslationAgent"
    domain = "nlp"
    capabilities = {"NLP_TRANSLATION"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.translation_worker import TranslationWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        result = await TranslationWorker().process({"text": text, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class PropagandaAgent(BaseAgent):
    name = "PropagandaAgent"
    domain = "nlp"
    capabilities = {"NLP_PROPAGANDA"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.propaganda_worker import PropagandaWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        result = await PropagandaWorker().process({"text": text, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""Ingestion domain agents — Layer 3 wrappers for IngestionSupervisor."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class NewsAgent(BaseAgent):
    name = "NewsAgent"
    domain = "ingestion"
    capabilities = {"INGEST_NEWS", "INGEST_ANY"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.news_worker import NewsWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await NewsWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class IndiaAPIAgent(BaseAgent):
    name = "IndiaAPIAgent"
    domain = "ingestion"
    capabilities = {"INGEST_INDIA_API"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.india_api_worker import IndiaAPIWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await IndiaAPIWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class TelegramAgent(BaseAgent):
    name = "TelegramAgent"
    domain = "ingestion"
    capabilities = {"INGEST_TELEGRAM"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.telegram_worker import TelegramWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await TelegramWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class AISAgent(BaseAgent):
    name = "AISAgent"
    domain = "ingestion"
    capabilities = {"INGEST_AIS"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.ais_worker import AISWorker
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await AISWorker().process({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

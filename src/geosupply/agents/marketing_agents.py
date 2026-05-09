"""Marketing domain agents — Layer 3 wrappers for MarketingSupervisor."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent
from geosupply.config import SQLITE_PATH

logger = logging.getLogger(__name__)


class TweetGenAgent(BaseAgent):
    name = "TweetGenAgent"
    domain = "marketing"
    capabilities = {"MKT_TWEET_GEN"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.claim_worker import ClaimWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        ner_r, claim_r = await asyncio.gather(
            NERWorker().process({"text": text, "trace_id": trace_id}),
            ClaimWorker().process({"text": text, "trace_id": trace_id}),
        )
        entities = [e.get("text", "") for e in ner_r.get("result", {}).get("entities", [])[:3]]
        claims = claim_r.get("result", {}).get("claims", [])
        top_claim = claims[0] if claims else text[:100]
        tags = " ".join(f"#{e.replace(' ', '')}" for e in entities if e)
        tweet = f"{top_claim[:200]} {tags}"[:280]
        cost = (
            ner_r.get("meta", {}).get("cost_inr", 0.0)
            + claim_r.get("meta", {}).get("cost_inr", 0.0)
        )
        return {
            "result": {"tweet": tweet, "char_count": len(tweet)},
            "meta": {
                "agent": self.name,
                "cost_inr": round(cost, 6),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class PredictionPostAgent(BaseAgent):
    name = "PredictionPostAgent"
    domain = "marketing"
    capabilities = {"MKT_PREDICTION_POST"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.sentiment_worker import SentimentWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        ner_r, sentiment_r = await asyncio.gather(
            NERWorker().process({"text": text, "trace_id": trace_id}),
            SentimentWorker().process({"text": text, "trace_id": trace_id}),
        )
        entities = [e.get("text", "") for e in ner_r.get("result", {}).get("entities", [])[:2]]
        polarity: float = sentiment_r.get("result", {}).get("polarity", 0.0)
        prediction = ""
        if polarity < -0.3:
            entity_str = entities[0] if entities else "supply chain"
            prediction = f"PREDICTION: {entity_str} supply disruption likely"
        cost = (
            ner_r.get("meta", {}).get("cost_inr", 0.0)
            + sentiment_r.get("meta", {}).get("cost_inr", 0.0)
        )
        return {
            "result": {"prediction": prediction, "polarity": polarity, "triggered": bool(prediction)},
            "meta": {
                "agent": self.name,
                "cost_inr": round(cost, 6),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class AnalyticsAgent(BaseAgent):
    name = "AnalyticsAgent"
    domain = "marketing"
    capabilities = {"MKT_ANALYTICS"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        top_routes: list[dict] = []
        cost_by_source: list[dict] = []
        total_tasks_24h: int = 0
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                rows = conn.execute(
                    "SELECT message, COUNT(*) as freq FROM swarm_logs "
                    "GROUP BY message ORDER BY freq DESC LIMIT 10"
                ).fetchall()
                top_routes = [{"route": row[0], "frequency": row[1]} for row in rows]

                rows2 = conn.execute(
                    "SELECT agent_name, SUM(cost_inr) FROM swarm_logs "
                    "GROUP BY agent_name ORDER BY SUM(cost_inr) DESC LIMIT 10"
                ).fetchall()
                cost_by_source = [
                    {"source": row[0], "total_cost_inr": row[1] or 0.0} for row in rows2
                ]

                row3 = conn.execute(
                    "SELECT COUNT(*) FROM swarm_logs "
                    "WHERE timestamp >= datetime('now', '-1 day')"
                ).fetchone()
                total_tasks_24h = int(row3[0] or 0)
        except sqlite3.OperationalError as exc:
            logger.warning("AnalyticsAgent: SQLite query failed: %s", exc)
        return {
            "result": {
                "top_routes": top_routes,
                "cost_by_source": cost_by_source,
                "total_tasks_24h": total_tasks_24h,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class ContentGenAgent(BaseAgent):
    name = "ContentGenAgent"
    domain = "marketing"
    capabilities = {"MKT_CONTENT_GEN"}

    async def execute(self, task: dict) -> dict:
        from geosupply.workers.claim_worker import ClaimWorker
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.sentiment_worker import SentimentWorker
        trace_id = task.get("trace_id", "")
        text = task.get("payload", {}).get("text", task.get("text", ""))
        claim_r, ner_r, sentiment_r = await asyncio.gather(
            ClaimWorker().process({"text": text, "trace_id": trace_id}),
            NERWorker().process({"text": text, "trace_id": trace_id}),
            SentimentWorker().process({"text": text, "trace_id": trace_id}),
        )
        claims = claim_r.get("result", {}).get("claims", [])
        entities = [e.get("text", "") for e in ner_r.get("result", {}).get("entities", [])[:5]]
        polarity: float = sentiment_r.get("result", {}).get("polarity", 0.0)
        if polarity < -0.5:
            risk_level = "HIGH"
        elif polarity < -0.1:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        report = {
            "title": f"Intelligence Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "key_entities": entities,
            "claims": claims[:5],
            "sentiment": {"polarity": polarity},
            "risk_level": risk_level,
        }
        cost = (
            claim_r.get("meta", {}).get("cost_inr", 0.0)
            + ner_r.get("meta", {}).get("cost_inr", 0.0)
            + sentiment_r.get("meta", {}).get("cost_inr", 0.0)
        )
        return {
            "result": report,
            "meta": {
                "agent": self.name,
                "cost_inr": round(cost, 6),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

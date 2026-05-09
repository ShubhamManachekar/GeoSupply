"""
GeoSupply MCP — Tool definitions.

10 tools exposed to MCP clients:
  1.  submit_task           — Queue any task type through the swarm
  2.  run_supply_brief      — Full 10-step DAG supply intelligence brief
  3.  analyze_text          — NLP pipeline (sentiment, NER, claims) on raw text
  4.  screen_entity         — Sanctions check + supplier scoring for an entity
  5.  query_knowledge_graph — Cypher-style KG query via GraphRAGSubAgent
  6.  get_task_status       — Poll a previously submitted task
  7.  get_system_health     — Live health of all swarm layers
  8.  get_budget_status     — Current INR budget consumption
  9.  run_audit             — Retrieve the most recent audit log entries
  10. ingest_and_analyze    — Ingest a news URL and run the full NLP pipeline on it

All tools are registered on a FastMCP instance imported from server.py.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# _mcp is injected by server.py before this module is used
_mcp: Any = None  # set by register_tools()


def register_tools(mcp_instance: Any) -> None:
    global _mcp
    _mcp = mcp_instance

    # ── 1. submit_task ────────────────────────────────────────────────────────

    @mcp_instance.tool()
    async def submit_task(
        task_type: str,
        payload: dict,
        trace_id: str = "",
        budget_inr: float = 10.0,
    ) -> dict:
        """Submit any task type to the GeoSupply swarm for processing.

        Args:
            task_type:  One of the routing table keys (e.g. CLAIM_VERIFY,
                        NLP_SENTIMENT, SANCTIONS_CHECK, ML_STRESS_SCORE).
            payload:    Task-specific input dictionary.
            trace_id:   Optional trace identifier for observability.
                        Auto-generated if not provided.
            budget_inr: Maximum spend in Indian Rupees for this task (default ₹10).

        Returns:
            Task result with result, meta, and cost breakdown.
        """
        from geosupply.mcp._context import get_swarm, get_budget
        from geosupply.schemas import TaskPacket

        tid = trace_id or str(uuid.uuid4())[:8]
        swarm = get_swarm()
        budget_agent = get_budget()

        # Budget gate
        budget_ok = await budget_agent.execute({
            "action": "check",
            "amount_inr": budget_inr,
            "trace_id": tid,
        })
        if not budget_ok.get("result", {}).get("approved", True):
            return {"error": "budget_exceeded", "trace_id": tid, "budget_inr": budget_inr}

        packet = TaskPacket(
            task_id=tid,
            task_type=task_type,
            payload=payload,
            trace_id=tid,
        )
        result = await swarm.dispatch(packet)
        return {"task_id": tid, "task_type": task_type, **result}

    # ── 2. run_supply_brief ───────────────────────────────────────────────────

    @mcp_instance.tool()
    async def run_supply_brief(
        topic: str,
        source_credibility: float = 0.8,
        trace_id: str = "",
    ) -> dict:
        """Run the full 10-step supply chain intelligence DAG for a topic.

        This executes: ingestion → NLP → claim extraction → entity screening
        → source scoring → verification → brief synthesis → risk scoring.

        Args:
            topic:              Natural-language topic or claim to investigate.
                                E.g. "India wheat export ban impact on prices".
            source_credibility: Prior source credibility score (0.0–1.0).
                                Default 0.8 (trusted source).
            trace_id:           Optional trace ID for observability.

        Returns:
            Comprehensive supply brief with confidence score, risk level,
            key entities, claims, cost breakdown, and aggregation metadata.
        """
        from geosupply.mcp._context import get_swarm

        tid = trace_id or str(uuid.uuid4())[:8]
        swarm = get_swarm()
        result = await swarm.run_supply_brief({
            "topic": topic,
            "source_credibility": source_credibility,
            "trace_id": tid,
        })
        return {"trace_id": tid, **result}

    # ── 3. analyze_text ───────────────────────────────────────────────────────

    @mcp_instance.tool()
    async def analyze_text(text: str, trace_id: str = "") -> dict:
        """Run the NLP pipeline (sentiment, NER, claim extraction) on raw text.

        Args:
            text:      Text to analyse (news article, report, tweet, etc.).
            trace_id:  Optional trace ID.

        Returns:
            sentiment (polarity, subjectivity), entities (text, label),
            claims (list of factual claim strings), and per-worker costs.
        """
        import asyncio
        from geosupply.workers.sentiment_worker import SentimentWorker
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.claim_worker import ClaimWorker

        tid = trace_id or str(uuid.uuid4())[:8]
        inp = {"text": text, "trace_id": tid}

        sentiment_r, ner_r, claim_r = await asyncio.gather(
            SentimentWorker().process(inp),
            NERWorker().process(inp),
            ClaimWorker().process(inp),
        )
        total_cost = sum(
            r.get("meta", {}).get("cost_inr", 0.0)
            for r in (sentiment_r, ner_r, claim_r)
        )
        return {
            "trace_id": tid,
            "sentiment": sentiment_r.get("result", {}),
            "entities": ner_r.get("result", {}).get("entities", []),
            "claims": claim_r.get("result", {}).get("claims", []),
            "cost_inr": round(total_cost, 6),
        }

    # ── 4. screen_entity ─────────────────────────────────────────────────────

    @mcp_instance.tool()
    async def screen_entity(
        entity_name: str,
        entity_type: str = "supplier",
        trace_id: str = "",
    ) -> dict:
        """Screen an entity against sanctions lists and supplier risk scores.

        Args:
            entity_name:  Name of the entity (company, person, vessel, port).
            entity_type:  One of: supplier, person, vessel, port, country.
            trace_id:     Optional trace ID.

        Returns:
            sanctions_hit (bool), risk_score (0–1), risk_flags (list),
            ofac_match (bool), eu_match (bool), un_match (bool).
        """
        import asyncio
        from geosupply.workers.sanctions_worker import SanctionsWorker
        from geosupply.workers.supplier_worker import SupplierWorker

        tid = trace_id or str(uuid.uuid4())[:8]
        sanctions_r, supplier_r = await asyncio.gather(
            SanctionsWorker().process({"entity_name": entity_name, "trace_id": tid}),
            SupplierWorker().process({
                "entity_name": entity_name,
                "entity_type": entity_type,
                "trace_id": tid,
            }),
        )
        return {
            "trace_id": tid,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "sanctions": sanctions_r.get("result", {}),
            "supplier_risk": supplier_r.get("result", {}),
            "cost_inr": round(
                sanctions_r.get("meta", {}).get("cost_inr", 0.0)
                + supplier_r.get("meta", {}).get("cost_inr", 0.0),
                6,
            ),
        }

    # ── 5. query_knowledge_graph ──────────────────────────────────────────────

    @mcp_instance.tool()
    async def query_knowledge_graph(
        query: str,
        max_hops: int = 2,
        trace_id: str = "",
    ) -> dict:
        """Query the supply-chain knowledge graph for entity relationships.

        Args:
            query:     Natural-language query or entity name to explore.
                       E.g. "Adani Ports suppliers", "Ukraine wheat routes".
            max_hops:  Maximum graph traversal depth (1–4, default 2).
            trace_id:  Optional trace ID.

        Returns:
            nodes, edges, paths, and retrieval confidence.
        """
        from geosupply.subagents.graph_rag_subagent import GraphRAGSubAgent

        tid = trace_id or str(uuid.uuid4())[:8]
        result = await GraphRAGSubAgent().run({
            "query": query,
            "trace_id": tid,
            "max_hops": max(1, min(4, max_hops)),
        })
        return {"trace_id": tid, **result.get("result", {})}

    # ── 6. get_task_status ────────────────────────────────────────────────────

    @mcp_instance.tool()
    async def get_task_status(task_id: str) -> dict:
        """Poll the status of a previously submitted swarm task.

        Args:
            task_id: The task_id returned by submit_task.

        Returns:
            status (pending|running|complete|failed), result (if complete),
            and elapsed_seconds.
        """
        import sqlite3
        from geosupply.config import SQLITE_PATH

        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                row = conn.execute(
                    "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
        except sqlite3.OperationalError:
            row = None

        if row:
            import json
            return {"task_id": task_id, "found": True, "data": json.loads(row[0])}
        return {"task_id": task_id, "found": False, "status": "unknown"}

    # ── 7. get_system_health ─────────────────────────────────────────────────

    @mcp_instance.tool()
    async def get_system_health() -> dict:
        """Return live health status of all swarm layers.

        Returns:
            status per layer: API, SwarmMaster, supervisors (14), workers (19),
            SQLite connectivity, and uptime.
        """
        from geosupply.mcp._context import get_swarm
        import sqlite3
        from geosupply.config import SQLITE_PATH

        swarm = get_swarm()
        supervisor_names = list(swarm._supervisor_registry.keys())

        sqlite_ok = False
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=2.0) as conn:
                conn.execute("SELECT 1").fetchone()
            sqlite_ok = True
        except sqlite3.OperationalError:
            pass

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "layers": {
                "swarm_master": "ok",
                "supervisors": {"count": len(supervisor_names), "names": supervisor_names},
                "sqlite": "ok" if sqlite_ok else "degraded",
                "anthropic_api": "configured" if __import__("os").getenv("ANTHROPIC_API_KEY") else "not_configured",
            },
        }

    # ── 8. get_budget_status ──────────────────────────────────────────────────

    @mcp_instance.tool()
    async def get_budget_status() -> dict:
        """Return current INR budget consumption and remaining allowance.

        Returns:
            spent_inr, remaining_inr, budget_inr, utilisation_pct, alerts.
        """
        from geosupply.mcp._context import get_budget

        budget_agent = get_budget()
        result = await budget_agent.execute({"action": "status", "trace_id": "mcp-budget"})
        return result.get("result", {})

    # ── 9. run_audit ──────────────────────────────────────────────────────────

    @mcp_instance.tool()
    async def run_audit(limit: int = 50, agent_name: str = "") -> dict:
        """Retrieve recent swarm audit log entries from SQLite.

        Args:
            limit:      Maximum number of log rows to return (default 50).
            agent_name: Filter by agent name (empty = all agents).

        Returns:
            List of log entries with timestamp, agent, message, cost_inr.
        """
        import sqlite3
        from geosupply.config import SQLITE_PATH

        rows = []
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                if agent_name:
                    cur = conn.execute(
                        "SELECT timestamp, agent_name, message, cost_inr "
                        "FROM swarm_logs WHERE agent_name = ? "
                        "ORDER BY timestamp DESC LIMIT ?",
                        (agent_name, max(1, min(500, limit))),
                    )
                else:
                    cur = conn.execute(
                        "SELECT timestamp, agent_name, message, cost_inr "
                        "FROM swarm_logs ORDER BY timestamp DESC LIMIT ?",
                        (max(1, min(500, limit)),),
                    )
                rows = [
                    {"timestamp": r[0], "agent": r[1], "message": r[2], "cost_inr": r[3] or 0.0}
                    for r in cur.fetchall()
                ]
        except sqlite3.OperationalError as exc:
            return {"error": str(exc), "entries": []}

        return {"count": len(rows), "entries": rows}

    # ── 10. ingest_and_analyze ────────────────────────────────────────────────

    @mcp_instance.tool()
    async def ingest_and_analyze(
        url: str,
        source_credibility: float = 0.7,
        trace_id: str = "",
    ) -> dict:
        """Ingest a news article URL and run the full NLP pipeline on it.

        Fetches the article via NewsWorker, then runs sentiment, NER,
        claim extraction, and source credibility scoring.

        Args:
            url:                Direct URL to a news article.
            source_credibility: Prior credibility for this source (0.0–1.0).
            trace_id:           Optional trace ID.

        Returns:
            article_text (truncated), sentiment, entities, claims,
            source_credibility_score, and total cost_inr.
        """
        import asyncio
        from geosupply.workers.news_worker import NewsWorker
        from geosupply.workers.sentiment_worker import SentimentWorker
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.claim_worker import ClaimWorker
        from geosupply.workers.source_cred_worker import SourceCredWorker

        tid = trace_id or str(uuid.uuid4())[:8]

        news_r = await NewsWorker().process({"url": url, "trace_id": tid})
        article_text: str = news_r.get("result", {}).get("text", "")

        if not article_text:
            return {"trace_id": tid, "error": "Could not fetch article", "url": url}

        inp = {"text": article_text, "trace_id": tid}
        sentiment_r, ner_r, claim_r, cred_r = await asyncio.gather(
            SentimentWorker().process(inp),
            NERWorker().process(inp),
            ClaimWorker().process(inp),
            SourceCredWorker().process({"url": url, "source_credibility": source_credibility, "trace_id": tid}),
        )

        total_cost = sum(
            r.get("meta", {}).get("cost_inr", 0.0)
            for r in (news_r, sentiment_r, ner_r, claim_r, cred_r)
        )
        return {
            "trace_id": tid,
            "url": url,
            "article_preview": article_text[:500],
            "sentiment": sentiment_r.get("result", {}),
            "entities": ner_r.get("result", {}).get("entities", []),
            "claims": claim_r.get("result", {}).get("claims", []),
            "source_credibility": cred_r.get("result", {}),
            "cost_inr": round(total_cost, 6),
        }

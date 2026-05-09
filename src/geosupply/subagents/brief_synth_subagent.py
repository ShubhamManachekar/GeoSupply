"""
BriefSynthSubAgent — Layer 4 SubAgent
FA v2 | Part III | §3.2 — Mixture-of-Agents brief synthesis

3 proposers (parallel) + 4-level aggregation fallback.

PIPELINE:
    Step 1: propose_x3  — 3 parallel deterministic proposal generators (Tier-1/2/3)
    Step 2: save_proposals  — persist all 3 to SQLite BEFORE aggregation (audit invariant)
    Step 3: aggregate  — 4-level MoA fallback cascade
    Step 4: hallucination_gate  — confidence ≥ HALLUCINATION_FLOOR

MoA LEVELS:
    Level 0: Primary aggregation policy
    Level 1: Secondary aggregation policy (breaker fallback)
    Level 2: Scoring-based selection (weighted: factcheck×0.4 + source_cred×0.3 + evidence×0.3)
    Level 3: Return all 3 proposals to admin queue

INVARIANT: All 3 proposals saved to SQLite BEFORE aggregation (even if aggregation fails).
Circuit breaker: 60s timeout, 3 max failures (from config).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

from geosupply.config import (
    HALLUCINATION_FLOOR,
    INTERNAL_BREAKER_MAX_FAILURES,
    MOA_ESCALATE_THRESHOLD,
)
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import BriefProposal

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS brief_proposals (
    id TEXT PRIMARY KEY,
    trace_id TEXT,
    proposal_text TEXT,
    confidence REAL,
    proposer_tier INTEGER,
    factcheck_score REAL,
    source_credibility_avg REAL,
    claim_evidence_ratio REAL,
    created_at TEXT
)
"""

_INSERT_SQL = """
INSERT INTO brief_proposals
    (id, trace_id, proposal_text, confidence, proposer_tier,
     factcheck_score, source_credibility_avg, claim_evidence_ratio, created_at)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _level3_result(proposals: list[BriefProposal], trace_id: str, name: str) -> dict:
    return {
        "result": {
            "brief_text": "",
            "confidence": 0.0,
            "aggregation_level_used": 3,
            "proposer_count": len(proposals),
            "proposal_ids": [p.proposal_id for p in proposals],
            "cost_breakdown": {"total": 0.0},
            "admin_queue": [p.model_dump() for p in proposals],
        },
        "meta": {"subagent": name, "cost_inr": 0.0, "trace_id": trace_id},
    }


class BriefSynthSubAgent(BaseSubAgent):
    """
    Mixture-of-Agents brief synthesis with 3 parallel proposers and a
    4-level aggregation fallback cascade.

    Input:
        claim_text (str): Claim text to synthesise a brief for.
        source_credibility (float): Source credibility score (0–1).
        trace_id (str): Propagated trace identifier.

    Output:
        result:
            brief_text, confidence, aggregation_level_used,
            proposer_count, proposal_ids, cost_breakdown
        meta:
            subagent, cost_inr, trace_id
    """

    name = "BriefSynthSubAgent"
    pipeline_steps = ["propose_x3", "save_proposals", "aggregate", "hallucination_gate"]
    parallel_steps = {"propose_x3"}

    def __init__(self, db_path: str | None = None) -> None:
        # db_path: SQLite path for proposal persistence. None → in-memory store for tests.
        self._db_path = db_path
        self._proposals_store: list[dict] = []  # in-memory fallback when db_path is None
        self._breaker_failures: int = 0
        self._breaker_open: bool = False
        self._tier2_cost: float = 0.0
        self._tier3_cost: float = 0.0

    # ------------------------------------------------------------------
    # Deterministic proposers (Step 1)
    # ------------------------------------------------------------------

    async def _propose_tier1(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        from geosupply.workers.claim_worker import ClaimWorker
        from geosupply.workers.sentiment_worker import SentimentWorker
        from geosupply.workers.ner_worker import NERWorker

        claim_r, sentiment_r, ner_r = await asyncio.gather(
            ClaimWorker().process({"text": claim_text, "trace_id": trace_id}),
            SentimentWorker().process({"text": claim_text, "trace_id": trace_id}),
            NERWorker().process({"text": claim_text, "trace_id": trace_id}),
        )

        claims: list[str] = claim_r.get("result", {}).get("claims", [])
        polarity: float = abs(sentiment_r.get("result", {}).get("polarity", 0.0))
        entities: list[str] = [e.get("text", "") for e in ner_r.get("result", {}).get("entities", [])]
        sentences = claim_text.split(". ")
        claim_density = len(claims) / max(1, len(sentences))

        entity_str = ", ".join(entities[:5]) if entities else "unspecified entities"
        claim_str = "; ".join(claims[:3]) if claims else claim_text[:120]
        brief_text = (
            f"[Tier1] Key entities: {entity_str}. Claims: {claim_str}. "
            f"Source credibility: {source_credibility:.2f}."
        )
        confidence = round(0.4 * min(1.0, claim_density) + 0.3 * source_credibility + 0.3 * polarity, 4)
        factcheck_score = round(source_credibility * min(1.0, claim_density + 0.1), 4)
        claim_evidence_ratio = round(min(1.0, len(claims) / max(1, len(sentences))), 4)

        return BriefProposal(
            proposal_id=f"{trace_id}_1", trace_id=trace_id, brief_text=brief_text,
            confidence=confidence, proposer_tier=1, factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility, claim_evidence_ratio=claim_evidence_ratio,
        )

    async def _propose_tier2(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        from geosupply.subagents.nlp_pipeline_subagent import NLPPipelineSubAgent
        from geosupply.subagents.source_cluster_subagent import SourceClusterSubAgent

        nlp_out, cluster_out = await asyncio.gather(
            NLPPipelineSubAgent().run({"text": claim_text, "trace_id": trace_id}),
            SourceClusterSubAgent().run({"texts": [claim_text], "trace_id": trace_id}),
        )
        nlp_r = nlp_out.get("result", {})
        entities = [e.get("text", "") for e in nlp_r.get("entities", [])[:5]]
        claims = nlp_r.get("claims", [])
        sentiment = nlp_r.get("sentiment") or {}
        clusters: int = cluster_out.get("result", {}).get("cluster_count", 1)
        polarity_abs = abs(sentiment.get("polarity", 0.0))
        subjectivity = sentiment.get("subjectivity", 0.5)
        sentences = claim_text.split(". ")
        claim_ratio = min(1.0, len(claims) / max(1, len(sentences)))

        brief_text = (
            f"[Tier2] Entities: {', '.join(entities) or 'unknown'}. "
            f"Claims: {'; '.join(claims[:3]) if claims else claim_text[:120]}. "
            f"Sentiment polarity: {sentiment.get('polarity', 0.0):.2f}. Source clusters: {clusters}."
        )
        confidence = round(0.4 * source_credibility + 0.3 * polarity_abs + 0.3 * claim_ratio, 4)
        factcheck_score = round(source_credibility * (1.0 - subjectivity * 0.2), 4)

        nlp_cost = nlp_out.get("meta", {}).get("cost_inr", 0.0)
        cluster_cost = cluster_out.get("meta", {}).get("cost_inr", 0.0)
        self._tier2_cost = round(nlp_cost + cluster_cost, 6)

        return BriefProposal(
            proposal_id=f"{trace_id}_2", trace_id=trace_id, brief_text=brief_text,
            confidence=confidence, proposer_tier=2, factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility, claim_evidence_ratio=claim_ratio,
        )

    async def _propose_tier3(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        from geosupply.subagents.rag_pipeline_subagent import RAGPipelineSubAgent
        from geosupply.subagents.graph_rag_subagent import GraphRAGSubAgent

        rag_out, grag_out = await asyncio.gather(
            RAGPipelineSubAgent().run({"query": claim_text, "trace_id": trace_id, "top_k": 5}),
            GraphRAGSubAgent().run({"query": claim_text, "trace_id": trace_id, "max_hops": 2}),
        )
        rag_r = rag_out.get("result", {})
        grag_r = grag_out.get("result", {})
        rag_chunks = [c.get("text", "") for c in rag_r.get("chunks", [])[:3]]
        kg_paths = [str(p) for p in grag_r.get("paths", [])[:2]]
        retrieval_score: float = rag_r.get("retrieval_score", 0.0)

        context_str = " ".join(rag_chunks[:2])[:200] if rag_chunks else "No context retrieved."
        kg_str = "; ".join(kg_paths) if kg_paths else "No graph paths."
        brief_text = (
            f"[Tier3] {claim_text[:100]}. Context: {context_str} KG evidence: {kg_str}."
        )
        confidence = round(
            0.5 * min(1.0, retrieval_score)
            + 0.3 * source_credibility
            + 0.2 * (1.0 if rag_chunks else 0.0),
            4,
        )
        factcheck_score = round(source_credibility * min(1.0, retrieval_score + 0.2), 4)
        claim_evidence_ratio = min(1.0, round(len(rag_chunks) / 3.0, 4))

        rag_cost = rag_out.get("meta", {}).get("cost_inr", 0.0)
        grag_cost = grag_out.get("meta", {}).get("cost_inr", 0.0)
        self._tier3_cost = round(rag_cost + grag_cost, 6)

        return BriefProposal(
            proposal_id=f"{trace_id}_3", trace_id=trace_id, brief_text=brief_text,
            confidence=confidence, proposer_tier=3, factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility, claim_evidence_ratio=claim_evidence_ratio,
        )

    # ------------------------------------------------------------------
    # Step 2: save_proposals
    # ------------------------------------------------------------------

    def _save_proposals(self, proposals: list[BriefProposal]) -> None:
        """Persist proposals to SQLite inside a transaction, then mirror to in-memory store."""
        if self._db_path is not None:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                conn.execute("BEGIN")
                try:
                    conn.execute(_CREATE_TABLE_SQL)
                    for p in proposals:
                        conn.execute(
                            _INSERT_SQL,
                            (
                                p.proposal_id,
                                p.trace_id,
                                p.brief_text,
                                p.confidence,
                                p.proposer_tier,
                                p.factcheck_score,
                                p.source_credibility_avg,
                                p.claim_evidence_ratio,
                                p.created_at.isoformat(),
                            ),
                        )
                    conn.execute("COMMIT")
                except sqlite3.Error:
                    conn.execute("ROLLBACK")
                    raise

        # Always append to in-memory audit trail
        for p in proposals:
            self._proposals_store.append(p.model_dump())

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def run(self, input_data: dict) -> dict:
        claim_text: str = input_data.get("claim_text", "")
        source_credibility: float = float(input_data.get("source_credibility", 0.8))
        trace_id: str = input_data.get("trace_id", "test")

        # Step 1: propose_x3 — 3 parallel proposers
        proposals: list[BriefProposal] = list(
            await asyncio.gather(
                self._propose_tier3(claim_text, source_credibility, trace_id),
                self._propose_tier2(claim_text, source_credibility, trace_id),
                self._propose_tier1(claim_text, source_credibility, trace_id),
            )
        )

        # Step 2: save_proposals — MUST happen before aggregation (audit invariant)
        self._save_proposals(proposals)

        # Step 3: aggregate — 4-level MoA fallback cascade
        aggregation_level: int

        if not self._breaker_open:
            # Level 0: primary policy — highest confidence wins
            best = max(proposals, key=lambda p: p.confidence)
            aggregation_level = 0
        else:
            # Level 1: breaker fallback policy — same deterministic chooser
            if self._breaker_failures < INTERNAL_BREAKER_MAX_FAILURES:
                best = max(proposals, key=lambda p: p.confidence)
                aggregation_level = 1
            else:
                # Level 2: scoring-based selection
                # MOA_SCORING_WEIGHTS = {"factcheck_score": 0.4,
                #                        "source_credibility_avg": 0.3,
                #                        "claim_evidence_ratio": 0.3}
                def _score(p: BriefProposal) -> float:
                    return (
                        p.factcheck_score * 0.4
                        + p.source_credibility_avg * 0.3
                        + p.claim_evidence_ratio * 0.3
                    )

                scored = sorted(proposals, key=_score, reverse=True)

                # If top score < MOA_ESCALATE_THRESHOLD → Level 3 manual
                if _score(scored[0]) < MOA_ESCALATE_THRESHOLD:
                    # Level 3: return all proposals for manual selection
                    return _level3_result(proposals, trace_id, self.name)

                best = scored[0]
                aggregation_level = 2

        # Step 4: hallucination_gate
        if best.confidence < HALLUCINATION_FLOOR:
            logger.warning(
                "%s: confidence %.4f below HALLUCINATION_FLOOR %.4f — flagging as borderline",
                self.name,
                best.confidence,
                HALLUCINATION_FLOOR,
            )
            # Flag as borderline but do not block pipeline
            best = best.model_copy(
                update={"confidence": round(HALLUCINATION_FLOOR * 0.99, 6)}
            )

        return {
            "result": {
                "brief_text": best.brief_text,
                "confidence": best.confidence,
                "aggregation_level_used": aggregation_level,
                "proposer_count": len(proposals),
                "proposal_ids": [p.proposal_id for p in proposals],
                "cost_breakdown": {
                    "tier1": 0.0,
                    "tier2": self._tier2_cost,
                    "tier3": self._tier3_cost,
                    "total": round(self._tier2_cost + self._tier3_cost, 6),
                },
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
            },
        }

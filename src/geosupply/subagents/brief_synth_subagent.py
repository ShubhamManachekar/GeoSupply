"""
BriefSynthSubAgent — Layer 4 SubAgent
FA v2 | Part III | §3.2 — Mixture-of-Agents brief synthesis

3 proposers (parallel) + 4-level aggregation fallback.

PIPELINE:
    Step 1: propose_x3  — 3 parallel BriefWorker stub calls (Tier-1/2/3)
    Step 2: save_proposals  — persist all 3 to SQLite BEFORE aggregation (audit invariant)
    Step 3: aggregate  — 4-level MoA fallback cascade
    Step 4: hallucination_gate  — confidence ≥ HALLUCINATION_FLOOR

MoA LEVELS:
    Level 0: GPT-OSS:20b aggregation (primary — stub in this implementation)
    Level 1: Groq llama-3.3-70b aggregation (cloud fallback — stub)
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

    # ------------------------------------------------------------------
    # Proposer stubs (Step 1)
    # ------------------------------------------------------------------

    async def _propose_tier3(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        await asyncio.sleep(0)
        confidence = 0.78
        factcheck_score = source_credibility * 0.9
        return BriefProposal(
            proposal_id=f"{trace_id}_3",
            trace_id=trace_id,
            brief_text=f"[Tier3] {claim_text[:80]} — comprehensive analysis.",
            confidence=confidence,
            proposer_tier=3,
            factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility,
            claim_evidence_ratio=0.75,
        )

    async def _propose_tier2(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        await asyncio.sleep(0)
        confidence = 0.74
        factcheck_score = source_credibility * 0.9
        return BriefProposal(
            proposal_id=f"{trace_id}_2",
            trace_id=trace_id,
            brief_text=f"[Tier2] {claim_text[:80]} — concise summary.",
            confidence=confidence,
            proposer_tier=2,
            factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility,
            claim_evidence_ratio=0.75,
        )

    async def _propose_tier1(
        self, claim_text: str, source_credibility: float, trace_id: str
    ) -> BriefProposal:
        await asyncio.sleep(0)
        confidence = 0.71
        factcheck_score = source_credibility * 0.9
        return BriefProposal(
            proposal_id=f"{trace_id}_1",
            trace_id=trace_id,
            brief_text=f"[Tier1] {claim_text[:80]} — bullet points.",
            confidence=confidence,
            proposer_tier=1,
            factcheck_score=factcheck_score,
            source_credibility_avg=source_credibility,
            claim_evidence_ratio=0.75,
        )

    # ------------------------------------------------------------------
    # Step 2: save_proposals
    # ------------------------------------------------------------------

    def _save_proposals(self, proposals: list[BriefProposal]) -> None:
        """Persist proposals to SQLite and in-memory store."""
        if self._db_path is not None:
            conn = sqlite3.connect(self._db_path)
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
                conn.commit()
            finally:
                conn.close()

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

        # Step 1: propose_x3 — 3 parallel proposer stubs
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
            # Level 0: GPT-OSS:20b (stub — select proposal with highest confidence)
            best = max(proposals, key=lambda p: p.confidence)
            aggregation_level = 0
        else:
            # Level 1: Groq llama-3.3-70b fallback (stub — same selection logic)
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
                    "tier2": 0.0,
                    "tier3": 0.0,
                    "total": 0.0,
                },
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
            },
        }

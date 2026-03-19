"""
FactCheckAgent — Layer 3 Agent
FA v2 | Part IV | QualitySupervisor domain

Verifies claims from the NLP pipeline using multi-source evidence
and enforces the HALLUCINATION_FLOOR (0.70) quality gate.

Capabilities: FACT_CHECK, CLAIM_VERIFY, EVIDENCE_SCORE, QUARANTINE_BRIEF
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_agent import BaseAgent
from geosupply.schemas import FactCheckResult

logger = logging.getLogger(__name__)

# Minimum sources required for a PASS verdict
MIN_SOURCES_FOR_PASS: int = 2


def _score_evidence(claims: list[str], evidence: list[str]) -> tuple[float, int]:
    """
    Simple keyword-overlap evidence scorer (deterministic, no LLM needed).

    Returns (confidence_score 0.0-1.0, evidence_count).
    Production implementation would use a cross-encoder NLI model.
    """
    if not claims or not evidence:
        return 0.0, 0

    claim_words = set(" ".join(claims).lower().split())
    total_score = 0.0
    evidence_count = 0

    for ev in evidence:
        ev_words = set(ev.lower().split())
        if not ev_words:
            continue
        overlap = len(claim_words & ev_words) / max(len(claim_words), 1)
        total_score += min(overlap * 2.0, 1.0)   # cap per-source at 1.0
        evidence_count += 1

    avg_score = total_score / max(evidence_count, 1)
    return round(min(avg_score, 1.0), 4), evidence_count


class FactCheckAgent(BaseAgent):
    """
    Verifies NLP pipeline output claims against provided evidence.

    TASK ACTIONS:
        fact_check     → verify claims with evidence list
        batch_check    → verify multiple claim groups
        health         → agent status

    HALLUCINATION_FLOOR:
        confidence < 0.70 → verdict = QUARANTINE
        confidence < 0.50 → verdict = FAIL

    OUTPUT:
        FactCheckResult schema (#29)
    """

    name = "FactCheckAgent"
    domain = "quality"
    capabilities = {"FACT_CHECK", "CLAIM_VERIFY", "EVIDENCE_SCORE", "QUARANTINE_BRIEF"}
    max_concurrent = 5

    def __init__(self) -> None:
        self._total_checked: int = 0
        self._total_quarantined: int = 0

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "fact_check")

        if action == "fact_check":
            return await self._handle_fact_check(task)
        elif action == "batch_check":
            return await self._handle_batch_check(task)
        elif action == "health":
            return self._handle_health()
        else:
            return {
                "result": {"error": f"Unknown action: {action}"},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

    async def _handle_fact_check(self, task: dict) -> dict:
        """
        Verify a single claim against provided evidence.

        task keys:
            claim_text  str   — the claim to verify
            evidence    list  — list of evidence strings
            sources     list  — source names (for attribution)
            trace_id    str
        """
        trace_id = task.get("trace_id", "unknown")
        claim_text = str(task.get("claim_text", "")).strip()
        evidence: list[str] = task.get("evidence", [])
        sources: list[str] = task.get("sources", [])

        if not claim_text:
            return {
                "result": {"error": "claim_text is required"},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        confidence, evidence_count = _score_evidence([claim_text], evidence)

        # Determine verdict
        if confidence >= HALLUCINATION_FLOOR and evidence_count >= MIN_SOURCES_FOR_PASS:
            verdict = "PASS"
        elif confidence >= 0.50:
            verdict = "UNVERIFIABLE"
        elif confidence >= HALLUCINATION_FLOOR:
            verdict = "UNVERIFIABLE"   # enough confidence but too few sources
        elif evidence_count == 0:
            verdict = "UNVERIFIABLE"
        else:
            verdict = "QUARANTINE"

        # Quarantine if confidence below floor regardless
        if confidence < HALLUCINATION_FLOOR and verdict not in ("QUARANTINE",):
            verdict = "QUARANTINE"

        result = FactCheckResult(
            claim_text=claim_text,
            verdict=verdict,
            confidence=confidence,
            evidence_count=evidence_count,
            hallucination_score=round(1.0 - confidence, 4),
            sources_checked=sources[:10],   # cap at 10
            trace_id=trace_id,
        )

        self._total_checked += 1
        if verdict == "QUARANTINE":
            self._total_quarantined += 1
            logger.warning(
                "%s: QUARANTINE — claim='%.50s' confidence=%.3f [trace=%s]",
                self.name, claim_text, confidence, trace_id,
            )

        cost = 0.002 if evidence else 0.0

        return {
            "result": result.model_dump(mode="json"),
            "meta": {
                "agent": self.name,
                "cost_inr": cost,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def _handle_batch_check(self, task: dict) -> dict:
        """Verify a list of claim dicts in sequence."""
        trace_id = task.get("trace_id", "unknown")
        claims_list: list[dict] = task.get("claims", [])

        if not claims_list:
            return {
                "result": {"error": "claims list is empty"},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        results = []
        total_cost = 0.0
        for item in claims_list:
            item["trace_id"] = trace_id
            r = await self._handle_fact_check(item)
            results.append(r["result"])
            total_cost += r["meta"]["cost_inr"]

        quarantine_count = sum(1 for r in results if r.get("verdict") == "QUARANTINE")

        return {
            "result": {
                "batch_results": results,
                "total": len(results),
                "quarantine_count": quarantine_count,
                "pass_count": sum(1 for r in results if r.get("verdict") == "PASS"),
            },
            "meta": {
                "agent": self.name,
                "cost_inr": total_cost,
                "trace_id": trace_id,
            },
        }

    def _handle_health(self) -> dict:
        return {
            "result": {
                "status": "healthy",
                "total_checked": self._total_checked,
                "total_quarantined": self._total_quarantined,
                "quarantine_rate": (
                    self._total_quarantined / max(self._total_checked, 1)
                ),
            },
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }

    @property
    def stats(self) -> dict:
        return {
            "total_checked": self._total_checked,
            "total_quarantined": self._total_quarantined,
        }

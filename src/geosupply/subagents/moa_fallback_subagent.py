"""
MoAFallbackSubAgent — Phase 6 SubAgent Layer
FA v2 | Part III G8 | Layer 4

Aggregates multiple BriefProposal candidates using weighted MoA scoring.

PIPELINE:
    Step 1 (score_proposals):        Score each BriefProposal using config weights
    Step 2 (select_or_merge):        Select winner or merge top-2 if within threshold
    Step 3 (apply_hallucination_gate): Enforce HALLUCINATION_FLOOR on selected output

Scoring formula (from MOA_SCORING_WEIGHTS in config.py):
    score = 0.4 * factcheck_score + 0.3 * source_credibility_avg + 0.3 * claim_evidence_ratio

Actions returned:
    SELECTED   -- single winner chosen (top score >= MOA_ESCALATE_THRESHOLD, no merge)
    MERGED     -- top-2 within MOA_MERGE_THRESHOLD (0.05) -> merge brief_text
    ESCALATE   -- all proposals score below MOA_ESCALATE_THRESHOLD (0.50)
    BELOW_FLOOR -- winner confidence < HALLUCINATION_FLOOR (0.70)

Cost: Rs 0.0 (Tier-0 -- no LLM).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from geosupply.config import (
    HALLUCINATION_FLOOR,
    MOA_SCORING_WEIGHTS,
    MOA_MERGE_THRESHOLD,
    MOA_ESCALATE_THRESHOLD,
)
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import BriefProposal

logger = logging.getLogger(__name__)


class MoAFallbackSubAgent(BaseSubAgent):
    """Mixture-of-Agents aggregation for brief proposals."""

    name = "MoAFallbackSubAgent"
    pipeline_steps = ["score_proposals", "select_or_merge", "apply_hallucination_gate"]
    parallel_steps: set[str] = set()

    async def setup(self) -> None:
        await super().setup()

    async def teardown(self) -> None:
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        """
        Score, select or merge BriefProposals, then apply hallucination gate.
        """
        trace_id = input_data.get("trace_id", str(uuid.uuid4()))
        raw_proposals = input_data.get("proposals", [])

        # ----------------------------------------------------------------
        # Step 1 — score_proposals
        # ----------------------------------------------------------------
        scored_proposals: list[tuple[BriefProposal, float]] = []
        for raw in raw_proposals:
            try:
                p = BriefProposal.model_validate(raw)
            except Exception as exc:
                logger.warning("MoAFallbackSubAgent: skipping invalid proposal: %s", exc)
                continue
            score = (
                MOA_SCORING_WEIGHTS["factcheck_score"] * p.factcheck_score
                + MOA_SCORING_WEIGHTS["source_credibility_avg"] * p.source_credibility_avg
                + MOA_SCORING_WEIGHTS["claim_evidence_ratio"] * p.claim_evidence_ratio
            )
            scored_proposals.append((p, round(score, 4)))

        if not scored_proposals:
            return {
                "result": {
                    "selected_proposal": None,
                    "action": "ESCALATE",
                    "score": 0.0,
                    "proposal_count": 0,
                    "trace_id": trace_id,
                },
                "meta": {
                    "subagent": self.name,
                    "cost_inr": 0.0,
                    "steps_completed": 3,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        # Sort by score descending
        scored_proposals.sort(key=lambda x: x[1], reverse=True)

        # ----------------------------------------------------------------
        # Step 2 — select_or_merge
        # ----------------------------------------------------------------
        top_score = scored_proposals[0][1]
        selected: BriefProposal | None = None
        final_score: float = top_score
        action: str

        if top_score < MOA_ESCALATE_THRESHOLD:
            action = "ESCALATE"
            selected = None
            final_score = top_score
        elif (
            len(scored_proposals) >= 2
            and (top_score - scored_proposals[1][1]) <= MOA_MERGE_THRESHOLD
        ):
            # Merge top-2
            p1, p2 = scored_proposals[0][0], scored_proposals[1][0]
            merged_brief = p1.brief_text + " [MERGED] " + p2.brief_text
            merged_confidence = (p1.confidence + p2.confidence) / 2
            selected = p1.model_copy(update={"brief_text": merged_brief, "confidence": merged_confidence})
            action = "MERGED"
            final_score = round((top_score + scored_proposals[1][1]) / 2, 4)
        else:
            selected = scored_proposals[0][0]
            action = "SELECTED"
            final_score = top_score

        # ----------------------------------------------------------------
        # Step 3 — apply_hallucination_gate
        # ----------------------------------------------------------------
        if action not in ("ESCALATE",) and selected is not None:
            if selected.confidence < HALLUCINATION_FLOOR:
                logger.warning(
                    "MoAFallbackSubAgent: selected proposal confidence %.3f < "
                    "HALLUCINATION_FLOOR %.2f",
                    selected.confidence, HALLUCINATION_FLOOR,
                )
                action = "BELOW_FLOOR"
                selected = None

        return {
            "result": {
                "selected_proposal": selected.model_dump() if selected else None,
                "action": action,
                "score": round(final_score, 4),
                "proposal_count": len(scored_proposals),
                "trace_id": trace_id,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "steps_completed": 3,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

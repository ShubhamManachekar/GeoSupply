"""
HallucinationCheckSubAgent - Phase 5 SubAgent Layer
FA v2 | Part III | Layer 4

Validates an LLM or worker output against the HALLUCINATION_FLOOR threshold.
Combines ClaimWorker + SentimentWorker outputs to produce a composite
confidence score and flag outputs that fall below the floor.

PIPELINE:
    Step 1: ClaimWorker    → claim type + evidence_needed
    Step 2: SentimentWorker → confidence proxy
    Step 3 (fuse): composite_confidence = weighted average
                   flag if composite_confidence < HALLUCINATION_FLOOR
"""

from __future__ import annotations

from datetime import datetime, timezone

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.sentiment_worker import SentimentWorker


# Weights for composite confidence
_CLAIM_WEIGHT = 0.60
_SENTIMENT_WEIGHT = 0.40

# Claim-type base confidence priors
_CLAIM_CONFIDENCE_PRIOR: dict[str, float] = {
    "FACTUAL": 0.80,
    "STATISTICAL": 0.75,
    "CAUSAL": 0.65,
    "PREDICTIVE": 0.55,
    "OPINION": 0.40,
}


class HallucinationCheckSubAgent(BaseSubAgent):
    """
    Check whether a text output meets the HALLUCINATION_FLOOR (0.70).

    Input:
        text (str): Text to validate.
        trace_id (str): Propagated trace identifier.

    Output:
        result:
            composite_confidence: float
            hallucination_floor: float (config constant)
            passes_floor: bool
            claim_type: str
            evidence_needed: bool
            sentiment_confidence: float
        meta:
            subagent, cost_inr, steps_completed, trace_id, timestamp
    """

    name = "HallucinationCheckSubAgent"
    pipeline_steps = ["claim", "sentiment", "fuse"]
    parallel_steps = {"claim", "sentiment"}

    def __init__(self) -> None:
        self._claim = ClaimWorker()
        self._sentiment = SentimentWorker()

    async def setup(self) -> None:
        await self._claim.setup()
        await self._sentiment.setup()
        await super().setup()

    async def teardown(self) -> None:
        await self._claim.teardown()
        await self._sentiment.teardown()
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("sanitised_text") or input_data.get("text", "")

        payload = {"text": text, "trace_id": trace_id}

        # Step 1+2: parallel
        claim_res, sentiment_res = await self.run_parallel(
            steps=[self._claim.safe_process, self._sentiment.safe_process],
            inputs=[payload, payload],
        )

        total_cost = (
            claim_res.get("meta", {}).get("cost_inr", 0.0)
            + sentiment_res.get("meta", {}).get("cost_inr", 0.0)
        )

        # Step 3: fuse
        claim_data = claim_res.get("result") or {}
        sentiment_data = sentiment_res.get("result") or {}

        claim_type = claim_data.get("claim_type", "FACTUAL")
        evidence_needed = claim_data.get("evidence_needed", True)
        claim_prior = _CLAIM_CONFIDENCE_PRIOR.get(claim_type, 0.60)
        sentiment_conf = float(sentiment_data.get("confidence", 0.50))

        composite = round(
            _CLAIM_WEIGHT * claim_prior + _SENTIMENT_WEIGHT * sentiment_conf, 4
        )
        passes_floor = composite >= HALLUCINATION_FLOOR

        return {
            "result": {
                "composite_confidence": composite,
                "hallucination_floor": HALLUCINATION_FLOOR,
                "passes_floor": passes_floor,
                "claim_type": claim_type,
                "evidence_needed": evidence_needed,
                "sentiment_confidence": round(sentiment_conf, 4),
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": total_cost,
                "steps_completed": 3,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

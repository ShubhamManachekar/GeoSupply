"""
SourceFeedbackSubAgent - Phase 5 SubAgent Layer
FA v2 | Part III | Layer 4

Applies feedback loops to source credibility scores.
When a claim is found to be false or propaganda, the originating
source takes a penalty strike; when verified, it gets a boost.

This implements FA v1's 3-strike penalty system at the SubAgent level:
    Strike 1: -0.05
    Strike 2: -0.10
    Strike 3: -0.20
    Strike 4+: permanent flag

PIPELINE:
    Step 1: SourceCredWorker → current score
    Step 2: PropagandaWorker → propaganda signal
    Step 3 (fuse): Compute delta, produce SourceFeedbackScore
"""

from __future__ import annotations

from datetime import datetime, timezone

from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import SourceFeedbackScore
from geosupply.workers.propaganda_worker import PropagandaWorker
from geosupply.workers.source_cred_worker import SourceCredWorker

_PENALTY_LEVELS = [-0.05, -0.10, -0.20]
_BOOST_AMOUNT = 0.03    # small verified-correct boost
_MAX_SCORE = 1.0
_MIN_SCORE = 0.0


class SourceFeedbackSubAgent(BaseSubAgent):
    """
    Apply credibility feedback to a source based on content quality.

    Input:
        source_id (str): URL or identifier of the source.
        text (str): Content from the source for propaganda check.
        verified_correct (bool, optional): Admin-confirmed correct → boost.
        strike_number (int, optional): Current strike count (1-indexed).
        trace_id (str): Propagated trace identifier.

    Output:
        result:
            source_id: str
            old_score: float
            new_score: float
            penalty: float (negative = penalty, positive = boost)
            reason: str
            is_propaganda: bool
        meta:
            subagent, cost_inr, steps_completed, trace_id, timestamp
    """

    name = "SourceFeedbackSubAgent"
    pipeline_steps = ["source_cred", "propaganda", "fuse"]
    parallel_steps = {"source_cred", "propaganda"}

    def __init__(self) -> None:
        self._source_cred = SourceCredWorker()
        self._propaganda = PropagandaWorker()

    async def setup(self) -> None:
        await self._source_cred.setup()
        await self._propaganda.setup()
        await super().setup()

    async def teardown(self) -> None:
        await self._source_cred.teardown()
        await self._propaganda.teardown()
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        source_id = input_data.get("source_id", "unknown_source")
        text = input_data.get("sanitised_text") or input_data.get("text", "")
        verified_correct = bool(input_data.get("verified_correct", False))
        strike_number = int(input_data.get("strike_number", 0))

        cred_payload = {"source_id": source_id, "trace_id": trace_id}
        prop_payload = {"text": text, "trace_id": trace_id}

        # Step 1+2: parallel
        cred_res, prop_res = await self.run_parallel(
            steps=[self._source_cred.safe_process, self._propaganda.safe_process],
            inputs=[cred_payload, prop_payload],
        )

        total_cost = (
            cred_res.get("meta", {}).get("cost_inr", 0.0)
            + prop_res.get("meta", {}).get("cost_inr", 0.0)
        )

        # Step 3: fuse
        cred_data = cred_res.get("result") or {}
        prop_data = prop_res.get("result") or {}

        old_score = float(cred_data.get("credibility_score", 0.55))
        is_propaganda = bool(prop_data.get("is_propaganda", False))

        # Compute delta
        if verified_correct:
            delta = _BOOST_AMOUNT
            reason = "verified_correct"
        elif is_propaganda:
            idx = min(strike_number, len(_PENALTY_LEVELS) - 1)
            delta = _PENALTY_LEVELS[idx]
            reason = f"propaganda_detected_strike_{strike_number + 1}"
        else:
            delta = 0.0
            reason = "no_change"

        new_score = round(min(_MAX_SCORE, max(_MIN_SCORE, old_score + delta)), 4)

        record = SourceFeedbackScore(
            source_id=source_id,
            old_score=round(old_score, 4),
            new_score=new_score,
            penalty=round(delta, 4),
            reason=reason,
        )

        return {
            "result": {
                **record.model_dump(),
                "is_propaganda": is_propaganda,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": total_cost,
                "steps_completed": 3,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

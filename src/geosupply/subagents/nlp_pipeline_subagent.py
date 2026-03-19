"""
NLPPipelineSubAgent - Phase 5 SubAgent Layer
FA v2 | Part III | Layer 4

Composes SentimentWorker + NERWorker + ClaimWorker into a parallel
NLP enrichment pipeline for a single text input.

PIPELINE:
    Step 1 (parallel): SentimentWorker + NERWorker + ClaimWorker
    Step 2 (fuse): Merge results into NLPEnrichedOutput
"""

from __future__ import annotations

from datetime import datetime, timezone

from geosupply.core.base_subagent import BaseSubAgent
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.ner_worker import NERWorker
from geosupply.workers.sentiment_worker import SentimentWorker


class NLPPipelineSubAgent(BaseSubAgent):
    """
    Run sentiment, NER, and claim extraction in parallel, then fuse.

    Input:
        text (str): raw or sanitised text
        trace_id (str): propagated trace identifier

    Output:
        result:
            sentiment: SentimentOutput dict
            entities: list[NEREntity dict]
            claim: ClaimOutput dict
            nlp_cost_inr: float
        meta:
            subagent, cost_inr, steps_completed, trace_id, timestamp
    """

    name = "NLPPipelineSubAgent"
    pipeline_steps = ["sentiment", "ner", "claim"]
    parallel_steps = {"sentiment", "ner", "claim"}

    def __init__(self) -> None:
        self._sentiment = SentimentWorker()
        self._ner = NERWorker()
        self._claim = ClaimWorker()

    async def setup(self) -> None:
        await self._sentiment.setup()
        await self._ner.setup()
        await self._claim.setup()
        await super().setup()

    async def teardown(self) -> None:
        await self._sentiment.teardown()
        await self._ner.teardown()
        await self._claim.teardown()
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("sanitised_text") or input_data.get("text", "")

        payload = {"text": text, "trace_id": trace_id}

        # Step 1: all three workers in parallel
        sentiment_res, ner_res, claim_res = await self.run_parallel(
            steps=[
                self._sentiment.safe_process,
                self._ner.safe_process,
                self._claim.safe_process,
            ],
            inputs=[payload, payload, payload],
        )

        total_cost = sum(
            r.get("meta", {}).get("cost_inr", 0.0)
            for r in (sentiment_res, ner_res, claim_res)
        )

        # Step 2: fuse — surface errors transparently
        return {
            "result": {
                "sentiment": sentiment_res.get("result"),
                "entities": (ner_res.get("result") or {}).get("entities", []),
                "claim": claim_res.get("result"),
                "nlp_cost_inr": total_cost,
                "errors": [
                    r.get("error_type")
                    for r in (sentiment_res, ner_res, claim_res)
                    if "error_type" in r
                ],
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": total_cost,
                "steps_completed": 2,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

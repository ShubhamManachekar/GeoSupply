"""
AuditSampleSubAgent - Phase 5 SubAgent Layer
FA v2 | Part III | Layer 4

Samples pipeline outputs at a configurable rate and runs
schema-validation + hallucination-floor checks. Produces an
AuditSample record for downstream review by AuditorAgent.

PIPELINE:
    Step 1: Decide whether to audit this item (sampling gate)
    Step 2 (parallel): ClaimWorker + SentimentWorker → composite confidence
    Step 3 (fuse): Validate against HALLUCINATION_FLOOR → AuditSample
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import AuditSample
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.sentiment_worker import SentimentWorker

_DEFAULT_SAMPLING_RATE = 0.05   # 5% of pipeline outputs audited


class AuditSampleSubAgent(BaseSubAgent):
    """
    Probabilistic audit sampler for pipeline QA.

    Input:
        text (str): Pipeline output text to audit.
        trace_id (str): Propagated trace identifier.
        sample_id (str, optional): Unique ID for this audit record.
        sampling_rate (float, optional): Override default 5% rate.
        force_audit (bool, optional): Bypass sampling gate.

    Output:
        result:
            sampled: bool — whether this item was audited
            audit_result: 'PASS' | 'FAIL' | 'WARN' | 'SKIPPED'
            audit_record: AuditSample dict (if sampled)
            composite_confidence: float (if sampled)
        meta:
            subagent, cost_inr, steps_completed, trace_id, timestamp
    """

    name = "AuditSampleSubAgent"
    pipeline_steps = ["sample_gate", "validate", "fuse"]
    parallel_steps = {"validate"}

    def __init__(self, sampling_rate: float = _DEFAULT_SAMPLING_RATE) -> None:
        self._sampling_rate = max(0.0, min(1.0, sampling_rate))
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
        sample_id = input_data.get("sample_id", f"audit-{trace_id}")
        sampling_rate = float(input_data.get("sampling_rate", self._sampling_rate))
        force_audit = bool(input_data.get("force_audit", False))

        # Step 1: Sampling gate
        do_audit = force_audit or (random.random() < sampling_rate)

        if not do_audit:
            return {
                "result": {
                    "sampled": False,
                    "audit_result": "SKIPPED",
                    "audit_record": None,
                    "composite_confidence": None,
                },
                "meta": {
                    "subagent": self.name,
                    "cost_inr": 0.0,
                    "steps_completed": 1,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        payload = {"text": text, "trace_id": trace_id}

        # Step 2: Parallel claim + sentiment
        claim_res, sentiment_res = await self.run_parallel(
            steps=[self._claim.safe_process, self._sentiment.safe_process],
            inputs=[payload, payload],
        )

        total_cost = (
            claim_res.get("meta", {}).get("cost_inr", 0.0)
            + sentiment_res.get("meta", {}).get("cost_inr", 0.0)
        )

        # Step 3: Fuse → composite confidence → audit verdict
        claim_data = claim_res.get("result") or {}
        sent_data = sentiment_res.get("result") or {}

        _CLAIM_PRIOR = {
            "FACTUAL": 0.80, "STATISTICAL": 0.75, "CAUSAL": 0.65,
            "PREDICTIVE": 0.55, "OPINION": 0.40,
        }
        claim_type = claim_data.get("claim_type", "FACTUAL")
        claim_prior = _CLAIM_PRIOR.get(claim_type, 0.60)
        sent_conf = float(sent_data.get("confidence", 0.50))
        composite = round(0.60 * claim_prior + 0.40 * sent_conf, 4)

        if composite >= HALLUCINATION_FLOOR:
            audit_result = "PASS"
        elif composite >= HALLUCINATION_FLOOR * 0.85:
            audit_result = "WARN"
        else:
            audit_result = "FAIL"

        pipeline_output = {
            "claim_type": claim_type,
            "sentiment_confidence": sent_conf,
            "composite_confidence": composite,
        }

        record = AuditSample(
            sample_id=sample_id,
            pipeline_output=pipeline_output,
            audit_result=audit_result,  # type: ignore[arg-type]
            sampling_rate=sampling_rate,
        )

        return {
            "result": {
                "sampled": True,
                "audit_result": audit_result,
                "audit_record": record.model_dump(),
                "composite_confidence": composite,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": total_cost,
                "steps_completed": 3,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""ClaimWorker - Tier-1 STATIC claim extraction and classification."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import ClaimOutput, WorkerError

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


def _pick_claim_text(text: str) -> str:
    sentences = [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]
    if not sentences:
        return ""
    for sentence in sentences:
        if len(sentence) >= 24:
            return sentence
    return sentences[0]


def _classify_claim(claim_text: str) -> tuple[str, bool]:
    lowered = claim_text.lower()

    if re.search(r"\d+%|\b\d+(?:\.\d+)?\b", lowered) and re.search(
        r"increase|decrease|rise|drop|growth|decline", lowered
    ):
        return "STATISTICAL", True

    if re.search(r"\b(will|likely|forecast|expected|may|could)\b", lowered):
        return "PREDICTIVE", True

    if re.search(r"because|due to|leads to|led to|caused by|results in", lowered):
        return "CAUSAL", True

    if re.search(r"\b(i think|we believe|in my opinion|should|must)\b", lowered):
        return "OPINION", False

    return "FACTUAL", True


class ClaimWorker(BaseWorker):
    """Extract and classify the primary claim from input text."""

    name = "ClaimWorker"
    tier = 1
    use_static = True
    capabilities = {"CLAIM_EXTRACT", "CLAIM_CLASSIFY"}
    max_retries = 2
    timeout_seconds = 20

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("sanitised_text") or input_data.get("text")

        if not isinstance(text, str) or not text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'text' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        claim_text = _pick_claim_text(text)
        if not claim_text:
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Could not identify claim text",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        claim_type, evidence_needed = _classify_claim(claim_text)
        output = ClaimOutput(
            claim_text=claim_text,
            claim_type=claim_type,
            evidence_needed=evidence_needed,
        )

        return {
            "result": output.model_dump(),
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

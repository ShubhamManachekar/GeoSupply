"""SentimentWorker - Tier-1 STATIC sentiment scoring."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import SentimentOutput, WorkerError

_TOKEN_RE = re.compile(r"[A-Za-z']+")

_POSITIVE_WORDS = {
    "good",
    "great",
    "strong",
    "stable",
    "improve",
    "improved",
    "growth",
    "peace",
    "success",
    "benefit",
}

_NEGATIVE_WORDS = {
    "bad",
    "poor",
    "weak",
    "crisis",
    "decline",
    "war",
    "conflict",
    "risk",
    "failure",
    "loss",
}

_SUBJECTIVE_MARKERS = {
    "think",
    "believe",
    "seems",
    "appears",
    "likely",
    "possibly",
    "perhaps",
}


def _tokenise(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_sentiment(tokens: list[str]) -> tuple[float, float, float]:
    if not tokens:
        return 0.0, 0.0, 0.0

    positive = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    negative = sum(1 for t in tokens if t in _NEGATIVE_WORDS)
    subjective = sum(1 for t in tokens if t in _SUBJECTIVE_MARKERS)

    signal = positive + negative
    polarity = 0.0 if signal == 0 else (positive - negative) / float(signal)
    subjectivity = _clamp((subjective + signal) / max(len(tokens), 1), 0.0, 1.0)

    confidence = _clamp(0.35 + abs(polarity) * 0.4 + min(signal / 20.0, 0.25), 0.0, 1.0)
    return polarity, subjectivity, confidence


class SentimentWorker(BaseWorker):
    """Score sentiment for a text input with a schema-strict output."""

    name = "SentimentWorker"
    tier = 1
    use_static = True
    capabilities = {"SENTIMENT_SCORE", "EMOTION"}
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

        polarity, subjectivity, confidence = _score_sentiment(_tokenise(text))
        output = SentimentOutput(
            polarity=round(_clamp(polarity, -1.0, 1.0), 4),
            subjectivity=round(subjectivity, 4),
            confidence=round(confidence, 4),
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

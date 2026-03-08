"""PropagandaWorker - heuristic propaganda and technique detection."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

_FEAR_WORDS = {"threat", "destroy", "attack", "collapse", "danger", "chaos"}
_BANDWAGON_WORDS = {"everyone", "all", "always", "never", "true patriots"}
_DEMONIZE_WORDS = {"enemy", "traitor", "vermin", "evil", "corrupt"}
_IMPERATIVE_WORDS = {"must", "should", "obey", "fight", "act"}


def _tokenise(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z']+", text)]


def _score_techniques(tokens: list[str], original: str) -> tuple[float, list[str], list[str]]:
    if not tokens:
        return 0.0, [], []

    techniques: list[str] = []
    evidence: list[str] = []

    fear_hits = sum(1 for token in tokens if token in _FEAR_WORDS)
    bandwagon_hits = sum(1 for token in tokens if token in _BANDWAGON_WORDS)
    demonize_hits = sum(1 for token in tokens if token in _DEMONIZE_WORDS)
    urgency_hits = len(re.findall(r"!|urgent|immediately|now", original, flags=re.IGNORECASE))
    imperative_hits = sum(1 for token in tokens if token in _IMPERATIVE_WORDS)

    score = 0.0
    if fear_hits:
        techniques.append("FEAR_APPEAL")
        evidence.append(f"fear_hits={fear_hits}")
        score += min(0.35, fear_hits * 0.08)

    if bandwagon_hits:
        techniques.append("BANDWAGON")
        evidence.append(f"bandwagon_hits={bandwagon_hits}")
        score += min(0.25, bandwagon_hits * 0.07)

    if demonize_hits:
        techniques.append("NAME_CALLING")
        evidence.append(f"name_calling_hits={demonize_hits}")
        score += min(0.25, demonize_hits * 0.07)

    if urgency_hits:
        techniques.append("URGENCY")
        evidence.append(f"urgency_hits={urgency_hits}")
        score += min(0.15, urgency_hits * 0.05)

    if imperative_hits:
        techniques.append("IMPERATIVE_FRAMING")
        evidence.append(f"imperative_hits={imperative_hits}")
        score += min(0.12, imperative_hits * 0.06)

    pronoun_split = len(re.findall(r"\b(we|us|our)\b", original, flags=re.IGNORECASE))
    pronoun_other = len(re.findall(r"\b(they|them|their)\b", original, flags=re.IGNORECASE))
    if pronoun_split and pronoun_other:
        techniques.append("US_VS_THEM")
        evidence.append("dual_pronoun_frames")
        score += 0.1

    return min(1.0, score), sorted(set(techniques)), evidence


class PropagandaWorker(BaseWorker):
    """Classify persuasive manipulation signals in narrative text."""

    name = "PropagandaWorker"
    tier = 2
    use_static = False
    capabilities = {"PROPAGANDA_SCORE", "TECHNIQUE"}
    max_retries = 2
    timeout_seconds = 30

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

        score, techniques, evidence = _score_techniques(_tokenise(text), text)
        confidence = min(1.0, 0.4 + score * 0.6)

        return {
            "result": {
                "propaganda_score": round(score, 4),
                "is_propaganda": score >= 0.45,
                "techniques": techniques,
                "evidence": evidence,
                "confidence": round(confidence, 4),
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

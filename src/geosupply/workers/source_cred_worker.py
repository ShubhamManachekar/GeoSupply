"""SourceCredWorker - Tier-1 STATIC source credibility scoring."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import SourceCredOutput, WorkerError

# Known high-credibility domains (score bonus)
_HIGH_CRED_DOMAINS = frozenset({
    "reuters.com", "bbc.com", "apnews.com", "pti.in",
    "thehindu.com", "livemint.com", "economictimes.com",
    "ndtv.com", "hindustantimes.com", "businessstandard.com",
})

# Known low-credibility patterns
_LOW_CRED_PATTERNS = [
    re.compile(r"(breaking|exclusive|shocking|you won't believe)", re.IGNORECASE),
    re.compile(r"\b(fake|hoax|conspiracy)\b", re.IGNORECASE),
]

# Strike tracking: source_id → list of penalty reasons
_STRIKE_REGISTRY: dict[str, list[str]] = {}

_SOURCE_PENALTY_LEVELS = [-0.05, -0.10, -0.20]
_SOURCE_PERMANENT_FLAG_STRIKES = 4


def _extract_domain(source_id: str) -> str:
    """Extract base domain from a URL or return as-is."""
    match = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", source_id.lower())
    return match.group(1) if match else source_id.lower().strip()


def _base_score(domain: str) -> float:
    """Assign baseline credibility score from domain reputation."""
    if domain in _HIGH_CRED_DOMAINS:
        return 0.85
    if domain.endswith(".gov.in") or domain.endswith(".nic.in"):
        return 0.90
    if domain.endswith(".edu") or domain.endswith(".ac.in"):
        return 0.80
    return 0.55  # Unknown/default


def _apply_strikes(base: float, strikes: list[str]) -> float:
    """Deduct penalties based on historical strike count."""
    score = base
    for i, _ in enumerate(strikes):
        if i < len(_SOURCE_PENALTY_LEVELS):
            score += _SOURCE_PENALTY_LEVELS[i]
        else:
            score += _SOURCE_PENALTY_LEVELS[-1]
    return max(0.0, min(1.0, score))


def _scan_headline(headline: str) -> list[str]:
    """Return list of penalty reasons from headline text."""
    reasons: list[str] = []
    for pattern in _LOW_CRED_PATTERNS:
        if pattern.search(headline):
            reasons.append(f"clickbait_pattern:{pattern.pattern[:30]}")
    return reasons


class SourceCredWorker(BaseWorker):
    """
    Score source credibility using domain reputation + strike history.

    Input fields:
        source_id (str): URL or identifier of the source.
        headline (str, optional): Article headline for content scan.
        record_strike (bool, optional): If True + flagged, log a strike.
    """

    name = "SourceCredWorker"
    tier = 1
    use_static = True
    capabilities = {"SOURCE_SCORE", "CREDIBILITY"}
    max_retries = 2
    timeout_seconds = 20

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        source_id = input_data.get("source_id")
        headline = input_data.get("headline", "")
        record_strike = bool(input_data.get("record_strike", False))

        if not isinstance(source_id, str) or not source_id.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'source_id' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        domain = _extract_domain(source_id)
        base = _base_score(domain)

        # Content scan penalty
        headline_strikes = _scan_headline(headline) if isinstance(headline, str) else []
        if headline_strikes and record_strike:
            existing = _STRIKE_REGISTRY.setdefault(source_id, [])
            existing.extend(headline_strikes)

        all_strikes = _STRIKE_REGISTRY.get(source_id, [])
        final_score = _apply_strikes(base, all_strikes)

        # Permanently flagged if strikes ≥ threshold
        permanently_flagged = len(all_strikes) >= _SOURCE_PERMANENT_FLAG_STRIKES

        output = SourceCredOutput(
            source_id=source_id,
            credibility_score=round(final_score, 4),
            history=list(all_strikes[-5:]),  # last 5 events
        )

        return {
            "result": {
                **output.model_dump(),
                "domain": domain,
                "permanently_flagged": permanently_flagged,
                "strike_count": len(all_strikes),
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""VerifierWorker — Tier-3 claim verification against evidence context.

Primary path: Claude Haiku 4.5 (semantic reasoning).
Fallback path: rule-based pattern scoring (used when SDK/key unavailable).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import VerificationResult, WorkerError
from geosupply.workers.claude_mixin import ClaudeWorkerMixin

# ── Contradiction signal patterns ────────────────────────────────────────────
_CONTRADICTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(false|fabricated|misleading|incorrect|wrong|denied|untrue)\b", re.I),
    re.compile(r"\b(never happened|did not occur|no evidence|not confirmed)\b", re.I),
    re.compile(r"\b(disprove[sd]?|refute[sd]?|debunk[ed]*|retract[ed]*)\b", re.I),
]

# ── Corroboration signal patterns ─────────────────────────────────────────────
_CORROBORATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(confirm[ed]*|verified|corroborat[ed]*|substantiat[ed]*)\b", re.I),
    re.compile(r"\b(evidence shows|data indicates|report[s]? confirm|source[s]? confirm)\b", re.I),
    re.compile(r"\b(consistent with|agree[s]? with|support[s]? claim)\b", re.I),
]

# ── Hedging / uncertainty patterns ────────────────────────────────────────────
_UNCERTAINTY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(alleged|allegedly|reportedly|unconfirmed|rumoured|claimed)\b", re.I),
    re.compile(r"\b(could not verify|unable to confirm|unclear whether|unknown if)\b", re.I),
    re.compile(r"\b(speculation|speculated|unverified|not yet confirmed)\b", re.I),
]

_PROPAGANDA_AMPLIFIERS = re.compile(
    r"\b(state.?media|government.?source|official.?channel|ministry.?statement)\b", re.I
)

_METHOD_CORROBORATION = "multi-source-corroboration"
_METHOD_CONTRADICTION = "evidence-contradiction"
_METHOD_HEDGED = "source-hedging-analysis"
_METHOD_STATISTICAL = "statistical-claim-check"
_METHOD_INSUFFICIENT = "insufficient-evidence"
_METHOD_CLAUDE = "claude-semantic-verification"

_STATISTICAL_PATTERN = re.compile(
    r"\b(\d+\.?\d*\s*%|\d+\.?\d*\s*(billion|million|lakh|crore|thousand))\b", re.I
)

_SYSTEM_PROMPT = """You are a fact-checking specialist for geopolitical supply-chain intelligence.
Given a CLAIM and EVIDENCE, return ONLY a JSON object with these exact keys:
{
  "verdict": "<VERIFIED|REFUTED|UNVERIFIABLE|INSUFFICIENT_EVIDENCE>",
  "confidence": <0.0-1.0>,
  "evidence_count": <int>,
  "verification_method": "<brief method description>",
  "contradictions": ["<snippet>", ...],
  "supporting_sources": ["<source name>", ...]
}
Rules:
- VERIFIED: evidence clearly supports the claim with credible sources
- REFUTED: evidence clearly contradicts the claim
- UNVERIFIABLE: conflicting signals or hedged sources
- INSUFFICIENT_EVIDENCE: evidence too short or absent
- confidence reflects your certainty (0=none, 1=certain)
- Respond with JSON only, no commentary."""


def _count_signal(text: str, patterns: list[re.Pattern[str]]) -> int:
    return sum(1 for p in patterns if p.search(text))


def _extract_sources(text: str) -> list[str]:
    found: list[str] = []
    for m in re.finditer(
        r"(?:according to|per|says?|reported by|source:\s*)"
        r"([A-Z][A-Za-z\s]{2,30}(?:Times|Post|News|Report|Agency|Ministry|Bureau)?)",
        text,
    ):
        src = m.group(1).strip()
        if src not in found:
            found.append(src)
    for m in re.finditer(r"\b([a-z]+\.(com|in|org|gov\.in|net))\b", text, re.I):
        domain = m.group(1).lower()
        if domain not in found:
            found.append(domain)
    return found[:5]


def _extract_contradictions(text: str) -> list[str]:
    results: list[str] = []
    for pat in _CONTRADICTION_PATTERNS:
        for m in pat.finditer(text):
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].strip()
            if snippet not in results:
                results.append(snippet)
    return results[:3]


def _heuristic_verify(claim_text: str, evidence_text: str) -> VerificationResult:
    """Rule-based fallback — used when Claude is unavailable."""
    if not evidence_text or len(evidence_text.strip()) < 30:
        return VerificationResult(
            claim_text=claim_text,
            verdict="INSUFFICIENT_EVIDENCE",
            confidence=0.50,
            evidence_count=0,
            verification_method=_METHOD_INSUFFICIENT,
        )

    contradiction_count = _count_signal(evidence_text, _CONTRADICTION_PATTERNS)
    corroboration_count = _count_signal(evidence_text, _CORROBORATION_PATTERNS)
    uncertainty_count = _count_signal(evidence_text, _UNCERTAINTY_PATTERNS)
    has_propaganda = bool(_PROPAGANDA_AMPLIFIERS.search(evidence_text))

    is_statistical = bool(_STATISTICAL_PATTERN.search(claim_text))
    stat_matches = 0
    if is_statistical:
        claim_numbers = set(re.findall(r"\d+\.?\d*", claim_text))
        evidence_numbers = set(re.findall(r"\d+\.?\d*", evidence_text))
        stat_matches = len(claim_numbers & evidence_numbers)

    sources = _extract_sources(evidence_text)
    contradictions = _extract_contradictions(evidence_text) if contradiction_count > 0 else []

    base_confidence = 0.55
    base_confidence += min(corroboration_count * 0.08, 0.24)
    base_confidence -= min(contradiction_count * 0.12, 0.36)
    base_confidence -= min(uncertainty_count * 0.06, 0.18)
    if is_statistical and stat_matches > 0:
        base_confidence += 0.10
    if has_propaganda:
        base_confidence -= 0.05
    base_confidence = max(0.0, min(1.0, base_confidence))

    if corroboration_count == 0 and contradiction_count == 0 and uncertainty_count >= 2:
        verdict, method = "UNVERIFIABLE", _METHOD_HEDGED
    elif contradiction_count > corroboration_count:
        verdict, method = "REFUTED", _METHOD_CONTRADICTION
    elif corroboration_count > 0 and base_confidence >= 0.60:
        verdict, method = "VERIFIED", _METHOD_CORROBORATION
    elif is_statistical and stat_matches == 0:
        verdict, method = "UNVERIFIABLE", _METHOD_STATISTICAL
    elif len(evidence_text.strip()) < 100:
        verdict, method = "INSUFFICIENT_EVIDENCE", _METHOD_INSUFFICIENT
    else:
        verdict, method = "UNVERIFIABLE", _METHOD_HEDGED

    return VerificationResult(
        claim_text=claim_text,
        verdict=verdict,
        confidence=round(base_confidence, 4),
        evidence_count=len(sources),
        contradictions=contradictions,
        supporting_sources=sources,
        verification_method=method,
    )


class VerifierWorker(ClaudeWorkerMixin, BaseWorker):
    """
    Tier-3 claim verification worker.
    Primary: Claude Haiku 4.5 semantic reasoning.
    Fallback: multi-signal rule-based scoring.
    """

    name = "VerifierWorker"
    tier = 3
    use_static = False
    capabilities = {"CLAIM_VERIFY", "EVIDENCE_CHECK", "CONTRADICTION_DETECT"}
    max_retries = 1
    timeout_seconds = 45
    _max_tokens = 512

    async def setup(self) -> None:
        await super().setup()

    async def teardown(self) -> None:
        await super().teardown()

    async def process(self, input_data: dict) -> dict:
        """
        Input:
            text: str       — Claim to verify
            evidence: str   — Evidence context
            trace_id: str
        Output:
            result: VerificationResult fields
            meta: {worker, tier, cost_inr, trace_id, timestamp}
        """
        import json

        trace_id = input_data.get("trace_id", "unknown")
        claim_text = input_data.get("text") or input_data.get("claim_text") or ""
        evidence_text = input_data.get("evidence") or input_data.get("evidence_text") or ""

        if not isinstance(claim_text, str) or not claim_text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="claim_text is required and must be non-empty",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        user_msg = f"CLAIM: {claim_text.strip()}\n\nEVIDENCE:\n{evidence_text.strip() or '(none provided)'}"
        raw, cost_inr = await self._call_claude(_SYSTEM_PROMPT, user_msg)

        if raw:
            try:
                # Strip markdown fences if present
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = "\n".join(cleaned.split("\n")[1:])
                    cleaned = cleaned.rsplit("```", 1)[0].strip()
                parsed = json.loads(cleaned)
                verdict = parsed.get("verdict", "UNVERIFIABLE")
                result = VerificationResult(
                    claim_text=claim_text.strip(),
                    verdict=verdict,
                    confidence=round(float(parsed.get("confidence", 0.5)), 4),
                    evidence_count=int(parsed.get("evidence_count", 0)),
                    verification_method=parsed.get("verification_method", _METHOD_CLAUDE),
                    contradictions=parsed.get("contradictions", []),
                    supporting_sources=parsed.get("supporting_sources", []),
                )
            except (json.JSONDecodeError, ValueError, KeyError):
                result = _heuristic_verify(claim_text.strip(), evidence_text)
                cost_inr = 0.0
        else:
            result = _heuristic_verify(claim_text.strip(), evidence_text)
            cost_inr = 0.05

        return {
            "result": result.model_dump(),
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": cost_inr,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

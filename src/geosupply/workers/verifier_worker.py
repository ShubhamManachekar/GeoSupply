"""VerifierWorker — Tier-3 claim verification against evidence context."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import VerificationResult, WorkerError

# ── Contradiction signal patterns ────────────────────────────────────────────
_CONTRADICTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(false|fabricated|misleading|incorrect|wrong|denied|denied|untrue)\b", re.I),
    re.compile(r"\b(never happened|did not occur|no evidence|not confirmed)\b", re.I),
    re.compile(r"\b(disprove[sd]?|refute[sd]?|debunk[ed]*|retract[ed]*)\b", re.I),
]

# ── Corroboration signal patterns ─────────────────────────────────────────────
_CORROBORATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(confirm[ed]*|verified|corroborat[ed]*|substantiat[ed]*)\b", re.I),
    re.compile(r"\b(evidence shows|data indicates|report[s]? confirm|source[s]? confirm)\b", re.I),
    re.compile(r"\b(consistent with|agree[s]? with|support[s]? claim)\b", re.I),
]

# ── Hedging / uncertainty patterns → UNVERIFIABLE ─────────────────────────────
_UNCERTAINTY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(alleged|allegedly|reportedly|unconfirmed|rumoured|claimed)\b", re.I),
    re.compile(r"\b(could not verify|unable to confirm|unclear whether|unknown if)\b", re.I),
    re.compile(r"\b(speculation|speculated|unverified|not yet confirmed)\b", re.I),
]

# ── State-sponsored / propaganda boosters ─────────────────────────────────────
_PROPAGANDA_AMPLIFIERS = re.compile(
    r"\b(state.?media|government.?source|official.?channel|ministry.?statement)\b", re.I
)

# ── Verification method labels ─────────────────────────────────────────────────
_METHOD_CORROBORATION = "multi-source-corroboration"
_METHOD_CONTRADICTION = "evidence-contradiction"
_METHOD_HEDGED = "source-hedging-analysis"
_METHOD_STATISTICAL = "statistical-claim-check"
_METHOD_INSUFFICIENT = "insufficient-evidence"

# Statistical claim pattern — need numeric verification
_STATISTICAL_PATTERN = re.compile(
    r"\b(\d+\.?\d*\s*%|\d+\.?\d*\s*(billion|million|lakh|crore|thousand))\b", re.I
)


def _count_signal(text: str, patterns: list[re.Pattern[str]]) -> int:
    """Count how many of the given patterns match in text."""
    return sum(1 for p in patterns if p.search(text))


def _extract_sources(text: str) -> list[str]:
    """Extract likely source references from evidence text."""
    # Match quoted sources, news domains, or "according to X" patterns
    found: list[str] = []
    for m in re.finditer(
        r"(?:according to|per|says?|reported by|source:\s*)"
        r"([A-Z][A-Za-z\s]{2,30}(?:Times|Post|News|Report|Agency|Ministry|Bureau)?)",
        text,
    ):
        src = m.group(1).strip()
        if src not in found:
            found.append(src)
    # Also grab domain-like strings
    for m in re.finditer(r"\b([a-z]+\.(com|in|org|gov\.in|net))\b", text, re.I):
        domain = m.group(1).lower()
        if domain not in found:
            found.append(domain)
    return found[:5]  # cap at 5 sources


def _extract_contradictions(text: str) -> list[str]:
    """Extract brief contradiction phrases from text."""
    results: list[str] = []
    for pat in _CONTRADICTION_PATTERNS:
        for m in pat.finditer(text):
            # Grab surrounding context (up to 60 chars)
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].strip()
            if snippet not in results:
                results.append(snippet)
    return results[:3]


def _verify_claim(claim_text: str, evidence_text: str) -> VerificationResult:
    """
    Core verification logic — pure rule-based for Tier-3 STATIC mode.

    Decision tree:
    1. If evidence is too short → INSUFFICIENT_EVIDENCE
    2. Count contradiction signals in evidence
    3. Count corroboration signals in evidence
    4. Apply uncertainty/hedging modifiers
    5. Statistical claims require numeric presence in evidence
    """
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

    # Statistical claims: check if the same number appears in evidence
    is_statistical = bool(_STATISTICAL_PATTERN.search(claim_text))
    stat_matches = 0
    if is_statistical:
        claim_numbers = set(re.findall(r"\d+\.?\d*", claim_text))
        evidence_numbers = set(re.findall(r"\d+\.?\d*", evidence_text))
        stat_matches = len(claim_numbers & evidence_numbers)

    sources = _extract_sources(evidence_text)
    contradictions = _extract_contradictions(evidence_text) if contradiction_count > 0 else []

    # ── Scoring ────────────────────────────────────────────────────────────────
    base_confidence = 0.55

    # Corroboration bonus
    base_confidence += min(corroboration_count * 0.08, 0.24)

    # Contradiction penalty
    base_confidence -= min(contradiction_count * 0.12, 0.36)

    # Uncertainty penalty
    base_confidence -= min(uncertainty_count * 0.06, 0.18)

    # Statistical corroboration bonus
    if is_statistical and stat_matches > 0:
        base_confidence += 0.10

    # Propaganda source discount
    if has_propaganda:
        base_confidence -= 0.05

    base_confidence = max(0.0, min(1.0, base_confidence))

    # ── Verdict ────────────────────────────────────────────────────────────────
    if corroboration_count == 0 and contradiction_count == 0 and uncertainty_count >= 2:
        verdict = "UNVERIFIABLE"
        method = _METHOD_HEDGED
    elif contradiction_count > corroboration_count:
        verdict = "REFUTED"
        method = _METHOD_CONTRADICTION
    elif corroboration_count > 0 and base_confidence >= 0.60:
        verdict = "VERIFIED"
        method = _METHOD_CORROBORATION
    elif is_statistical and stat_matches == 0:
        verdict = "UNVERIFIABLE"
        method = _METHOD_STATISTICAL
    elif len(evidence_text.strip()) < 100:
        verdict = "INSUFFICIENT_EVIDENCE"
        method = _METHOD_INSUFFICIENT
    else:
        verdict = "UNVERIFIABLE"
        method = _METHOD_HEDGED

    return VerificationResult(
        claim_text=claim_text,
        verdict=verdict,
        confidence=round(base_confidence, 4),
        evidence_count=len(sources),
        contradictions=contradictions,
        supporting_sources=sources,
        verification_method=method,
    )


class VerifierWorker(BaseWorker):
    """
    Tier-3 claim verification worker.
    Verifies factual claims against provided evidence context using
    multi-signal rule-based scoring (corroboration, contradiction, hedging).
    Cost: ~₹0.05 per call (Tier-3 reasoning, local model).
    """

    name = "VerifierWorker"
    tier = 3
    use_static = False   # Tier-3 generation — not a STATIC decoder
    capabilities = {"CLAIM_VERIFY", "EVIDENCE_CHECK", "CONTRADICTION_DETECT"}
    max_retries = 1
    timeout_seconds = 45

    async def setup(self) -> None:
        await super().setup()

    async def teardown(self) -> None:
        await super().teardown()

    async def process(self, input_data: dict) -> dict:
        """
        Input:
            text: str            — Claim text to verify
            evidence: str        — Evidence context (article snippets, reports, etc.)
            trace_id: str
        Output:
            result: VerificationResult.model_dump()
            meta: {worker, tier, cost_inr, trace_id, timestamp}
        """
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

        verification = _verify_claim(claim_text.strip(), evidence_text)

        return {
            "result": verification.model_dump(),
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.05,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

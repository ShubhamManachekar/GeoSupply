"""AuthorWorker — Tier-3 author attribution and bot-detection analysis."""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import AuthorProfile, WorkerError

# ── Bot-behaviour patterns ─────────────────────────────────────────────────────
_BOT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(.{10,40})\1{2,}", re.S), "repetitive_template"),
    (re.compile(r"\b(click|share|retweet|follow|subscribe|like now|join us)\b", re.I), "cta_injection"),
    (re.compile(r"https?://\S+\s+https?://\S+\s+https?://\S+", re.I), "link_flooding"),
    (re.compile(r"[A-Z]{5,}", re.I), "all_caps_burst"),
    (re.compile(r"[!?]{3,}", re.I), "excessive_punctuation"),
]

# ── State-sponsored propaganda markers ────────────────────────────────────────
_STATE_SPONSORED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(xinhua|cgtn|tass|rt\.com|sputnik|pravda|global times|people's daily)\b", re.I),
     "state_media_mention"),
    (re.compile(r"\b(western propaganda|imperialist|hegemon\w*|sovereignty violation)\b", re.I),
     "anti-western_framing"),
    (re.compile(r"\b(narrative control|information war|hybrid war|lawfare|colour revolution)\b", re.I),
     "information_warfare_lexicon"),
    (re.compile(r"\b(motherland|sacred soil|national dignity|territorial integrity)\b", re.I),
     "nationalist_rhetoric"),
    (re.compile(r"\b(pak|isi|deep state|khalistani|separatist)\b", re.I),
     "india_adversary_framing"),
]

# ── Human register markers ─────────────────────────────────────────────────────
_HUMAN_FORMAL_PATTERNS = re.compile(
    r"\b(according to|analysis shows|data indicates|experts warn|officials say)\b", re.I
)
_HUMAN_INFORMAL_PATTERNS = re.compile(
    r"\b(folks|tbh|fwiw|imho|lol|btw|omg|ngl|honestly|just saying)\b", re.I
)
_TECHNICAL_PATTERNS = re.compile(
    r"\b(algorithm|neural network|regression|variance|p-value|coefficient|GDP|CAGR|EBITDA)\b", re.I
)
_PROPAGANDA_PATTERNS = re.compile(
    r"\b(brainwashed|sheeple|woke|deep state|cabal|globalist|rigged|puppet)\b", re.I
)

# ── Stylometric features ───────────────────────────────────────────────────────
def _avg_sentence_length(text: str) -> float:
    """Average words per sentence — bots tend toward uniform lengths."""
    sentences = re.split(r"[.!?]+", text)
    lengths = [len(s.split()) for s in sentences if s.strip()]
    return statistics.mean(lengths) if lengths else 0.0


def _sentence_length_variance(text: str) -> float:
    """High variance → human; low variance → bot."""
    sentences = re.split(r"[.!?]+", text)
    lengths = [len(s.split()) for s in sentences if s.strip()]
    if len(lengths) < 2:
        return 0.0
    return statistics.variance(lengths)


def _vocabulary_richness(text: str) -> float:
    """Type-token ratio — high ratio → human/formal."""
    words = re.findall(r"\b[a-z]+\b", text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def _detect_language_register(text: str) -> str:
    formal_count = len(_HUMAN_FORMAL_PATTERNS.findall(text))
    informal_count = len(_HUMAN_INFORMAL_PATTERNS.findall(text))
    tech_count = len(_TECHNICAL_PATTERNS.findall(text))
    prop_count = len(_PROPAGANDA_PATTERNS.findall(text))

    if prop_count >= 2:
        return "PROPAGANDA"
    if tech_count >= 2:
        return "TECHNICAL"
    if formal_count > informal_count:
        return "FORMAL"
    if informal_count > 0:
        return "INFORMAL"
    return "FORMAL"  # default


def _compute_bot_probability(text: str) -> tuple[float, list[str]]:
    """
    Return (bot_probability 0-1, list_of_detected_markers).
    """
    markers: list[str] = []
    bot_score = 0.0

    for pat, label in _BOT_PATTERNS:
        if pat.search(text):
            markers.append(label)
            bot_score += 0.18

    # Stylometric signals
    var_ = _sentence_length_variance(text)
    ttr = _vocabulary_richness(text)
    avg_len = _avg_sentence_length(text)

    # Very uniform sentence length → bot indicator
    if var_ < 2.0 and len(text) > 100:
        bot_score += 0.10
        markers.append("uniform_sentence_length")

    # Very low type-token ratio → bot indicator
    if ttr < 0.35 and len(text) > 80:
        bot_score += 0.08
        markers.append("low_vocabulary_richness")

    # Very long average sentence → template bloat
    if avg_len > 35:
        bot_score += 0.05
        markers.append("long_average_sentence")

    return min(1.0, round(bot_score, 4)), markers


def _compute_state_sponsored(text: str) -> tuple[float, list[str]]:
    """
    Return (state_sponsored_probability 0-1, list_of_indicators).
    """
    indicators: list[str] = []
    score = 0.0

    for pat, label in _STATE_SPONSORED_PATTERNS:
        if pat.search(text):
            indicators.append(label)
            score += 0.20

    return min(1.0, round(score, 4)), indicators


def _classify_author(
    bot_prob: float,
    state_prob: float,
    bot_markers: list[str],
    state_indicators: list[str],
) -> tuple[str, float]:
    """
    Map probabilities to author_type and attribution_confidence.
    Priority: STATE_SPONSORED > BOT > HUMAN > UNKNOWN
    """
    if state_prob >= 0.40:
        return "STATE_SPONSORED", round(state_prob, 4)
    if bot_prob >= 0.45:
        return "BOT", round(bot_prob, 4)
    if bot_prob < 0.20 and state_prob < 0.20:
        # Human confidence based on stylometric richness
        return "HUMAN", 0.72
    return "UNKNOWN", 0.50


class AuthorWorker(BaseWorker):
    """
    Tier-3 author attribution and bot-detection worker.
    Classifies text authors as HUMAN/BOT/STATE_SPONSORED/UNKNOWN using
    stylometric analysis, propaganda lexicon detection, and bot-pattern matching.
    Cost: ~₹0.05 per call (Tier-3 analysis, local model).
    """

    name = "AuthorWorker"
    tier = 3
    use_static = False
    capabilities = {"AUTHOR_CLASSIFY", "BOT_DETECT", "PROPAGANDA_FLAG", "STYLE_ANALYSIS"}
    max_retries = 1
    timeout_seconds = 45

    async def setup(self) -> None:
        await super().setup()

    async def teardown(self) -> None:
        await super().teardown()

    async def process(self, input_data: dict) -> dict:
        """
        Input:
            text: str        — Text to analyse for author attribution
            trace_id: str
        Output:
            result: AuthorProfile.model_dump()
            meta: {worker, tier, cost_inr, trace_id, timestamp}
        """
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("text") or input_data.get("sanitised_text") or ""

        if not isinstance(text, str) or not text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="text is required and must be non-empty",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        text = text.strip()

        bot_prob, bot_markers = _compute_bot_probability(text)
        state_prob, state_indicators = _compute_state_sponsored(text)
        author_type, attribution_confidence = _classify_author(
            bot_prob, state_prob, bot_markers, state_indicators
        )
        language_register = _detect_language_register(text)

        # Merge all style markers
        style_markers = bot_markers + state_indicators
        # Add register as a marker if not already there
        if language_register not in style_markers:
            style_markers.append(f"register:{language_register.lower()}")

        profile = AuthorProfile(
            author_type=author_type,
            attribution_confidence=attribution_confidence,
            style_markers=style_markers[:10],  # cap at 10
            bot_probability=bot_prob,
            state_sponsor_indicators=state_indicators,
            language_register=language_register,
        )

        return {
            "result": profile.model_dump(),
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.05,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""CIBWorker - Tier-2 Coordinated Inauthentic Behaviour and bot network detection."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

# Signals of coordinated inauthentic behaviour
_BOT_SIGNALS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"(share|repost|forward|spread).{0,30}(now|immediately|urgent)", re.I),
     "AMPLIFICATION_CALL", 0.20),
    (re.compile(r"#\w+\s+#\w+\s+#\w+", re.I),
     "HASHTAG_FLOOD", 0.15),
    (re.compile(r"\b(bot|automated|script|click farm|fake account)\b", re.I),
     "EXPLICIT_BOT_REF", 0.30),
    (re.compile(r"(copy.{0,10}paste|copy this|paste this)", re.I),
     "COPY_PASTE_INSTRUCTION", 0.25),
    (re.compile(r"\b(trending|make it trend|trending now)\b", re.I),
     "TREND_MANIPULATION", 0.15),
    (re.compile(r"(report|flag|block).{0,20}(account|user|profile)", re.I),
     "MASS_REPORTING", 0.20),
]

# Narrative coordination signals
_COORD_SIGNALS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\b(narrative|talking point|message discipline)\b", re.I),
     "NARRATIVE_SYNC", 0.25),
    (re.compile(r"\b(astroturf|sockpuppet|persona)\b", re.I),
     "ASTROTURFING", 0.35),
    (re.compile(r"(multiple|several|many).{0,20}(account|profile|handle)", re.I),
     "MULTI_ACCOUNT", 0.20),
    (re.compile(r"\b(state.?media|state.?sponsor|foreign.?influence)\b", re.I),
     "STATE_ACTOR", 0.30),
]


def _detect_signals(
    text: str, patterns: list[tuple[re.Pattern[str], str, float]]
) -> tuple[list[str], float]:
    found: list[str] = []
    score = 0.0
    for pattern, label, weight in patterns:
        if pattern.search(text):
            found.append(label)
            score += weight
    return found, min(1.0, score)


class CIBWorker(BaseWorker):
    """
    Detect Coordinated Inauthentic Behaviour (CIB) signals and bot-network
    indicators in social-media or narrative text.

    Input fields:
        text (str): Message, post, or article to analyse.
        sanitised_text (str, optional): Pre-sanitised version (preferred).
    """

    name = "CIBWorker"
    tier = 2
    use_static = False
    capabilities = {"CIB_DETECT", "BOT_NETWORK"}
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

        bot_signals, bot_score = _detect_signals(text, _BOT_SIGNALS)
        coord_signals, coord_score = _detect_signals(text, _COORD_SIGNALS)

        all_signals = bot_signals + coord_signals
        composite_score = round(min(1.0, (bot_score + coord_score) / 2.0 + 0.10 * bool(all_signals)), 4)
        is_cib = composite_score >= 0.30

        return {
            "result": {
                "cib_score": composite_score,
                "is_cib": is_cib,
                "bot_signals": bot_signals,
                "coordination_signals": coord_signals,
                "all_signals": all_signals,
                "confidence": round(min(1.0, 0.40 + composite_score * 0.60), 4),
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

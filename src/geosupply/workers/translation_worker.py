"""TranslationWorker - deterministic multi-language translation scaffold."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

SUPPORTED_LANGS = frozenset(
    {"en", "hi", "bn", "ta", "te", "mr", "gu", "pa", "ur", "fr", "es", "ar"}
)

_LEXICON: dict[tuple[str, str], dict[str, str]] = {
    ("en", "hi"): {
        "hello": "namaste",
        "world": "duniya",
        "risk": "jokhim",
        "market": "bazaar",
    },
    ("en", "es"): {
        "hello": "hola",
        "world": "mundo",
        "risk": "riesgo",
        "market": "mercado",
    },
}


def _detect_language(text: str) -> str:
    # Devanagari block is treated as Hindi for routing fallback.
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return "en"


def _translate_tokens(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang == target_lang:
        return text

    lexicon = _LEXICON.get((source_lang, target_lang), {})
    if not lexicon:
        return f"[{target_lang}] {text}"

    tokens = text.split()
    translated = [lexicon.get(token.lower(), token) for token in tokens]
    return " ".join(translated)


class TranslationWorker(BaseWorker):
    """Translate short text segments across 12 supported languages."""

    name = "TranslationWorker"
    tier = 2
    use_static = False
    capabilities = {"TRANSLATE", "12_LANGS"}
    max_retries = 2
    timeout_seconds = 30

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("text")
        target_lang = str(input_data.get("target_lang", "")).lower().strip()
        source_lang = str(input_data.get("source_lang", "")).lower().strip()

        if not isinstance(text, str) or not text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'text' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if not target_lang:
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing 'target_lang' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if target_lang not in SUPPORTED_LANGS:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Unsupported target_lang '{target_lang}'",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if not source_lang:
            source_lang = _detect_language(text)

        if source_lang not in SUPPORTED_LANGS:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Unsupported source_lang '{source_lang}'",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        translated_text = _translate_tokens(text, source_lang, target_lang)

        return {
            "result": {
                "source_lang": source_lang,
                "target_lang": target_lang,
                "translated_text": translated_text,
                "quality": "heuristic",
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

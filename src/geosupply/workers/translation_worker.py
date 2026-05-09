"""TranslationWorker — multi-language translation across 12 supported languages.

Primary path: Claude Haiku 4.5 (high-quality translation).
Fallback path: deterministic lexicon (used when SDK/key unavailable).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError
from geosupply.workers.claude_mixin import ClaudeWorkerMixin

SUPPORTED_LANGS = frozenset(
    {"en", "hi", "bn", "ta", "te", "mr", "gu", "pa", "ur", "fr", "es", "ar"}
)

_LANG_NAMES = {
    "en": "English", "hi": "Hindi", "bn": "Bengali", "ta": "Tamil",
    "te": "Telugu", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi",
    "ur": "Urdu", "fr": "French", "es": "Spanish", "ar": "Arabic",
}

# Lexicon fallback — covers only the most common supply-chain terms
_LEXICON: dict[tuple[str, str], dict[str, str]] = {
    ("en", "hi"): {"hello": "namaste", "world": "duniya", "risk": "jokhim", "market": "bazaar"},
    ("en", "es"): {"hello": "hola", "world": "mundo", "risk": "riesgo", "market": "mercado"},
}

_SYSTEM_PROMPT = """You are a professional translator specializing in geopolitical, supply-chain, and trade intelligence content.
Translate the given text accurately into the requested language.
Preserve technical terms, entity names, and numerical values exactly.
Return ONLY the translated text — no explanations, no notes, no source text."""


def _detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    return "en"


def _lexicon_translate(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang == target_lang:
        return text
    lexicon = _LEXICON.get((source_lang, target_lang), {})
    if not lexicon:
        return f"[{target_lang}] {text}"
    tokens = text.split()
    return " ".join(lexicon.get(t.lower(), t) for t in tokens)


class TranslationWorker(ClaudeWorkerMixin, BaseWorker):
    """Translate short text segments across 12 supported languages.

    Primary: Claude Haiku 4.5.
    Fallback: deterministic lexicon (en↔hi, en↔es only).
    """

    name = "TranslationWorker"
    tier = 2
    use_static = False
    capabilities = {"TRANSLATE", "12_LANGS"}
    max_retries = 2
    timeout_seconds = 30
    _max_tokens = 2048

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

        if source_lang == target_lang:
            return {
                "result": {
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "translated_text": text,
                    "quality": "passthrough",
                },
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.0,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        target_name = _LANG_NAMES.get(target_lang, target_lang)
        source_name = _LANG_NAMES.get(source_lang, source_lang)
        user_msg = (
            f"Translate the following text from {source_name} to {target_name}:\n\n{text.strip()}"
        )

        translated, cost_inr = await self._call_claude(_SYSTEM_PROMPT, user_msg)

        if translated:
            quality = "claude"
        else:
            translated = _lexicon_translate(text, source_lang, target_lang)
            quality = "heuristic"
            cost_inr = 0.0

        return {
            "result": {
                "source_lang": source_lang,
                "target_lang": target_lang,
                "translated_text": translated,
                "quality": quality,
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": cost_inr,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""
InputSanitiserWorker — Worker #34
FA v2 | Part II | Layer 5

Capabilities: SANITISE_INPUT, INJECTION_SCAN
Fixes: v9 LOOPHOLE 2 (STATIC decoder prompt length bypass)

All Tier-1 STATIC inputs MUST pass through this worker before processing.
Tier 0, no LLM needed — pure Python logic.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

from geosupply.config import STATIC_INPUT_TOKEN_LIMIT, STATIC_INPUT_TOKEN_WARN
from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)

# Known injection patterns (expandable)
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
    re.compile(r"###\s*(instruction|system|human|assistant)", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]", re.IGNORECASE),
    re.compile(r"(?:reveal|show|print)\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"jailbreak|DAN\s+mode", re.IGNORECASE),
]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def _normalise_unicode(text: str) -> str:
    """Normalise unicode to NFC form and strip control characters."""
    normalised = unicodedata.normalize("NFC", text)
    # Remove control characters except newlines and tabs
    cleaned = "".join(
        ch for ch in normalised
        if unicodedata.category(ch) not in ("Cc", "Cf")
        or ch in ("\n", "\t", "\r")
    )
    return cleaned


def _detect_injections(text: str) -> list[str]:
    """Scan text for known prompt injection patterns."""
    found: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            found.append(f"Pattern: {pattern.pattern[:40]}... at pos {match.start()}")
    return found


class InputSanitiserWorker(BaseWorker):
    """
    Sanitises all input before Tier-1 STATIC decoder processing.

    PIPELINE POSITION: First worker in any Tier-1 pipeline.

    CHECKS:
        1. Unicode normalisation (NFC)
        2. Token count (2048 hard limit, 1500 warn)
        3. Prompt injection detection (8 patterns)
        4. Control character stripping

    CAPABILITIES: SANITISE_INPUT, INJECTION_SCAN
    TIER: 0 (CPU only, no LLM)
    STATIC: No
    """

    name = "InputSanitiserWorker"
    tier = 0
    use_static = False
    capabilities = {"SANITISE_INPUT", "INJECTION_SCAN"}
    max_retries = 1  # No point retrying sanitisation
    timeout_seconds = 10

    async def process(self, input_data: dict) -> dict:
        """
        Sanitise input text.

        Args:
            input_data: {
                "text": str,           # required
                "trace_id": str,       # required
                "source": str,         # optional origin
            }

        Returns:
            dict with sanitised text, token count, injection findings
        """
        trace_id = input_data.get("trace_id", "unknown")
        raw_text = input_data.get("text")

        if not raw_text or not isinstance(raw_text, str):
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or non-string 'text' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # Step 1: Unicode normalisation
        cleaned = _normalise_unicode(raw_text)

        # Step 2: Token count check
        token_count = _estimate_tokens(cleaned)
        truncated = False

        if token_count > STATIC_INPUT_TOKEN_LIMIT:
            # Hard truncate at limit
            char_limit = STATIC_INPUT_TOKEN_LIMIT * 4
            cleaned = cleaned[:char_limit]
            token_count = STATIC_INPUT_TOKEN_LIMIT
            truncated = True
            logger.warning(
                "%s: truncated input from ~%d to %d tokens [trace=%s]",
                self.name, _estimate_tokens(raw_text), token_count, trace_id,
            )

        token_warning = token_count > STATIC_INPUT_TOKEN_WARN

        # Step 3: Injection scan
        injections = _detect_injections(cleaned)
        is_suspicious = len(injections) > 0

        if is_suspicious:
            logger.warning(
                "%s: injection detected (%d patterns) [trace=%s]",
                self.name, len(injections), trace_id,
            )

        return {
            "result": {
                "sanitised_text": cleaned,
                "original_length": len(raw_text),
                "sanitised_length": len(cleaned),
                "token_count": token_count,
                "truncated": truncated,
                "token_warning": token_warning,
                "is_suspicious": is_suspicious,
                "injection_findings": injections,
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,  # CPU only — zero cost
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

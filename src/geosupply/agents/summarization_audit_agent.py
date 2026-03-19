"""
SummarizationAuditAgent — Layer 3 Agent
FA v2 | Part IV | MarketingSupervisor domain

Catches semantic distortion in marketing summaries and tweets.
Verifies that summary language severity band matches underlying score band.

Fixes: v9 GAP 2 — summaries were not checked for direction/magnitude distortion.

SEVERITY BANDS (from config.py):
    0.0-0.30  → minimal/negligible
    0.30-0.50 → low/modest
    0.50-0.70 → moderate/notable
    0.70-0.85 → high/significant
    0.85-1.00 → critical/severe

RULE: Summary language must NOT use a HIGHER band than the underlying score.

Capabilities: SUMMARIZATION_AUDIT, DISTORTION_CHECK, BAND_VERIFY
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from geosupply.config import SEVERITY_BANDS
from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Band keywords — ordered low→high (each list represents one band)
_BAND_KEYWORDS: list[tuple[str, list[str]]] = [
    ("minimal",  ["minimal", "negligible", "trivial", "minor", "slight"]),
    ("low",      ["low", "modest", "limited", "small", "marginal"]),
    ("moderate", ["moderate", "notable", "noticeable", "moderate", "considerable"]),
    ("high",     ["high", "significant", "substantial", "major", "serious", "severe"]),
    ("critical", ["critical", "extreme", "catastrophic", "crisis", "devastating", "urgent"]),
]
_BAND_ORDER = [b[0] for b in _BAND_KEYWORDS]


def _score_to_band(score: float) -> str:
    """Map a 0.0-1.0 score to its severity band name."""
    for band_name, (lo, hi) in SEVERITY_BANDS.items():
        if lo <= score < hi:
            return band_name
    return "critical"   # score == 1.0 edge case


def _detect_band_in_text(text: str) -> str | None:
    """
    Find the HIGHEST severity band keyword present in text.
    Returns the band name or None if no keywords match.
    """
    text_lower = text.lower()
    detected = None
    for band_name, keywords in _BAND_KEYWORDS:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                detected = band_name   # keep highest match
    return detected


def _band_index(band: str) -> int:
    """Return ordinal of band (0=minimal … 4=critical)."""
    try:
        return _BAND_ORDER.index(band)
    except ValueError:
        return -1


class SummarizationAuditAgent(BaseAgent):
    """
    Audits marketing summaries / tweets for severity band distortion.

    TASK ACTIONS:
        audit       → check one summary against one score
        batch_audit → check list of {summary, score} pairs
        health      → agent status

    VERDICT:
        PASS            — summary band ≤ score band (or no keywords detected)
        FAIL_EXAGGERATED — summary uses a higher band than the score warrants
        UNVERIFIABLE    — no band keywords found in summary
    """

    name = "SummarizationAuditAgent"
    domain = "quality"
    capabilities = {"SUMMARIZATION_AUDIT", "DISTORTION_CHECK", "BAND_VERIFY"}
    max_concurrent = 10

    def __init__(self) -> None:
        super().__init__()
        self._total_audited: int = 0
        self._total_exaggerated: int = 0

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "audit")

        if action == "audit":
            return self._handle_audit(task)
        elif action == "batch_audit":
            return self._handle_batch_audit(task)
        elif action == "health":
            return self._handle_health()
        else:
            return {
                "result": {"error": f"Unknown action: {action}"},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

    def _handle_audit(self, task: dict) -> dict:
        """
        Audit a single summary against an underlying score.

        task keys:
            summary     str    — the marketing summary / tweet text
            score       float  — underlying risk/confidence score (0.0-1.0)
            trace_id    str
        """
        trace_id = task.get("trace_id", "unknown")
        summary = str(task.get("summary", "")).strip()
        score = float(task.get("score", 0.0))
        score = max(0.0, min(1.0, score))

        if not summary:
            return {
                "result": {"error": "summary is required"},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        score_band = _score_to_band(score)
        text_band = _detect_band_in_text(summary)

        if text_band is None:
            verdict = "UNVERIFIABLE"
            distortion_delta = 0
        elif _band_index(text_band) > _band_index(score_band):
            verdict = "FAIL_EXAGGERATED"
            distortion_delta = _band_index(text_band) - _band_index(score_band)
        else:
            verdict = "PASS"
            distortion_delta = 0

        self._total_audited += 1
        if verdict == "FAIL_EXAGGERATED":
            self._total_exaggerated += 1
            logger.warning(
                "%s: FAIL_EXAGGERATED — score=%.3f (%s) but text uses '%s' [trace=%s]",
                self.name, score, score_band, text_band, trace_id,
            )

        return {
            "result": {
                "verdict": verdict,
                "score": score,
                "score_band": score_band,
                "detected_band": text_band,
                "distortion_delta": distortion_delta,
                "summary_snippet": summary[:100],
                "trace_id": trace_id,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _handle_batch_audit(self, task: dict) -> dict:
        """Audit a list of {summary, score} pairs."""
        trace_id = task.get("trace_id", "unknown")
        items: list[dict] = task.get("items", [])

        if not items:
            return {
                "result": {"error": "items list is empty"},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        results = []
        for item in items:
            item["trace_id"] = trace_id
            r = self._handle_audit(item)
            results.append(r["result"])

        exaggerated_count = sum(1 for r in results if r.get("verdict") == "FAIL_EXAGGERATED")
        return {
            "result": {
                "batch_results": results,
                "total": len(results),
                "exaggerated_count": exaggerated_count,
                "pass_count": sum(1 for r in results if r.get("verdict") == "PASS"),
            },
            "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
        }

    def _handle_health(self) -> dict:
        return {
            "result": {
                "status": "healthy",
                "total_audited": self._total_audited,
                "total_exaggerated": self._total_exaggerated,
                "exaggeration_rate": self._total_exaggerated / max(self._total_audited, 1),
            },
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }

    @property
    def stats(self) -> dict:
        return {
            "total_audited": self._total_audited,
            "total_exaggerated": self._total_exaggerated,
        }

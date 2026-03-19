"""
SemanticDriftMonitor — Layer 4 SubAgent
FA v2 | Part III | §3.2 — Source semantic drift detection

Detects when a source channel has semantically drifted from its baseline
using KL divergence on n-gram frequency distributions.

PIPELINE:
    Step 1: load_baselines     — retrieve ChannelFingerprint baselines (from input)
    Step 2: compute_current    — build n-gram distribution from recent messages
    Step 3: kl_divergence      — KL(current || baseline) per channel
    Step 4: classify_drift     — NORMAL / WARN / SUSPEND / SILENT
    Step 5: emit_alerts        — publish drift events to EventBus

Alert levels:
    NORMAL : KL < CHANNEL_KL_WARN_THRESHOLD (0.30)
    WARN   : 0.30 ≤ KL < CHANNEL_KL_SUSPEND_THRESHOLD (0.60)
    SUSPEND: KL ≥ CHANNEL_KL_SUSPEND_THRESHOLD (0.60)
    SILENT : no messages in last CHANNEL_SILENT_ALERT_DAYS (7) days

Parallel steps: {compute_current, kl_divergence} for multiple channels
Cost: ₹0.0 (pure Python, no LLM)
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone

from geosupply.config import (
    CHANNEL_BASELINE_MIN_MESSAGES,
    CHANNEL_KL_SUSPEND_THRESHOLD,
    CHANNEL_KL_WARN_THRESHOLD,
    CHANNEL_SILENT_ALERT_DAYS,
)
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import DriftReport, Event

logger = logging.getLogger(__name__)


# ============================================================
# Module-level helpers
# ============================================================

def kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """
    KL(P || Q) — measure how much P has drifted from baseline Q.
    Epsilon smoothing: add 1e-10 to avoid log(0).
    """
    vocab = set(p) | set(q)
    eps = 1e-10
    return sum(
        p.get(w, eps) * math.log((p.get(w, eps)) / (q.get(w, eps) + eps))
        for w in vocab
        if p.get(w, eps) > 0
    )


def build_ngram_dist(messages: list[str], n: int = 2) -> dict[str, float]:
    """Build normalised n-gram frequency distribution from a list of messages."""
    counts: dict[str, int] = {}
    total = 0
    for msg in messages:
        tokens = re.findall(r"\b[a-z]{2,}\b", msg.lower())
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            counts[gram] = counts.get(gram, 0) + 1
            total += 1
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _days_since(iso_date_str: str) -> float:
    """Return float days between now and an ISO-format date string."""
    try:
        dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 86400
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# SemanticDriftMonitor
# ============================================================

class SemanticDriftMonitor(BaseSubAgent):
    """
    Monitors source channels for semantic drift from their baselines.

    PIPELINE:
        load_baselines → compute_current → kl_divergence → classify_drift → emit_alerts

    USAGE:
        result = await monitor.run({
            "channels": [
                {
                    "channel_id": "ch-001",
                    "recent_messages": ["port closure supply chain risk"],
                    "baseline_ngrams": {"supply chain": 0.5, "port risk": 0.5},
                    "last_message_at": "2024-01-01T00:00:00Z",
                    "message_count": 500,
                },
            ],
            "trace_id": "sdm-001",
        })
    """

    name = "SemanticDriftMonitor"
    pipeline_steps = [
        "load_baselines",
        "compute_current",
        "kl_divergence",
        "classify_drift",
        "emit_alerts",
    ]
    parallel_steps = {"compute_current", "kl_divergence"}

    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    async def run(self, input_data: dict) -> dict:
        """
        Detect semantic drift across all input channels.

        Input:
            channels  list[dict]  — channel objects with:
                channel_id       str        — unique channel identifier
                recent_messages  list[str]  — messages from the last week
                baseline_ngrams  dict       — pre-computed baseline n-gram dist
                                             (empty dict = skip KL)
                last_message_at  str|None   — ISO datetime of most recent message
                message_count    int        — total historical messages
            trace_id  str

        Output:
            result:
                drift_report    list[dict]  — DriftReport objects (serialised)
                total_channels  int
                warn_count      int
                suspend_count   int
                silent_count    int
            meta:
                subagent        str
                cost_inr        float       — always 0.0 (no LLM)
                trace_id        str
        """
        trace_id = input_data.get("trace_id", "")
        channels: list[dict] = input_data.get("channels", [])

        if not channels:
            return {
                "result": {
                    "drift_report": [],
                    "total_channels": 0,
                    "warn_count": 0,
                    "suspend_count": 0,
                    "silent_count": 0,
                },
                "meta": {
                    "subagent": self.name,
                    "cost_inr": 0.0,
                    "trace_id": trace_id,
                },
            }

        # ------------------------------------------------------------------
        # Step 1: load_baselines — baselines come directly from input_data.
        # ------------------------------------------------------------------
        # (pass-through; each channel carries its own baseline_ngrams)

        # ------------------------------------------------------------------
        # Steps 2 & 3: compute_current + kl_divergence (logically parallel
        # per channel — pure Python, run synchronously in a single pass)
        # ------------------------------------------------------------------
        drift_reports: list[DriftReport] = []

        for channel in channels:
            cid: str = channel.get("channel_id", "unknown")
            recent_messages: list[str] = channel.get("recent_messages", [])
            baseline_ngrams: dict = channel.get("baseline_ngrams", {})
            last_message_at: str | None = channel.get("last_message_at")
            message_count: int = channel.get("message_count", 0)

            # Step 2: compute current n-gram distribution
            current_dist = build_ngram_dist(recent_messages)

            # Step 3: determine whether baseline is usable
            baseline_available = bool(baseline_ngrams) and (
                message_count >= CHANNEL_BASELINE_MIN_MESSAGES
            )

            kl: float = 0.0
            if baseline_available:
                kl = max(0.0, kl_divergence(current_dist, baseline_ngrams))

            # ------------------------------------------------------------------
            # Step 4: classify_drift
            # ------------------------------------------------------------------
            if last_message_at and _days_since(last_message_at) >= CHANNEL_SILENT_ALERT_DAYS:
                alert_level = "SILENT"
                action = "alert_admin_silent"
            elif not baseline_available:
                alert_level = "NORMAL"
                action = "insufficient_baseline"
            elif kl >= CHANNEL_KL_SUSPEND_THRESHOLD:
                alert_level = "SUSPEND"
                action = "auto_suspend_source"
            elif kl >= CHANNEL_KL_WARN_THRESHOLD:
                alert_level = "WARN"
                action = "flag_for_review"
            else:
                alert_level = "NORMAL"
                action = "no_action"

            drift_reports.append(
                DriftReport(
                    channel_id=cid,
                    kl_score=kl,
                    alert_level=alert_level,
                    action=action,
                    message_count=message_count,
                )
            )

            if alert_level in ("WARN", "SUSPEND", "SILENT"):
                logger.warning(
                    "%s: channel=%s alert_level=%s kl=%.4f [trace=%s]",
                    self.name,
                    cid,
                    alert_level,
                    kl,
                    trace_id,
                )

        # ------------------------------------------------------------------
        # Step 5: emit_alerts — publish to EventBus for SUSPEND and SILENT
        # ------------------------------------------------------------------
        if self._event_bus is not None:
            for dr in drift_reports:
                if dr.alert_level == "SUSPEND":
                    event = Event(
                        topic="source.suspend",
                        source=self.name,
                        payload={
                            "channel_id": dr.channel_id,
                            "kl_score": dr.kl_score,
                            "trace_id": trace_id,
                        },
                    )
                    try:
                        await self._event_bus.publish(event)
                    except Exception as exc:
                        logger.warning(
                            "%s: failed to publish source.suspend event for %s: %s",
                            self.name,
                            dr.channel_id,
                            exc,
                        )

                elif dr.alert_level == "SILENT":
                    event = Event(
                        topic="source.silent_alert",
                        source=self.name,
                        payload={
                            "channel_id": dr.channel_id,
                            "trace_id": trace_id,
                        },
                    )
                    try:
                        await self._event_bus.publish(event)
                    except Exception as exc:
                        logger.warning(
                            "%s: failed to publish source.silent_alert event for %s: %s",
                            self.name,
                            dr.channel_id,
                            exc,
                        )

        # ------------------------------------------------------------------
        # Build and return summary
        # ------------------------------------------------------------------
        warn_count = sum(1 for dr in drift_reports if dr.alert_level == "WARN")
        suspend_count = sum(1 for dr in drift_reports if dr.alert_level == "SUSPEND")
        silent_count = sum(1 for dr in drift_reports if dr.alert_level == "SILENT")

        return {
            "result": {
                "drift_report": [dr.model_dump() for dr in drift_reports],
                "total_channels": len(channels),
                "warn_count": warn_count,
                "suspend_count": suspend_count,
                "silent_count": silent_count,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
            },
        }

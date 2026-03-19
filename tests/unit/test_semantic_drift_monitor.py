"""Tests for SemanticDriftMonitor — semantic drift detection via KL divergence."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from geosupply.subagents.semantic_drift_monitor import (
    SemanticDriftMonitor,
    build_ngram_dist,
    kl_divergence,
    _days_since,
)


# ============================================================
# Shared fixtures
# ============================================================

@pytest.fixture
async def monitor():
    m = SemanticDriftMonitor()
    await m.setup()
    yield m
    await m.teardown()


class _FakeBus:
    """Minimal EventBus stand-in that records published events."""

    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


# ============================================================
# Helper: build a channel dict for run() tests
# ============================================================

def _channel(
    channel_id: str = "ch-test",
    recent_messages: list[str] | None = None,
    baseline_ngrams: dict | None = None,
    last_message_at: str | None = None,
    message_count: int = 500,
) -> dict:
    return {
        "channel_id": channel_id,
        "recent_messages": recent_messages if recent_messages is not None else [],
        "baseline_ngrams": baseline_ngrams if baseline_ngrams is not None else {},
        "last_message_at": last_message_at,
        "message_count": message_count,
    }


# ============================================================
# Test 1: kl_divergence — identical distributions → KL ≈ 0
# ============================================================

class TestKLDivergence:
    def test_kl_divergence_identical_dists(self):
        """KL(P || P) should be effectively zero."""
        p = {"supply chain": 0.5, "port risk": 0.5}
        result = kl_divergence(p, p)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_kl_divergence_different_dists(self):
        """KL(P || Q) > 0 when distributions differ."""
        p = {"supply chain": 0.9, "port risk": 0.1}
        q = {"supply chain": 0.1, "port risk": 0.9}
        result = kl_divergence(p, q)
        assert result > 0.0

    def test_kl_divergence_epsilon_smoothing(self):
        """Disjoint vocabularies must not raise ZeroDivisionError or math domain error."""
        p = {"alpha beta": 1.0}
        q = {"gamma delta": 1.0}
        # Should return a finite positive number without exceptions
        result = kl_divergence(p, q)
        assert isinstance(result, float)
        assert result > 0.0


# ============================================================
# Tests 4–5: build_ngram_dist helpers
# ============================================================

class TestBuildNgramDist:
    def test_build_ngram_dist_empty(self):
        """Empty message list should produce an empty distribution."""
        result = build_ngram_dist([])
        assert result == {}

    def test_build_ngram_dist_normalised(self):
        """Distribution values should sum to approximately 1.0."""
        messages = [
            "supply chain disruption port closure",
            "trade route risk assessment geopolitical",
        ]
        dist = build_ngram_dist(messages)
        assert dist  # non-empty
        total = sum(dist.values())
        assert total == pytest.approx(1.0, abs=1e-6)


# ============================================================
# Tests 6–14: SemanticDriftMonitor.run()
# ============================================================

class TestRunAlertLevels:
    @pytest.mark.asyncio
    async def test_run_normal_channel(self, monitor):
        """Channel with KL ≈ 0 → NORMAL / no_action (baseline = same messages)."""
        messages = ["supply chain port risk supply chain port risk"]
        # Use build_ngram_dist on the same messages so KL(current || baseline) ≈ 0
        baseline = build_ngram_dist(messages)
        ch = _channel(
            channel_id="ch-normal",
            recent_messages=messages,
            baseline_ngrams=baseline,
            message_count=500,
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-normal"})
        report = result["result"]["drift_report"][0]
        assert report["kl_score"] == pytest.approx(0.0, abs=1e-6)
        assert report["alert_level"] == "NORMAL"
        assert report["action"] == "no_action"

    @pytest.mark.asyncio
    async def test_run_warn_channel(self, monitor):
        """Channel with KL in [0.30, 0.60) → WARN / flag_for_review.

        We engineer messages + baseline so KL is deterministically in WARN range:
          recent_messages = ["ab cd ab cd ab cd"]
            → tokens [ab, cd, ab, cd, ab, cd]
            → bigrams: "ab cd" ×3, "cd ab" ×2  (total 5)
            → P = {"ab cd": 0.6, "cd ab": 0.4}
          baseline_ngrams = {"ab cd": 0.2, "cd ab": 0.8}
            → Q shares exact same vocabulary, no eps-penalty on unknown bigrams
          KL(P||Q) = 0.6·ln(0.6/0.2) + 0.4·ln(0.4/0.8) ≈ 0.382  (WARN ✓)
        """
        ch = _channel(
            channel_id="ch-warn",
            recent_messages=["ab cd ab cd ab cd"],
            baseline_ngrams={"ab cd": 0.2, "cd ab": 0.8},
            message_count=500,
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-warn"})
        report = result["result"]["drift_report"][0]
        assert report["kl_score"] == pytest.approx(0.382, abs=0.01)
        assert report["alert_level"] == "WARN"
        assert report["action"] == "flag_for_review"

    @pytest.mark.asyncio
    async def test_run_suspend_channel(self, monitor):
        """Channel with KL ≥ 0.60 → SUSPEND / auto_suspend_source.

        We feed a completely divergent distribution to guarantee KL is very high.
        """
        # Baseline: supply-chain domain
        baseline = {"supply chain": 0.9, "port closure": 0.1}
        # Current messages: entirely different vocabulary (no bigram overlap)
        current_messages = [
            "election result victory parliament opposition majority",
            "political party election parliament opposition majority",
            "election majority parliament political victory opposition",
        ]
        ch = _channel(
            channel_id="ch-suspend",
            recent_messages=current_messages,
            baseline_ngrams=baseline,
            message_count=500,
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-suspend"})
        report = result["result"]["drift_report"][0]
        assert report["alert_level"] == "SUSPEND"
        assert report["action"] == "auto_suspend_source"
        assert report["kl_score"] >= 0.60

    @pytest.mark.asyncio
    async def test_run_silent_channel(self, monitor):
        """Channel with last message > 7 days ago → SILENT / alert_admin_silent."""
        ten_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()
        ch = _channel(
            channel_id="ch-silent",
            recent_messages=[],
            baseline_ngrams={"supply chain": 1.0},
            last_message_at=ten_days_ago,
            message_count=500,
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-silent"})
        report = result["result"]["drift_report"][0]
        assert report["alert_level"] == "SILENT"
        assert report["action"] == "alert_admin_silent"

    @pytest.mark.asyncio
    async def test_run_insufficient_baseline(self, monitor):
        """Channel with message_count < 100 → NORMAL / insufficient_baseline."""
        ch = _channel(
            channel_id="ch-insuff",
            recent_messages=["supply chain port risk"],
            baseline_ngrams={"supply chain": 0.5, "port risk": 0.5},
            message_count=50,  # below CHANNEL_BASELINE_MIN_MESSAGES (100)
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-insuff"})
        report = result["result"]["drift_report"][0]
        assert report["alert_level"] == "NORMAL"
        assert report["action"] == "insufficient_baseline"

    @pytest.mark.asyncio
    async def test_run_returns_counts(self, monitor):
        """Mixed channels → warn_count and suspend_count match alert levels."""
        ten_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()

        # Channel 1: NORMAL (no drift — baseline matches current distribution)
        normal_msgs = ["supply chain port risk supply chain port risk"]
        ch_normal = _channel(
            channel_id="ch-c1",
            recent_messages=normal_msgs,
            baseline_ngrams=build_ngram_dist(normal_msgs),
            message_count=500,
        )

        # Channel 2: SUSPEND (completely different vocab)
        ch_suspend = _channel(
            channel_id="ch-c2",
            recent_messages=[
                "election parliament opposition majority political victory",
                "political party election parliament opposition majority",
            ],
            baseline_ngrams={"supply chain": 0.9, "port closure": 0.1},
            message_count=500,
        )

        # Channel 3: SILENT
        ch_silent = _channel(
            channel_id="ch-c3",
            baseline_ngrams={"supply chain": 1.0},
            last_message_at=ten_days_ago,
            message_count=500,
        )

        result = await monitor.run({
            "channels": [ch_normal, ch_suspend, ch_silent],
            "trace_id": "t-counts",
        })
        r = result["result"]
        assert r["total_channels"] == 3
        assert r["suspend_count"] >= 1
        assert r["silent_count"] == 1


class TestRunEventBus:
    @pytest.mark.asyncio
    async def test_run_publishes_suspend_event(self):
        """SUSPEND channel triggers event_bus.publish with topic 'source.suspend'."""
        bus = _FakeBus()
        monitor = SemanticDriftMonitor(event_bus=bus)
        await monitor.setup()

        ch = _channel(
            channel_id="ch-pub-suspend",
            recent_messages=[
                "election parliament opposition majority political victory",
                "political party election parliament opposition majority",
            ],
            baseline_ngrams={"supply chain": 0.9, "port closure": 0.1},
            message_count=500,
        )
        await monitor.run({"channels": [ch], "trace_id": "t-pub-suspend"})

        await monitor.teardown()

        suspend_events = [e for e in bus.published if e.topic == "source.suspend"]
        assert len(suspend_events) >= 1
        assert suspend_events[0].payload["channel_id"] == "ch-pub-suspend"
        assert suspend_events[0].payload["trace_id"] == "t-pub-suspend"

    @pytest.mark.asyncio
    async def test_run_publishes_silent_event(self):
        """SILENT channel triggers event_bus.publish with topic 'source.silent_alert'."""
        bus = _FakeBus()
        monitor = SemanticDriftMonitor(event_bus=bus)
        await monitor.setup()

        ten_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()
        ch = _channel(
            channel_id="ch-pub-silent",
            baseline_ngrams={"supply chain": 1.0},
            last_message_at=ten_days_ago,
            message_count=500,
        )
        await monitor.run({"channels": [ch], "trace_id": "t-pub-silent"})

        await monitor.teardown()

        silent_events = [e for e in bus.published if e.topic == "source.silent_alert"]
        assert len(silent_events) == 1
        assert silent_events[0].payload["channel_id"] == "ch-pub-silent"
        assert silent_events[0].payload["trace_id"] == "t-pub-silent"


class TestRunMeta:
    @pytest.mark.asyncio
    async def test_run_meta_cost_zero(self, monitor):
        """meta['cost_inr'] must always be 0.0 (no LLM calls)."""
        ch = _channel(
            channel_id="ch-cost",
            recent_messages=["supply chain port risk"],
            baseline_ngrams={"supply chain": 0.5, "port risk": 0.5},
            message_count=500,
        )
        result = await monitor.run({"channels": [ch], "trace_id": "t-cost"})
        assert result["meta"]["cost_inr"] == 0.0
        assert result["meta"]["subagent"] == "SemanticDriftMonitor"
        assert result["meta"]["trace_id"] == "t-cost"

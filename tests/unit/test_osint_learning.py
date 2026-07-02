"""
Self-reinforcement suite tests: RAG feedback learner + adaptive threshold
calibrator + their API endpoints. All real logic, no mocks (project rule).
"""
from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from geosupply.osint.calibration import (
    BAND_MAX,
    BAND_MIN,
    DEFAULT_BANDS,
    MIN_SAMPLES,
    ThresholdCalibrator,
)
from geosupply.osint.models import NewsItem, OsintSnapshot
from geosupply.osint.rag import answer_query
from geosupply.osint.rag_feedback import (
    FEEDBACK_CAP,
    FEEDBACK_FLOOR,
    FeedbackEvent,
    RagFeedback,
)


def _news(title: str, source: str, priority: int = 2,
          entities: list[str] | None = None) -> NewsItem:
    return NewsItem(id=f"n-{hash((title, source))}", title=title, source=source,
                    priority=priority, entities=entities or [])


# ---------------------------------------------------------------------------
# RAG feedback learner
# ---------------------------------------------------------------------------

class TestRagFeedback:
    def test_upvote_raises_weight_downvote_lowers(self):
        fb = RagFeedback()
        fb.apply([FeedbackEvent(source="GoodWire", kind="news", vote=1)])
        fb.apply([FeedbackEvent(source="BadWire", kind="news", vote=-1)])
        assert fb.weight("GoodWire") > 1.0
        assert fb.weight("BadWire") < 1.0
        assert fb.weight("Unseen") == 1.0     # untouched sources unchanged

    def test_bounded_never_beyond_floor_or_cap(self):
        fb = RagFeedback()
        for _ in range(100):
            fb.apply([FeedbackEvent(source="A", kind="news", vote=1),
                      FeedbackEvent(source="B", kind="news", vote=-1)])
        assert fb.weight("A") <= FEEDBACK_CAP
        assert fb.weight("B") >= FEEDBACK_FLOOR   # downweighted, never silenced

    def test_zero_or_invalid_votes_ignored(self):
        fb = RagFeedback()
        accepted = fb.apply([
            FeedbackEvent(source="X", kind="news", vote=0),
            FeedbackEvent(source="", kind="news", vote=1),
        ])
        assert accepted == 0
        assert fb.weight("X") == 1.0

    def test_summary_gated_by_min_votes(self):
        fb = RagFeedback()
        fb.apply([FeedbackEvent(source="A", kind="news", vote=1)])
        assert fb.summary() == []          # 1 vote < trust gate
        for _ in range(3):
            fb.apply([FeedbackEvent(source="A", kind="news", vote=1)])
        rows = fb.summary()
        assert rows and rows[0]["source"] == "A"
        assert fb.trained_sources == 1

    def test_state_roundtrip(self):
        fb = RagFeedback()
        for _ in range(4):
            fb.apply([FeedbackEvent(source="A", kind="news", vote=1)])
        restored = RagFeedback()
        restored.load_state(fb.to_state())
        assert restored.weight("A") == fb.weight("A")
        assert restored.trained_sources == 1

    def test_retrieval_reweighted_by_feedback(self):
        """The loop actually closes: a downvoted source sinks in citations."""
        news = [
            _news("Hormuz missile attack shakes shipping", "TrustedWire",
                  entities=["Iran", "Strait of Hormuz"]),
            _news("Hormuz missile attack panic special", "JunkWire",
                  entities=["Iran", "Strait of Hormuz"]),
        ]
        snap = OsintSnapshot(news=news)
        fb = RagFeedback()
        for _ in range(6):
            fb.apply([FeedbackEvent(source="JunkWire", kind="news", vote=-1),
                      FeedbackEvent(source="TrustedWire", kind="news", vote=1)])
        ans = answer_query("hormuz attack", snap, source_weight=fb.weight)
        news_cites = [c for c in ans.citations if c.kind == "news"]
        assert news_cites, "expected news citations"
        trusted = next(c for c in news_cites if c.source == "TrustedWire")
        junk = next(c for c in news_cites if c.source == "JunkWire")
        assert trusted.score > junk.score


# ---------------------------------------------------------------------------
# Adaptive threshold calibrator
# ---------------------------------------------------------------------------

class TestThresholdCalibrator:
    def test_defaults_until_min_samples(self):
        cal = ThresholdCalibrator()
        cal.observe([0.9] * (MIN_SAMPLES - 1))
        assert cal.bands() == DEFAULT_BANDS

    def test_noisy_world_raises_cutoffs(self):
        """Persistently high stress → bands drift up (less alarm fatigue)."""
        cal = ThresholdCalibrator()
        cal.observe([0.7, 0.8, 0.85, 0.9] * 100)
        e, h, c = cal.bands()
        assert e > DEFAULT_BANDS[0]
        assert c > DEFAULT_BANDS[2] or c == BAND_MAX[2]

    def test_quiet_world_lowers_cutoffs(self):
        """Persistently low stress → bands drift down (stay sensitive)."""
        cal = ThresholdCalibrator()
        cal.observe([0.0, 0.05, 0.1, 0.15] * 100)
        e, h, c = cal.bands()
        assert e < DEFAULT_BANDS[0]
        assert c < DEFAULT_BANDS[2]

    def test_guard_rails_hold(self):
        cal = ThresholdCalibrator()
        cal.observe([1.0] * 500)
        e, h, c = cal.bands()
        assert BAND_MIN[0] <= e <= BAND_MAX[0]
        assert BAND_MIN[2] <= c <= BAND_MAX[2]
        assert e < h < c                     # strictly increasing always

    def test_invalid_observations_ignored(self):
        cal = ThresholdCalibrator()
        cal.observe(["x", None, -1.0, 2.0])  # type: ignore[list-item]
        assert cal.samples == 0

    def test_state_roundtrip(self):
        cal = ThresholdCalibrator()
        cal.observe([0.6] * 100)
        restored = ThresholdCalibrator()
        restored.load_state(cal.to_state())
        assert restored.bands() == cal.bands()
        assert restored.samples == cal.samples


# ---------------------------------------------------------------------------
# API endpoints (real router + real learners over ASGI)
# ---------------------------------------------------------------------------

@pytest.fixture
async def api(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_STATE_PATH", str(tmp_path / "learn.json"))
    from geosupply.api.main import create_app
    from geosupply.api.routers import osint as osint_module
    from geosupply.osint.aggregator import OsintAggregator

    agg = OsintAggregator(client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
    app = create_app()
    app.dependency_overrides[osint_module.aggregator_dep] = lambda: agg
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, agg
    app.dependency_overrides.clear()
    await agg.teardown()


class TestFeedbackEndpoints:
    async def test_post_feedback_trains_learner(self, api):
        client, agg = api
        for _ in range(3):
            resp = await client.post("/osint/ask/feedback", json={
                "query": "hormuz",
                "items": [{"source": "BBC World", "kind": "news", "vote": 1}],
            })
            assert resp.status_code == 200
        ack = resp.json()
        assert ack["accepted"] == 1
        assert ack["trained_sources"] == 1
        assert agg.rag_feedback.weight("BBC World") > 1.0

    async def test_feedback_summary_endpoint(self, api):
        client, agg = api
        for _ in range(4):
            await client.post("/osint/ask/feedback", json={
                "items": [{"source": "JunkWire", "kind": "news", "vote": -1}]})
        rows = (await client.get("/osint/ask/feedback")).json()
        assert rows and rows[0]["source"] == "JunkWire"
        assert rows[0]["weight"] < 1.0

    async def test_invalid_vote_rejected_by_schema(self, api):
        client, _ = api
        resp = await client.post("/osint/ask/feedback", json={
            "items": [{"source": "X", "vote": 5}]})
        assert resp.status_code == 422

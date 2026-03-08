"""Tests for SentimentWorker."""

import pytest

from geosupply.workers.sentiment_worker import SentimentWorker, _score_sentiment, _tokenise


@pytest.fixture
async def worker():
    w = SentimentWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestSentimentScoringHelpers:
    def test_positive_tokens_raise_polarity(self):
        polarity, subjectivity, confidence = _score_sentiment(_tokenise("good growth and great success"))
        assert polarity > 0
        assert 0.0 <= subjectivity <= 1.0
        assert 0.0 <= confidence <= 1.0

    def test_negative_tokens_lower_polarity(self):
        polarity, _, _ = _score_sentiment(_tokenise("war risk and major loss"))
        assert polarity < 0


class TestSentimentWorkerProcess:
    @pytest.mark.asyncio
    async def test_happy_path_positive_text(self, worker):
        res = await worker.process({"text": "India shows strong growth and stable outlook", "trace_id": "t-pos"})
        assert "error_type" not in res
        assert res["result"]["polarity"] > 0
        assert res["meta"]["worker"] == "SentimentWorker"

    @pytest.mark.asyncio
    async def test_uses_sanitised_text_if_present(self, worker):
        res = await worker.process({"sanitised_text": "conflict and crisis are increasing", "trace_id": "t-s"})
        assert "error_type" not in res
        assert res["result"]["polarity"] < 0

    @pytest.mark.asyncio
    async def test_missing_text_returns_worker_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "SentimentWorker"


class TestSentimentWorkerMeta:
    def test_capabilities(self):
        w = SentimentWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "SENTIMENT_SCORE" in caps["capabilities"]

    @pytest.mark.asyncio
    async def test_safe_process_path(self):
        w = SentimentWorker()
        res = await w.safe_process({"text": "good peace", "trace_id": "t-safe"})
        assert "error_type" not in res

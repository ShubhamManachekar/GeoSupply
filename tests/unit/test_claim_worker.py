"""Tests for ClaimWorker."""

import pytest

from geosupply.workers.claim_worker import ClaimWorker


@pytest.fixture
async def worker():
    w = ClaimWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestClaimWorkerProcess:
    @pytest.mark.asyncio
    async def test_classifies_statistical_claim(self, worker):
        text = "Exports increased 12% this quarter due to lower shipping delays."
        res = await worker.process({"text": text, "trace_id": "t-stat"})
        assert "error_type" not in res
        assert res["result"]["claim_type"] == "STATISTICAL"
        assert res["result"]["evidence_needed"] is True

    @pytest.mark.asyncio
    async def test_classifies_predictive_claim(self, worker):
        text = "Analysts expect the corridor will face disruptions next week."
        res = await worker.process({"text": text, "trace_id": "t-pred"})
        assert "error_type" not in res
        assert res["result"]["claim_type"] == "PREDICTIVE"

    @pytest.mark.asyncio
    async def test_classifies_opinion_claim(self, worker):
        text = "In my opinion, this policy should be reversed immediately."
        res = await worker.process({"text": text, "trace_id": "t-op"})
        assert "error_type" not in res
        assert res["result"]["claim_type"] == "OPINION"
        assert res["result"]["evidence_needed"] is False

    @pytest.mark.asyncio
    async def test_missing_text_returns_worker_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "ClaimWorker"


class TestClaimWorkerMeta:
    def test_capabilities(self):
        w = ClaimWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "CLAIM_EXTRACT" in caps["capabilities"]

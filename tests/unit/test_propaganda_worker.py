"""Tests for PropagandaWorker."""

import pytest

from geosupply.workers.propaganda_worker import PropagandaWorker


@pytest.fixture
async def worker():
    w = PropagandaWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestPropagandaWorkerProcess:
    @pytest.mark.asyncio
    async def test_detects_multiple_techniques(self, worker):
        text = (
            "Everyone must act now! The enemy will destroy us if we do not respond immediately."
        )
        res = await worker.process({"text": text, "trace_id": "t-prop"})
        assert "error_type" not in res
        assert res["result"]["propaganda_score"] > 0.45
        assert res["result"]["is_propaganda"] is True
        assert "FEAR_APPEAL" in res["result"]["techniques"]
        assert "BANDWAGON" in res["result"]["techniques"]

    @pytest.mark.asyncio
    async def test_low_score_for_neutral_text(self, worker):
        res = await worker.process(
            {
                "text": "Port traffic remained stable and shipments arrived on schedule.",
                "trace_id": "t-neutral",
            }
        )
        assert "error_type" not in res
        assert res["result"]["propaganda_score"] < 0.45
        assert res["result"]["is_propaganda"] is False

    @pytest.mark.asyncio
    async def test_missing_text_returns_worker_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "PropagandaWorker"


class TestPropagandaWorkerMeta:
    def test_capabilities(self):
        w = PropagandaWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 2
        assert caps["use_static"] is False
        assert "PROPAGANDA_SCORE" in caps["capabilities"]

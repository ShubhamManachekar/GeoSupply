"""Tests for CIBWorker."""

import pytest
from geosupply.workers.cib_worker import CIBWorker


@pytest.fixture
async def worker():
    w = CIBWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestCIBWorkerProcess:
    @pytest.mark.asyncio
    async def test_detects_amplification_call(self, worker):
        text = "Share this now immediately! Forward to everyone urgently!"
        res = await worker.process({"text": text, "trace_id": "t-amp"})
        assert "error_type" not in res
        assert "AMPLIFICATION_CALL" in res["result"]["bot_signals"]

    @pytest.mark.asyncio
    async def test_detects_hashtag_flood(self, worker):
        text = "Check this out #India #China #War #Breaking #Urgent #Now"
        res = await worker.process({"text": text, "trace_id": "t-hash"})
        assert "HASHTAG_FLOOD" in res["result"]["bot_signals"]

    @pytest.mark.asyncio
    async def test_detects_astroturfing(self, worker):
        text = "Multiple sockpuppet accounts are spreading this narrative."
        res = await worker.process({"text": text, "trace_id": "t-astro"})
        assert "ASTROTURFING" in res["result"]["coordination_signals"]

    @pytest.mark.asyncio
    async def test_detects_state_actor(self, worker):
        text = "This is state-sponsored foreign influence operation by state media."
        res = await worker.process({"text": text, "trace_id": "t-state"})
        assert "STATE_ACTOR" in res["result"]["coordination_signals"]

    @pytest.mark.asyncio
    async def test_neutral_text_low_score(self, worker):
        text = "Port congestion at Mundra delayed 200 containers by 3 days."
        res = await worker.process({"text": text, "trace_id": "t-neutral"})
        assert "error_type" not in res
        assert res["result"]["is_cib"] is False
        assert res["result"]["cib_score"] < 0.30

    @pytest.mark.asyncio
    async def test_high_cib_score_flagged(self, worker):
        text = (
            "Share now immediately! #Trending #BreakingNews #ShareNow "
            "Copy paste this message. Multiple fake accounts spreading this. "
            "State-sponsored astroturf campaign — make it trend!"
        )
        res = await worker.process({"text": text, "trace_id": "t-high"})
        assert res["result"]["is_cib"] is True
        assert res["result"]["cib_score"] >= 0.30

    @pytest.mark.asyncio
    async def test_missing_text_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "CIBWorker"

    @pytest.mark.asyncio
    async def test_result_fields_present(self, worker):
        res = await worker.process({"text": "test message", "trace_id": "t-fields"})
        r = res["result"]
        for f in ("cib_score", "is_cib", "bot_signals", "coordination_signals", "confidence"):
            assert f in r

    @pytest.mark.asyncio
    async def test_explicit_bot_ref_detected(self, worker):
        res = await worker.process({
            "text": "These are bot accounts running a click farm script.",
            "trace_id": "t-bot",
        })
        assert "EXPLICIT_BOT_REF" in res["result"]["bot_signals"]


class TestCIBWorkerMeta:
    def test_capabilities(self):
        w = CIBWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 2
        assert caps["use_static"] is False
        assert "CIB_DETECT" in caps["capabilities"]
        assert "BOT_NETWORK" in caps["capabilities"]

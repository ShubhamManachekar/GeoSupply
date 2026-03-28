"""Tests for MarketingSupervisor."""

import pytest

from geosupply.supervisors.marketing_supervisor import MarketingSupervisor
from geosupply.schemas import TaskPacket


def _make_task(task_type: str, budget_inr: float = 1.0) -> TaskPacket:
    return TaskPacket(
        task_id=f"t-{task_type.lower()}",
        task_type=task_type,
        budget_inr=budget_inr,
        priority="P1",
    )


@pytest.fixture
def supervisor():
    sup = MarketingSupervisor()
    sup.reset_budget()
    return sup


class TestMarketingSupervisorInit:
    def test_init(self):
        sup = MarketingSupervisor()
        assert sup.name == "MarketingSupervisor"
        assert sup.domain == "marketing"
        assert sup.budget_inr == 8.0
        assert len(sup.agents) == 4
        assert not sup.is_budget_exhausted


class TestMarketingSupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_tweet_gen(self, supervisor):
        task = _make_task("MARKETING_TWEET_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_prediction_post(self, supervisor):
        task = _make_task("MARKETING_PREDICTION_POST")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_analytics(self, supervisor):
        task = _make_task("MARKETING_ANALYTICS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_content_gen(self, supervisor):
        task = _make_task("MARKETING_CONTENT_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown(self, supervisor):
        task = _make_task("UNKNOWN_MARKETING_TASK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_exhausted_rejection(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("MARKETING_TWEET_GEN", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("MARKETING_TWEET_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_blocks_dispatch(self, supervisor):
        supervisor.pause()
        task = _make_task("MARKETING_TWEET_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resume_unblocks_dispatch(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("MARKETING_TWEET_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent_replaces_stub(self, supervisor):
        calls = []

        class CustomAgent:
            name = "TweetGenAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("TweetGenAgent", CustomAgent())
        task = _make_task("MARKETING_TWEET_GEN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

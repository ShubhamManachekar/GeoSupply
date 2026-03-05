"""Unit tests for BaseSupervisor — dispatch gates, budget, queue, pause."""

import pytest
from geosupply.config import AgentState
from geosupply.core.base_agent import BaseAgent
from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket


class MockAgent(BaseAgent):
    name = "MockAgent"
    domain = "test"
    capabilities = {"MOCK"}

    async def execute(self, task: dict) -> dict:
        return {
            "result": {"done": True},
            "meta": {"agent": self.name, "cost_inr": 0.02},
        }


class TestSupervisor(BaseSupervisor):
    name = "TestSupervisor"
    domain = "test"
    budget_inr = 1.0
    agents = ["MockAgent"]

    _mock_agent: MockAgent | None = None

    async def _select_agent(self, task):
        if self._mock_agent is None:
            self._mock_agent = MockAgent()
        return self._mock_agent


@pytest.fixture
def sup():
    s = TestSupervisor()
    s.reset_budget()
    return s


def _make_task(task_id: str = "t1", budget: float = 0.1) -> TaskPacket:
    return TaskPacket(task_id=task_id, task_type="TEST", budget_inr=budget)


class TestBudget:
    @pytest.mark.asyncio
    async def test_dispatch_deducts_cost(self, sup):
        result = await sup.dispatch(_make_task())
        assert result["status"] == "completed"
        assert sup._budget_remaining < 1.0

    @pytest.mark.asyncio
    async def test_dispatch_rejects_exhausted_budget(self, sup):
        sup._budget_remaining = 0.0
        result = await sup.dispatch(_make_task())
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_dispatch_rejects_over_budget_task(self, sup):
        sup._budget_remaining = 0.05
        result = await sup.dispatch(_make_task(budget=0.10))
        assert result["status"] == "rejected"
        assert result["reason"] == "task_over_budget"

    def test_reset_budget(self, sup):
        sup._budget_remaining = 0.0
        sup.reset_budget()
        assert sup._budget_remaining == 1.0


class TestQueue:
    @pytest.mark.asyncio
    async def test_dispatch_rejects_full_queue(self, sup):
        sup.max_queue_depth = 0  # Queue is immediately full
        result = await sup.dispatch(_make_task())
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    def test_queue_depth_property(self, sup):
        assert sup.queue_depth == 0


class TestPause:
    @pytest.mark.asyncio
    async def test_paused_rejects(self, sup):
        sup.pause()
        result = await sup.dispatch(_make_task())
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resume_accepts(self, sup):
        sup.pause()
        sup.resume()
        result = await sup.dispatch(_make_task())
        assert result["status"] == "completed"


class TestProperties:
    def test_is_budget_exhausted(self, sup):
        assert not sup.is_budget_exhausted
        sup._budget_remaining = 0
        assert sup.is_budget_exhausted

    def test_repr(self, sup):
        r = repr(sup)
        assert "TestSupervisor" in r
        assert "₹" in r

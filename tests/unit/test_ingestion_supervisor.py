"""Tests for IngestionSupervisor."""

import pytest

from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
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
    sup = IngestionSupervisor()
    sup.reset_budget()
    return sup


class TestIngestionSupervisorInit:
    def test_name_and_domain(self):
        sup = IngestionSupervisor()
        assert sup.name == "IngestionSupervisor"
        assert sup.domain == "ingestion"

    def test_agents_declared(self):
        sup = IngestionSupervisor()
        assert "NewsAgent" in sup.agents
        assert "AISAgent" in sup.agents

    def test_budget_inr(self):
        sup = IngestionSupervisor()
        assert sup.budget_inr == 15.0


class TestIngestionSupervisorDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_known_task_type(self, supervisor):
        task = _make_task("INGEST_NEWS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_ais_task(self, supervisor):
        task = _make_task("INGEST_AIS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_india_api_task(self, supervisor):
        task = _make_task("INGEST_INDIA_API")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_telegram_task(self, supervisor):
        task = _make_task("INGEST_TELEGRAM")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rejects_when_budget_exhausted(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("INGEST_NEWS", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_rejects_when_task_over_budget(self, supervisor):
        supervisor._budget_remaining = 0.50
        task = _make_task("INGEST_NEWS", budget_inr=5.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "task_over_budget"

    @pytest.mark.asyncio
    async def test_rejects_when_paused(self, supervisor):
        supervisor.pause()
        task = _make_task("INGEST_NEWS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resumes_after_pause(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("INGEST_NEWS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rejects_when_queue_full(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("INGEST_NEWS")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"


class TestIngestionSupervisorPriority:
    def test_source_priority_order(self):
        sup = IngestionSupervisor()
        priority = sup.source_priority()
        assert priority[0] == "AISAgent"   # real-time maritime first
        assert "NewsAgent" in priority

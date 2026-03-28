"""Tests for DashboardSupervisor."""

import pytest

from geosupply.supervisors.dashboard_supervisor import DashboardSupervisor
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
    sup = DashboardSupervisor()
    sup.reset_budget()
    return sup


class TestDashboardSupervisorInit:
    def test_init(self):
        sup = DashboardSupervisor()
        assert sup.name == "DashboardSupervisor"
        assert sup.domain == "dashboard"
        assert sup.budget_inr == 3.0
        assert len(sup.agents) == 3
        assert not sup.is_budget_exhausted


class TestDashboardSupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_dash_refresh(self, supervisor):
        task = _make_task("DASH_REFRESH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_metric_pull(self, supervisor):
        task = _make_task("DASH_METRIC_PULL")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_alert_render(self, supervisor):
        task = _make_task("DASH_ALERT_RENDER")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_kpi_update(self, supervisor):
        task = _make_task("DASH_KPI_UPDATE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown(self, supervisor):
        task = _make_task("UNKNOWN_DASH_TASK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_exhausted_rejection(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("DASH_REFRESH", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("DASH_REFRESH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_blocks_dispatch(self, supervisor):
        supervisor.pause()
        task = _make_task("DASH_REFRESH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resume_unblocks_dispatch(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("DASH_REFRESH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent_replaces_stub(self, supervisor):
        calls = []

        class CustomAgent:
            name = "MetricPullAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("MetricPullAgent", CustomAgent())
        task = _make_task("DASH_REFRESH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

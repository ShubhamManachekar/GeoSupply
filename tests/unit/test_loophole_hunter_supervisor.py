"""Tests for LoopholeHunterSupervisor."""

import pytest

from geosupply.supervisors.loophole_hunter_supervisor import LoopholeHunterSupervisor
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
    sup = LoopholeHunterSupervisor()
    sup.reset_budget()
    return sup


class TestLoopholeHunterSupervisorInit:
    def test_init(self):
        sup = LoopholeHunterSupervisor()
        assert sup.name == "LoopholeHunterSupervisor"
        assert sup.domain == "security"
        assert sup.budget_inr == 5.0
        assert len(sup.agents) == 3
        assert not sup.is_budget_exhausted

    def test_agents_registered(self):
        sup = LoopholeHunterSupervisor()
        assert "LoopholeHunterAgent" in sup._agent_registry
        assert "PenTestAgent" in sup._agent_registry
        assert "OverrideMonitorAgent" in sup._agent_registry


class TestLoopholeHunterSupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_loophole_scan(self, supervisor):
        task = _make_task("LOOPHOLE_SCAN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_pen_test(self, supervisor):
        task = _make_task("LOOPHOLE_PEN_TEST")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_override_monitor(self, supervisor):
        task = _make_task("LOOPHOLE_OVERRIDE_MONITOR")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_schema_audit(self, supervisor):
        task = _make_task("LOOPHOLE_SCHEMA_AUDIT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown(self, supervisor):
        task = _make_task("UNKNOWN_SECURITY_TASK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_exhausted_rejection(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("LOOPHOLE_SCAN", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("LOOPHOLE_SCAN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_is_ignored(self, supervisor):
        supervisor.pause()
        assert not supervisor._is_paused
        task = _make_task("LOOPHOLE_SCAN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_resume_still_works(self, supervisor):
        supervisor.resume()
        task = _make_task("LOOPHOLE_SCAN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent_replaces_stub(self, supervisor):
        calls = []

        class CustomAgent:
            name = "LoopholeHunterAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("LoopholeHunterAgent", CustomAgent())
        task = _make_task("LOOPHOLE_SCAN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

"""Tests for TechSupervisor."""

import pytest

from geosupply.supervisors.tech_supervisor import TechSupervisor
from geosupply.schemas import TaskPacket


def _make_task(task_type: str, budget_inr: float = 1.0, payload: dict | None = None) -> TaskPacket:
    return TaskPacket(
        task_id=f"t-{task_type.lower()}",
        task_type=task_type,
        budget_inr=budget_inr,
        priority="P1",
        payload=payload or {},
    )


@pytest.fixture
def supervisor():
    sup = TechSupervisor()
    sup.reset_budget()
    return sup


class TestTechSupervisorInit:
    def test_init(self):
        sup = TechSupervisor()
        assert sup.name == "TechSupervisor"
        assert sup.domain == "tech"
        assert sup.budget_inr == 6.0
        assert len(sup.agents) == 3
        assert not sup.is_budget_exhausted


class TestTechSupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_api_health(self, supervisor):
        task = _make_task("TECH_API_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_db_check(self, supervisor):
        task = _make_task("TECH_DB_CHECK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_cache_flush(self, supervisor):
        task = _make_task("TECH_CACHE_FLUSH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_dependency_audit(self, supervisor):
        task = _make_task("TECH_DEPENDENCY_AUDIT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown(self, supervisor):
        task = _make_task("UNKNOWN_TECH_TASK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_exhausted_rejection(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("TECH_API_HEALTH", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("TECH_API_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_blocks_dispatch(self, supervisor):
        supervisor.pause()
        task = _make_task("TECH_API_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resume_unblocks_dispatch(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("TECH_API_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent_replaces_stub(self, supervisor):
        calls = []

        class CustomAgent:
            name = "APIHealthAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("APIHealthAgent", CustomAgent())
        task = _make_task("TECH_API_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_force_write_gate_rejects_when_budget_low(self, supervisor):
        supervisor._budget_remaining = 0.5
        task = _make_task("TECH_DB_CHECK", budget_inr=1.0, payload={"force_write": True})
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "db_write_budget_too_low"

    @pytest.mark.asyncio
    async def test_force_write_gate_passes_when_budget_ok(self, supervisor):
        supervisor._budget_remaining = 5.0
        task = _make_task("TECH_DB_CHECK", budget_inr=1.0, payload={"force_write": True})
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_db_check_without_force_write_always_passes(self, supervisor):
        supervisor._budget_remaining = 0.5
        task = _make_task("TECH_DB_CHECK", budget_inr=0.3, payload={})
        result = await supervisor.dispatch(task)
        # Proceeds past force_write gate, then hits standard budget gate
        # budget_inr=0.3 <= budget_remaining=0.5, so should complete
        assert result["status"] == "completed"

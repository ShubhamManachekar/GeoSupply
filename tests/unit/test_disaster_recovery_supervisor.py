"""Tests for DisasterRecoverySupervisor."""

import pytest

from geosupply.supervisors.disaster_recovery_supervisor import DisasterRecoverySupervisor
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
    sup = DisasterRecoverySupervisor()
    sup.reset_budget()
    return sup


class TestDisasterRecoverySupervisorInit:
    def test_init(self):
        sup = DisasterRecoverySupervisor()
        assert sup.name == "DisasterRecoverySupervisor"
        assert sup.domain == "disaster_recovery"
        assert sup.budget_inr == 2.0
        assert len(sup.agents) == 4
        assert not sup.is_budget_exhausted

    def test_agents_registered(self):
        sup = DisasterRecoverySupervisor()
        assert "BackupAgent" in sup._agent_registry
        assert "CostProjectionAgent" in sup._agent_registry
        assert "RestoreAgent" in sup._agent_registry
        assert "FailoverAgent" in sup._agent_registry


class TestDisasterRecoverySupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_backup_run(self, supervisor):
        task = _make_task("BACKUP_RUN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_cost_project(self, supervisor):
        task = _make_task("COST_PROJECT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_dr_restore(self, supervisor):
        task = _make_task("DR_RESTORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_dr_failover(self, supervisor):
        task = _make_task("DR_FAILOVER")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown_task_type(self, supervisor):
        task = _make_task("UNKNOWN_TASK_TYPE_XYZ")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rejects_when_budget_exhausted(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("BACKUP_RUN", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_rejects_when_queue_full(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("BACKUP_RUN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_is_ignored(self, supervisor):
        supervisor.pause()
        assert not supervisor._is_paused
        task = _make_task("BACKUP_RUN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_resume_still_works(self, supervisor):
        supervisor.resume()
        task = _make_task("BACKUP_RUN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent_replaces_stub(self, supervisor):
        calls = []

        class CustomAgent:
            name = "BackupAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("BackupAgent", CustomAgent())
        task = _make_task("BACKUP_RUN")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

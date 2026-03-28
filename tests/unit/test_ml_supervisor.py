"""Tests for MLSupervisor."""

import pytest

from geosupply.supervisors.ml_supervisor import MLSupervisor
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
    sup = MLSupervisor()
    sup.reset_budget()
    return sup


class TestMLSupervisorInit:
    def test_init(self):
        sup = MLSupervisor()
        assert sup.name == "MLSupervisor"
        assert sup.domain == "ml"
        assert sup.budget_inr == 12.0
        assert len(sup.agents) == 4
        assert not sup.is_budget_exhausted


class TestMLSupervisorRouting:
    @pytest.mark.asyncio
    async def test_routes_stress_score(self, supervisor):
        task = _make_task("ML_STRESS_SCORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_conflict_predict(self, supervisor):
        task = _make_task("ML_CONFLICT_PREDICT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_supplier_rank(self, supervisor):
        task = _make_task("ML_SUPPLIER_RANK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_routes_sanction_classify(self, supervisor):
        task = _make_task("ML_SANCTION_CLASSIFY")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fallback_on_unknown(self, supervisor):
        task = _make_task("UNKNOWN_ML_TASK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_exhausted_rejection(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("ML_STRESS_SCORE", budget_inr=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, supervisor):
        supervisor.max_queue_depth = 0
        task = _make_task("ML_STRESS_SCORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"

    @pytest.mark.asyncio
    async def test_pause_blocks_dispatch(self, supervisor):
        supervisor.pause()
        task = _make_task("ML_STRESS_SCORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "supervisor_paused"

    @pytest.mark.asyncio
    async def test_resume_unblocks_dispatch(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("ML_STRESS_SCORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_agent(self, supervisor):
        calls = []

        class CustomAgent:
            name = "StressScoreAgent"

            async def safe_execute(self, payload: dict) -> dict:
                calls.append(payload)
                return {"result": {"status": "custom_ok"}, "meta": {"cost_inr": 0.0}}

        supervisor.register_agent("StressScoreAgent", CustomAgent())
        task = _make_task("ML_STRESS_SCORE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert len(calls) == 1

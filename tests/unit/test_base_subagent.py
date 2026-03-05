"""Unit tests for BaseSubAgent — lifecycle, parallel execution, safe_run."""

import pytest
from geosupply.core.base_subagent import BaseSubAgent


class SimpleSubAgent(BaseSubAgent):
    name = "SimpleSubAgent"
    pipeline_steps = ["step_1", "step_2"]

    async def run(self, input_data: dict) -> dict:
        return {
            "result": {"processed": True},
            "meta": {"subagent": self.name, "cost_inr": 0.05, "steps_completed": 2},
        }


class FailSubAgent(BaseSubAgent):
    name = "FailSubAgent"
    pipeline_steps = ["step_1"]

    async def run(self, input_data: dict) -> dict:
        raise RuntimeError("pipeline broke")


class TestSubAgentLifecycle:
    @pytest.mark.asyncio
    async def test_setup_marks_ready(self):
        sa = SimpleSubAgent()
        assert not sa._is_setup
        await sa.setup()
        assert sa._is_setup

    @pytest.mark.asyncio
    async def test_teardown_resets(self):
        sa = SimpleSubAgent()
        await sa.setup()
        await sa.teardown()
        assert not sa._is_setup


class TestSubAgentRun:
    @pytest.mark.asyncio
    async def test_safe_run_success(self):
        sa = SimpleSubAgent()
        result = await sa.safe_run({"input": "test"})
        assert result["result"]["processed"] is True
        assert result["meta"]["cost_inr"] == 0.05

    @pytest.mark.asyncio
    async def test_safe_run_auto_setup(self):
        sa = SimpleSubAgent()
        assert not sa._is_setup
        await sa.safe_run({"input": "test"})
        assert sa._is_setup

    @pytest.mark.asyncio
    async def test_safe_run_handles_failure(self):
        sa = FailSubAgent()
        result = await sa.safe_run({"input": "test"})
        assert result["result"] is None
        assert "pipeline broke" in result["meta"]["error"]


class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_run_parallel_success(self):
        sa = SimpleSubAgent()

        async def step(data):
            return {"result": data["val"] * 2, "meta": {"cost_inr": 0.01}}

        results = await sa.run_parallel(
            [step, step, step],
            [{"val": 1}, {"val": 2}, {"val": 3}],
        )
        assert len(results) == 3
        assert results[0]["result"] == 2
        assert results[2]["result"] == 6

    @pytest.mark.asyncio
    async def test_run_parallel_mismatched_counts(self):
        sa = SimpleSubAgent()

        async def step(data):
            return data

        with pytest.raises(ValueError, match="mismatch"):
            await sa.run_parallel([step, step], [{"a": 1}])

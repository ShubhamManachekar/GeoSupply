"""Tests for HallucinationCheckSubAgent."""

import pytest

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.subagents.hallucination_check_subagent import HallucinationCheckSubAgent


@pytest.fixture
async def subagent():
    sa = HallucinationCheckSubAgent()
    await sa.setup()
    yield sa
    await sa.teardown()


class TestHallucinationCheckSubAgentRun:
    @pytest.mark.asyncio
    async def test_factual_claim_passes_floor(self, subagent):
        # Use text with strong positive sentiment words to push composite above floor
        res = await subagent.run({
            "text": "India shows great strong stable growth and success in exports.",
            "trace_id": "t-fact",
        })
        assert "error_type" not in res
        result = res["result"]
        assert "composite_confidence" in result
        assert "passes_floor" in result
        # FACTUAL prior = 0.80, strong positive sentiment → composite > 0.70
        assert result["passes_floor"] is True

    @pytest.mark.asyncio
    async def test_opinion_claim_may_fail_floor(self, subagent):
        res = await subagent.run({
            "text": "In my opinion this policy should be reversed immediately.",
            "trace_id": "t-op",
        })
        result = res["result"]
        assert result["claim_type"] == "OPINION"
        # OPINION prior = 0.40, composite likely below floor
        assert result["composite_confidence"] < HALLUCINATION_FLOOR

    @pytest.mark.asyncio
    async def test_floor_value_matches_config(self, subagent):
        res = await subagent.run({
            "text": "Strong growth forecast for India next quarter.",
            "trace_id": "t-floor",
        })
        assert res["result"]["hallucination_floor"] == HALLUCINATION_FLOOR

    @pytest.mark.asyncio
    async def test_meta_steps_completed(self, subagent):
        res = await subagent.run({
            "text": "Supply chains are improving rapidly.",
            "trace_id": "t-steps",
        })
        assert res["meta"]["steps_completed"] == 3
        assert res["meta"]["subagent"] == "HallucinationCheckSubAgent"

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self, subagent):
        res = await subagent.run({
            "text": "Exports increased 12% this quarter.",
            "trace_id": "t-fields",
        })
        result = res["result"]
        for field in (
            "composite_confidence", "hallucination_floor", "passes_floor",
            "claim_type", "evidence_needed", "sentiment_confidence",
        ):
            assert field in result

    @pytest.mark.asyncio
    async def test_statistical_claim_passes_floor(self, subagent):
        # "increase" + percentage triggers STATISTICAL; positive words boost sentiment
        res = await subagent.run({
            "text": "Exports increase 20% this quarter. Strong growth and stable trade.",
            "trace_id": "t-stat",
        })
        assert res["result"]["claim_type"] == "STATISTICAL"
        assert res["result"]["passes_floor"] is True

    @pytest.mark.asyncio
    async def test_safe_run_without_prior_setup(self):
        sa = HallucinationCheckSubAgent()
        res = await sa.safe_run({
            "text": "India will likely see growth next year.",
            "trace_id": "t-safe",
        })
        assert "result" in res
        await sa.teardown()

    @pytest.mark.asyncio
    async def test_composite_confidence_in_range(self, subagent):
        res = await subagent.run({
            "text": "The trade route faces disruption due to conflict risk.",
            "trace_id": "t-range",
        })
        conf = res["result"]["composite_confidence"]
        assert 0.0 <= conf <= 1.0


class TestHallucinationCheckSubAgentMeta:
    def test_pipeline_steps_declared(self):
        sa = HallucinationCheckSubAgent()
        assert "claim" in sa.pipeline_steps
        assert "sentiment" in sa.pipeline_steps
        assert "fuse" in sa.pipeline_steps

    def test_parallel_steps(self):
        sa = HallucinationCheckSubAgent()
        assert sa.parallel_steps == {"claim", "sentiment"}

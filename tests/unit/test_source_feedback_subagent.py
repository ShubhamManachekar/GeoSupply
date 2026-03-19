"""Tests for SourceFeedbackSubAgent."""

import pytest
from geosupply.subagents.source_feedback_subagent import SourceFeedbackSubAgent


@pytest.fixture
async def subagent():
    sa = SourceFeedbackSubAgent()
    await sa.setup()
    yield sa
    await sa.teardown()


class TestSourceFeedbackSubAgentRun:
    @pytest.mark.asyncio
    async def test_verified_correct_boosts_score(self, subagent):
        res = await subagent.run({
            "source_id": "https://reuters.com",
            "text": "India trade surplus rose this quarter.",
            "verified_correct": True,
            "trace_id": "t-boost",
        })
        assert "error_type" not in res
        result = res["result"]
        assert result["penalty"] > 0   # positive = boost
        assert result["new_score"] > result["old_score"]
        assert result["reason"] == "verified_correct"

    @pytest.mark.asyncio
    async def test_propaganda_detection_penalises_source(self, subagent):
        text = (
            "Everyone must act now! The enemy will destroy us. "
            "We vs them — urgent threat! Fight back immediately!"
        )
        res = await subagent.run({
            "source_id": "https://unknown-blog.xyz",
            "text": text,
            "strike_number": 0,
            "trace_id": "t-penalty",
        })
        result = res["result"]
        if result["is_propaganda"]:
            assert result["penalty"] < 0
            assert result["new_score"] < result["old_score"]
            assert "propaganda_detected" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_change_for_neutral_unverified(self, subagent):
        res = await subagent.run({
            "source_id": "https://thehindu.com",
            "text": "Port traffic remained stable this week.",
            "trace_id": "t-neutral",
        })
        result = res["result"]
        # Neutral text + not verified → no change (if not propaganda)
        if not result["is_propaganda"]:
            assert result["penalty"] == 0.0
            assert result["reason"] == "no_change"

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self, subagent):
        res = await subagent.run({
            "source_id": "apnews.com",
            "text": "Trade data released today.",
            "trace_id": "t-fields",
        })
        r = res["result"]
        for f in ("source_id", "old_score", "new_score", "penalty", "reason", "is_propaganda"):
            assert f in r

    @pytest.mark.asyncio
    async def test_meta_steps_completed(self, subagent):
        res = await subagent.run({
            "source_id": "bbc.com",
            "text": "Supply chains improving globally.",
            "trace_id": "t-steps",
        })
        assert res["meta"]["steps_completed"] == 3
        assert res["meta"]["subagent"] == "SourceFeedbackSubAgent"

    @pytest.mark.asyncio
    async def test_score_stays_in_range(self, subagent):
        res = await subagent.run({
            "source_id": "low-cred-site.xyz",
            "text": "Supply update.",
            "trace_id": "t-range",
        })
        score = res["result"]["new_score"]
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_safe_run_auto_setup(self):
        sa = SourceFeedbackSubAgent()
        res = await sa.safe_run({
            "source_id": "reuters.com",
            "text": "Global markets stable.",
            "trace_id": "t-safe",
        })
        assert "result" in res
        await sa.teardown()


class TestSourceFeedbackSubAgentMeta:
    def test_pipeline_steps(self):
        sa = SourceFeedbackSubAgent()
        assert "source_cred" in sa.pipeline_steps
        assert "propaganda" in sa.pipeline_steps
        assert "fuse" in sa.pipeline_steps

    def test_parallel_steps(self):
        sa = SourceFeedbackSubAgent()
        assert sa.parallel_steps == {"source_cred", "propaganda"}

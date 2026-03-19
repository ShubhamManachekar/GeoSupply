"""Tests for NLPPipelineSubAgent."""

import pytest

from geosupply.subagents.nlp_pipeline_subagent import NLPPipelineSubAgent


@pytest.fixture
async def subagent():
    sa = NLPPipelineSubAgent()
    await sa.setup()
    yield sa
    await sa.teardown()


class TestNLPPipelineSubAgentRun:
    @pytest.mark.asyncio
    async def test_happy_path_returns_all_three_results(self, subagent):
        res = await subagent.run({
            "text": "India shows strong growth. Exports increased 15% this quarter.",
            "trace_id": "t-nlp-1",
        })
        assert "error_type" not in res
        result = res["result"]
        assert result["sentiment"] is not None
        assert result["claim"] is not None
        assert isinstance(result["entities"], list)

    @pytest.mark.asyncio
    async def test_meta_fields_present(self, subagent):
        res = await subagent.run({"text": "hello world", "trace_id": "t-meta"})
        meta = res["meta"]
        assert meta["subagent"] == "NLPPipelineSubAgent"
        assert meta["steps_completed"] == 2
        assert "cost_inr" in meta
        assert "timestamp" in meta

    @pytest.mark.asyncio
    async def test_positive_sentiment_detected(self, subagent):
        res = await subagent.run({
            "text": "Great success and strong growth in peace negotiations.",
            "trace_id": "t-pos",
        })
        assert res["result"]["sentiment"]["polarity"] > 0

    @pytest.mark.asyncio
    async def test_entities_extracted_for_geo_text(self, subagent):
        res = await subagent.run({
            "text": "India and China held talks at the United Nations.",
            "trace_id": "t-ner",
        })
        entity_texts = {e["text"] for e in res["result"]["entities"]}
        assert "India" in entity_texts
        assert "China" in entity_texts

    @pytest.mark.asyncio
    async def test_statistical_claim_detected(self, subagent):
        # "increase" + percentage → STATISTICAL (before CAUSAL check)
        res = await subagent.run({
            "text": "Exports increase 20% this quarter showing strong growth.",
            "trace_id": "t-claim",
        })
        assert res["result"]["claim"]["claim_type"] == "STATISTICAL"

    @pytest.mark.asyncio
    async def test_empty_text_returns_errors_list(self, subagent):
        res = await subagent.run({"text": "", "trace_id": "t-empty"})
        # Workers return errors, subagent surfaces them
        errors = res["result"].get("errors", [])
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_safe_run_setup_guard(self):
        sa = NLPPipelineSubAgent()
        # safe_run calls setup automatically
        res = await sa.safe_run({
            "text": "Supply chain risk is rising globally.",
            "trace_id": "t-safe",
        })
        assert "result" in res
        await sa.teardown()

    @pytest.mark.asyncio
    async def test_sanitised_text_preferred(self, subagent):
        res = await subagent.run({
            "text": "bad text",
            "sanitised_text": "India exports increased 10% this quarter.",
            "trace_id": "t-san",
        })
        assert res["result"]["claim"]["claim_type"] == "STATISTICAL"


class TestNLPPipelineSubAgentMeta:
    def test_pipeline_steps_declared(self):
        sa = NLPPipelineSubAgent()
        assert "sentiment" in sa.pipeline_steps
        assert "ner" in sa.pipeline_steps
        assert "claim" in sa.pipeline_steps

    def test_parallel_steps_declared(self):
        sa = NLPPipelineSubAgent()
        assert sa.parallel_steps == {"sentiment", "ner", "claim"}

    def test_repr(self):
        sa = NLPPipelineSubAgent()
        assert "NLPPipelineSubAgent" in repr(sa)

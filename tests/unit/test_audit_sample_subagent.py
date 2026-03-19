"""Tests for AuditSampleSubAgent."""

import pytest
from geosupply.config import HALLUCINATION_FLOOR
from geosupply.subagents.audit_sample_subagent import AuditSampleSubAgent


@pytest.fixture
async def subagent():
    sa = AuditSampleSubAgent(sampling_rate=1.0)   # always audit
    await sa.setup()
    yield sa
    await sa.teardown()


class TestAuditSampleSubAgentRun:
    @pytest.mark.asyncio
    async def test_force_audit_bypasses_sampling_gate(self, subagent):
        res = await subagent.run({
            "text": "India shows strong growth and success.",
            "trace_id": "t-force",
            "force_audit": True,
        })
        assert res["result"]["sampled"] is True
        assert res["result"]["audit_result"] in ("PASS", "WARN", "FAIL")

    @pytest.mark.asyncio
    async def test_sampling_rate_zero_skips_audit(self):
        sa = AuditSampleSubAgent(sampling_rate=0.0)
        await sa.setup()
        res = await sa.run({"text": "some text", "trace_id": "t-skip"})
        assert res["result"]["sampled"] is False
        assert res["result"]["audit_result"] == "SKIPPED"
        await sa.teardown()

    @pytest.mark.asyncio
    async def test_pass_verdict_for_factual_positive_text(self, subagent):
        res = await subagent.run({
            "text": "India shows great strong stable growth and excellent success.",
            "trace_id": "t-pass",
            "force_audit": True,
        })
        assert res["result"]["sampled"] is True
        assert res["result"]["audit_result"] == "PASS"
        assert res["result"]["composite_confidence"] >= HALLUCINATION_FLOOR

    @pytest.mark.asyncio
    async def test_fail_verdict_for_opinion_text(self, subagent):
        res = await subagent.run({
            "text": "In my opinion this should be reversed immediately.",
            "trace_id": "t-fail",
            "force_audit": True,
        })
        assert res["result"]["sampled"] is True
        # OPINION prior is low → likely FAIL
        assert res["result"]["audit_result"] in ("FAIL", "WARN")

    @pytest.mark.asyncio
    async def test_audit_record_schema(self, subagent):
        res = await subagent.run({
            "text": "Exports increase 10% this quarter.",
            "sample_id": "s-001",
            "trace_id": "t-schema",
            "force_audit": True,
        })
        record = res["result"]["audit_record"]
        assert record["sample_id"] == "s-001"
        assert "pipeline_output" in record
        assert "audit_result" in record
        assert "sampling_rate" in record

    @pytest.mark.asyncio
    async def test_meta_steps_completed_when_sampled(self, subagent):
        res = await subagent.run({
            "text": "Strong trade growth.",
            "trace_id": "t-steps",
            "force_audit": True,
        })
        assert res["meta"]["steps_completed"] == 3

    @pytest.mark.asyncio
    async def test_meta_steps_completed_when_skipped(self):
        sa = AuditSampleSubAgent(sampling_rate=0.0)
        await sa.setup()
        res = await sa.run({"text": "x", "trace_id": "t-s0"})
        assert res["meta"]["steps_completed"] == 1
        await sa.teardown()

    @pytest.mark.asyncio
    async def test_safe_run_auto_setup(self):
        sa = AuditSampleSubAgent(sampling_rate=1.0)
        res = await sa.safe_run({
            "text": "India holds strong.",
            "trace_id": "t-safe",
            "force_audit": True,
        })
        assert "result" in res
        await sa.teardown()


class TestAuditSampleSubAgentMeta:
    def test_pipeline_steps(self):
        sa = AuditSampleSubAgent()
        assert "sample_gate" in sa.pipeline_steps
        assert "validate" in sa.pipeline_steps
        assert "fuse" in sa.pipeline_steps

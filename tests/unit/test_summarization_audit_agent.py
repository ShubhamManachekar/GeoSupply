"""Tests for SummarizationAuditAgent — severity band distortion detection."""

import pytest
from geosupply.agents.summarization_audit_agent import (
    SummarizationAuditAgent,
    _score_to_band,
    _detect_band_in_text,
    _band_index,
)


@pytest.fixture
def agent():
    return SummarizationAuditAgent()


class TestHelpers:
    def test_score_to_band_minimal(self):
        assert _score_to_band(0.10) == "minimal"

    def test_score_to_band_low(self):
        assert _score_to_band(0.40) == "low"

    def test_score_to_band_moderate(self):
        assert _score_to_band(0.60) == "moderate"

    def test_score_to_band_high(self):
        assert _score_to_band(0.75) == "high"

    def test_score_to_band_critical(self):
        assert _score_to_band(0.90) == "critical"

    def test_detect_band_critical(self):
        text = "This is a critical situation requiring urgent attention"
        assert _detect_band_in_text(text) == "critical"

    def test_detect_band_minimal(self):
        text = "Only a negligible impact was observed"
        assert _detect_band_in_text(text) == "minimal"

    def test_detect_band_none(self):
        assert _detect_band_in_text("India supply chain quarterly update") is None

    def test_detect_band_highest_wins(self):
        # Both "modest" (low) and "critical" present → critical wins
        text = "modest improvements yet critical disruptions loom"
        assert _detect_band_in_text(text) == "critical"

    def test_band_index_ordering(self):
        assert _band_index("minimal") < _band_index("low")
        assert _band_index("low") < _band_index("moderate")
        assert _band_index("moderate") < _band_index("high")
        assert _band_index("high") < _band_index("critical")

    def test_band_index_unknown(self):
        assert _band_index("nonsense") == -1


class TestAuditHappyPath:
    @pytest.mark.asyncio
    async def test_pass_when_band_matches(self, agent):
        """Score 0.75 = high band; summary uses 'significant' → PASS."""
        result = await agent.execute({
            "action": "audit",
            "summary": "Significant disruption to supply chains detected",
            "score": 0.75,
            "trace_id": "sa-001",
        })
        assert result["result"]["verdict"] == "PASS"
        assert result["result"]["score_band"] == "high"

    @pytest.mark.asyncio
    async def test_pass_when_lower_band_used(self, agent):
        """Score 0.90 = critical; summary uses 'significant' (high) → PASS."""
        result = await agent.execute({
            "action": "audit",
            "summary": "Significant risk identified",
            "score": 0.90,
            "trace_id": "sa-002",
        })
        # high <= critical → PASS
        assert result["result"]["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_fail_exaggerated_when_overstated(self, agent):
        """Score 0.15 = minimal; summary uses 'catastrophic' → FAIL_EXAGGERATED."""
        result = await agent.execute({
            "action": "audit",
            "summary": "Catastrophic and devastating collapse imminent",
            "score": 0.15,
            "trace_id": "sa-003",
        })
        assert result["result"]["verdict"] == "FAIL_EXAGGERATED"
        assert result["result"]["distortion_delta"] > 0

    @pytest.mark.asyncio
    async def test_unverifiable_when_no_keywords(self, agent):
        """Summary has no band keywords → UNVERIFIABLE."""
        result = await agent.execute({
            "action": "audit",
            "summary": "Supply chain status update for Q1",
            "score": 0.50,
            "trace_id": "sa-004",
        })
        assert result["result"]["verdict"] == "UNVERIFIABLE"

    @pytest.mark.asyncio
    async def test_cost_is_always_zero(self, agent):
        result = await agent.execute({
            "action": "audit",
            "summary": "test",
            "score": 0.5,
            "trace_id": "sa-cost",
        })
        assert result["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_score_clamped_between_0_and_1(self, agent):
        result = await agent.execute({
            "action": "audit",
            "summary": "moderate risk",
            "score": 1.5,
            "trace_id": "sa-clamp",
        })
        assert result["result"]["score"] == 1.0


class TestAuditErrorPaths:
    @pytest.mark.asyncio
    async def test_missing_summary_returns_error(self, agent):
        result = await agent.execute({"action": "audit", "score": 0.5, "trace_id": "sa-err"})
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, agent):
        result = await agent.execute({"action": "unknown_action"})
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_empty_summary_returns_error(self, agent):
        result = await agent.execute({
            "action": "audit",
            "summary": "   ",
            "score": 0.5,
            "trace_id": "sa-blank",
        })
        assert "error" in result["result"]


class TestBatchAudit:
    @pytest.mark.asyncio
    async def test_batch_processes_all_items(self, agent):
        result = await agent.execute({
            "action": "batch_audit",
            "items": [
                {"summary": "Critical crisis now", "score": 0.10},
                {"summary": "Moderate impact observed", "score": 0.60},
            ],
            "trace_id": "sa-batch",
        })
        r = result["result"]
        assert r["total"] == 2

    @pytest.mark.asyncio
    async def test_batch_counts_exaggerated(self, agent):
        result = await agent.execute({
            "action": "batch_audit",
            "items": [
                {"summary": "Catastrophic failure", "score": 0.10},
                {"summary": "Minimal disruption", "score": 0.20},
            ],
            "trace_id": "sa-batch-count",
        })
        assert result["result"]["exaggerated_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_batch_returns_error(self, agent):
        result = await agent.execute({"action": "batch_audit", "items": []})
        assert "error" in result["result"]


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_action(self, agent):
        result = await agent.execute({"action": "health"})
        r = result["result"]
        assert r["status"] == "healthy"
        assert "exaggeration_rate" in r

    def test_stats_property(self, agent):
        assert agent.stats["total_audited"] == 0
        assert agent.stats["total_exaggerated"] == 0

    @pytest.mark.asyncio
    async def test_exaggeration_counter_increments(self, agent):
        await agent.execute({
            "action": "audit",
            "summary": "Catastrophic devastating crisis",
            "score": 0.05,
            "trace_id": "sa-ctr",
        })
        assert agent.stats["total_exaggerated"] == 1
        assert agent.stats["total_audited"] == 1

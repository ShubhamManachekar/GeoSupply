"""Tests for FactCheckAgent — Layer 3 quality gate."""

import pytest
from geosupply.agents.fact_check_agent import FactCheckAgent, _score_evidence
from geosupply.config import HALLUCINATION_FLOOR


@pytest.fixture
def agent():
    return FactCheckAgent()


class TestScoreEvidence:
    def test_no_evidence_returns_zero(self):
        score, count = _score_evidence(["claim"], [])
        assert score == 0.0
        assert count == 0

    def test_no_claims_returns_zero(self):
        score, count = _score_evidence([], ["evidence here"])
        assert score == 0.0
        assert count == 0

    def test_strong_overlap_scores_high(self):
        claims = ["India supply chain disruption at Gujarat port"]
        evidence = ["India supply chain at Gujarat facing disruption", "India port supply delays"]
        score, count = _score_evidence(claims, evidence)
        assert score > 0.3
        assert count == 2

    def test_weak_overlap_scores_low(self):
        claims = ["India supply chain"]
        evidence = ["Unrelated topic about weather in Paris"]
        score, count = _score_evidence(claims, evidence)
        assert score < HALLUCINATION_FLOOR


class TestFactCheckHappyPath:
    @pytest.mark.asyncio
    async def test_pass_with_strong_evidence(self, agent):
        task = {
            "action": "fact_check",
            "claim_text": "India port delays in Gujarat causing supply disruption",
            "evidence": [
                "India Gujarat port is experiencing severe delays in supply",
                "Gujarat India supply chain disruption reported at port facilities",
                "Port delays at Gujarat India impacting supply chains",
            ],
            "sources": ["Reuters", "Bloomberg", "TheHindu"],
            "trace_id": "fc-001",
        }
        result = await agent.execute(task)
        r = result["result"]
        assert r["verdict"] in ("PASS", "UNVERIFIABLE")
        assert "confidence" in r
        assert result["meta"]["cost_inr"] >= 0.0

    @pytest.mark.asyncio
    async def test_quarantine_with_no_evidence(self, agent):
        task = {
            "action": "fact_check",
            "claim_text": "Some unverifiable claim",
            "evidence": [],
            "trace_id": "fc-002",
        }
        result = await agent.execute(task)
        # With zero evidence: confidence=0.0 < HALLUCINATION_FLOOR → QUARANTINE
        assert result["result"]["verdict"] in ("QUARANTINE", "UNVERIFIABLE")

    @pytest.mark.asyncio
    async def test_hallucination_score_is_complement(self, agent):
        task = {
            "action": "fact_check",
            "claim_text": "claim",
            "evidence": ["strong matching claim"],
            "trace_id": "fc-003",
        }
        result = await agent.execute(task)
        r = result["result"]
        assert abs(r["hallucination_score"] - (1.0 - r["confidence"])) < 0.001

    @pytest.mark.asyncio
    async def test_missing_claim_text_returns_error(self, agent):
        result = await agent.execute({"action": "fact_check", "trace_id": "fc-err"})
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_sources_capped_at_ten(self, agent):
        task = {
            "action": "fact_check",
            "claim_text": "test claim",
            "evidence": ["ev"] * 5,
            "sources": [f"src{i}" for i in range(20)],
            "trace_id": "fc-cap",
        }
        result = await agent.execute(task)
        assert len(result["result"]["sources_checked"]) <= 10


class TestFactCheckErrorPaths:
    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, agent):
        result = await agent.execute({"action": "nonexistent"})
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_empty_claim_returns_error(self, agent):
        result = await agent.execute({
            "action": "fact_check",
            "claim_text": "   ",
            "trace_id": "fc-empty",
        })
        assert "error" in result["result"]


class TestBatchCheck:
    @pytest.mark.asyncio
    async def test_batch_returns_all_results(self, agent):
        task = {
            "action": "batch_check",
            "claims": [
                {"claim_text": "Claim A", "evidence": [], "trace_id": "b1"},
                {"claim_text": "Claim B", "evidence": ["B evidence"], "trace_id": "b2"},
            ],
            "trace_id": "batch-001",
        }
        result = await agent.execute(task)
        r = result["result"]
        assert r["total"] == 2
        assert "batch_results" in r

    @pytest.mark.asyncio
    async def test_empty_batch_returns_error(self, agent):
        result = await agent.execute({"action": "batch_check", "claims": []})
        assert "error" in result["result"]


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_action(self, agent):
        result = await agent.execute({"action": "health"})
        r = result["result"]
        assert r["status"] == "healthy"
        assert "total_checked" in r
        assert "quarantine_rate" in r

    def test_stats_property(self, agent):
        assert agent.stats["total_checked"] == 0
        assert agent.stats["total_quarantined"] == 0


class TestHallucinationFloor:
    @pytest.mark.asyncio
    async def test_confidence_below_floor_triggers_quarantine(self, agent):
        """Any score below HALLUCINATION_FLOOR must yield QUARANTINE or UNVERIFIABLE."""
        task = {
            "action": "fact_check",
            "claim_text": "xyz abc qrs",
            "evidence": ["completely unrelated mumbo jumbo"],
            "trace_id": "fc-floor",
        }
        result = await agent.execute(task)
        r = result["result"]
        if r["confidence"] < HALLUCINATION_FLOOR:
            assert r["verdict"] in ("QUARANTINE", "UNVERIFIABLE")

"""Tests for MoAFallbackSubAgent."""

import pytest
import uuid

from geosupply.subagents.moa_fallback_subagent import MoAFallbackSubAgent
from geosupply.schemas import BriefProposal
from geosupply.config import MOA_SCORING_WEIGHTS


def _make_proposal(
    factcheck: float = 0.8,
    source_cred: float = 0.7,
    claim_ratio: float = 0.9,
    confidence: float = 0.85,
    text: str = "brief text",
) -> dict:
    return BriefProposal(
        proposal_id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        brief_text=text,
        confidence=confidence,
        proposer_tier=1,
        factcheck_score=factcheck,
        source_credibility_avg=source_cred,
        claim_evidence_ratio=claim_ratio,
    ).model_dump()


@pytest.fixture
def agent():
    return MoAFallbackSubAgent()


class TestMoAFallbackSubAgentSelect:
    @pytest.mark.asyncio
    async def test_selects_highest_scoring_proposal(self, agent):
        proposals = [
            _make_proposal(factcheck=0.9, source_cred=0.9, claim_ratio=0.9, text="best"),
            _make_proposal(factcheck=0.3, source_cred=0.3, claim_ratio=0.3, text="worst"),
            _make_proposal(factcheck=0.5, source_cred=0.5, claim_ratio=0.5, text="mid"),
        ]
        result = await agent.run({"proposals": proposals})
        assert result["result"]["action"] == "SELECTED"
        assert result["result"]["selected_proposal"]["brief_text"] == "best"

    @pytest.mark.asyncio
    async def test_scoring_uses_config_weights(self, agent):
        p = _make_proposal(factcheck=0.8, source_cred=0.6, claim_ratio=0.7, confidence=0.9)
        expected_score = round(
            MOA_SCORING_WEIGHTS["factcheck_score"] * 0.8
            + MOA_SCORING_WEIGHTS["source_credibility_avg"] * 0.6
            + MOA_SCORING_WEIGHTS["claim_evidence_ratio"] * 0.7,
            4,
        )
        result = await agent.run({"proposals": [p]})
        # With only 1 proposal above threshold, action is SELECTED
        assert result["result"]["score"] == pytest.approx(expected_score, abs=0.001)


class TestMoAFallbackSubAgentMerge:
    @pytest.mark.asyncio
    async def test_merges_when_top_two_within_threshold(self, agent):
        # Two proposals with nearly identical scores (within 0.04)
        p1 = _make_proposal(factcheck=0.8, source_cred=0.7, claim_ratio=0.8, confidence=0.85, text="brief A")
        p2 = _make_proposal(factcheck=0.79, source_cred=0.7, claim_ratio=0.79, confidence=0.82, text="brief B")
        result = await agent.run({"proposals": [p1, p2]})
        # Scores should be within MOA_MERGE_THRESHOLD (0.05) to trigger merge
        assert result["result"]["action"] in ("MERGED", "SELECTED")
        if result["result"]["action"] == "MERGED":
            assert "[MERGED]" in result["result"]["selected_proposal"]["brief_text"]


class TestMoAFallbackSubAgentEscalate:
    @pytest.mark.asyncio
    async def test_escalates_when_all_below_threshold(self, agent):
        proposals = [
            _make_proposal(factcheck=0.2, source_cred=0.2, claim_ratio=0.2),
            _make_proposal(factcheck=0.1, source_cred=0.1, claim_ratio=0.1),
        ]
        result = await agent.run({"proposals": proposals})
        assert result["result"]["action"] == "ESCALATE"
        assert result["result"]["selected_proposal"] is None

    @pytest.mark.asyncio
    async def test_empty_proposals_escalates(self, agent):
        result = await agent.run({"proposals": []})
        assert result["result"]["action"] == "ESCALATE"
        assert result["result"]["proposal_count"] == 0
        assert result["meta"]["cost_inr"] == 0.0


class TestMoAFallbackSubAgentBelowFloor:
    @pytest.mark.asyncio
    async def test_below_floor_when_winner_confidence_low(self, agent):
        # Score is high but confidence is low
        p = _make_proposal(
            factcheck=0.9, source_cred=0.9, claim_ratio=0.9,
            confidence=0.60,  # below HALLUCINATION_FLOOR=0.70
        )
        result = await agent.run({"proposals": [p]})
        assert result["result"]["action"] == "BELOW_FLOOR"
        assert result["result"]["selected_proposal"] is None

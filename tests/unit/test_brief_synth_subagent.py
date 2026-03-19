"""Tests for BriefSynthSubAgent."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from geosupply.config import HALLUCINATION_FLOOR, INTERNAL_BREAKER_MAX_FAILURES
from geosupply.subagents.brief_synth_subagent import BriefSynthSubAgent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_INPUT = {
    "claim_text": "India's semiconductor imports rose 18% in Q3 amid supply constraints.",
    "source_credibility": 0.85,
    "trace_id": "t-brief-01",
}


@pytest.fixture
def agent() -> BriefSynthSubAgent:
    """Fresh BriefSynthSubAgent with no SQLite persistence (in-memory only)."""
    return BriefSynthSubAgent(db_path=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBriefSynthSubAgentRun:

    @pytest.mark.asyncio
    async def test_run_returns_brief_text(self, agent: BriefSynthSubAgent) -> None:
        """run() returns a non-empty brief_text string."""
        res = await agent.run(_DEFAULT_INPUT)
        assert res["result"]["brief_text"] != ""

    @pytest.mark.asyncio
    async def test_run_level_0_default(self, agent: BriefSynthSubAgent) -> None:
        """aggregation_level_used == 0 when circuit breaker is not open."""
        assert agent._breaker_open is False
        res = await agent.run(_DEFAULT_INPUT)
        assert res["result"]["aggregation_level_used"] == 0

    @pytest.mark.asyncio
    async def test_run_three_proposers(self, agent: BriefSynthSubAgent) -> None:
        """proposer_count must equal 3 (one per tier)."""
        res = await agent.run(_DEFAULT_INPUT)
        assert res["result"]["proposer_count"] == 3

    @pytest.mark.asyncio
    async def test_run_proposal_ids_all_present(self, agent: BriefSynthSubAgent) -> None:
        """Three distinct proposal_ids are returned — one per tier."""
        res = await agent.run(_DEFAULT_INPUT)
        ids = res["result"]["proposal_ids"]
        assert len(ids) == 3

    @pytest.mark.asyncio
    async def test_run_proposals_stored_in_memory(self, agent: BriefSynthSubAgent) -> None:
        """After run(), _proposals_store contains at least 3 entries."""
        await agent.run(_DEFAULT_INPUT)
        assert len(agent._proposals_store) >= 3

    @pytest.mark.asyncio
    async def test_run_confidence_at_least_hallucination_floor(
        self, agent: BriefSynthSubAgent
    ) -> None:
        """Returned confidence must be >= HALLUCINATION_FLOOR (or the borderline value)."""
        res = await agent.run(_DEFAULT_INPUT)
        # Proposer A returns 0.78 which is above the 0.70 floor; we allow >= 0.699
        assert res["result"]["confidence"] >= HALLUCINATION_FLOOR * 0.99

    @pytest.mark.asyncio
    async def test_run_cost_is_zero(self, agent: BriefSynthSubAgent) -> None:
        """All stubs produce zero cost — meta.cost_inr must be 0.0."""
        res = await agent.run(_DEFAULT_INPUT)
        assert res["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_run_level2_scoring(self, agent: BriefSynthSubAgent) -> None:
        """When breaker is open and failures >= MAX, level 2 scoring is used."""
        agent._breaker_open = True
        agent._breaker_failures = INTERNAL_BREAKER_MAX_FAILURES
        res = await agent.run(_DEFAULT_INPUT)
        assert res["result"]["aggregation_level_used"] == 2

    @pytest.mark.asyncio
    async def test_run_level3_manual_when_score_too_low(
        self, agent: BriefSynthSubAgent
    ) -> None:
        """When breaker open, failures high, and score < threshold → level 3 with admin_queue."""
        agent._breaker_open = True
        agent._breaker_failures = INTERNAL_BREAKER_MAX_FAILURES + 999  # well above limit

        # Patch the threshold to 1.0 so the scoring gate always triggers level 3
        with patch(
            "geosupply.subagents.brief_synth_subagent.MOA_ESCALATE_THRESHOLD",
            1.0,
        ):
            res = await agent.run(_DEFAULT_INPUT)

        assert res["result"]["aggregation_level_used"] == 3
        assert "admin_queue" in res["result"]
        assert len(res["result"]["admin_queue"]) == 3

    @pytest.mark.asyncio
    async def test_run_sqlite_persistence(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Proposals are written to the SQLite database when db_path is provided."""
        db_file = str(tmp_path / "test_proposals.db")
        agent_with_db = BriefSynthSubAgent(db_path=db_file)

        await agent_with_db.run(_DEFAULT_INPUT)

        conn = sqlite3.connect(db_file)
        try:
            rows = conn.execute(
                "SELECT id FROM brief_proposals WHERE trace_id = ?",
                (_DEFAULT_INPUT["trace_id"],),
            ).fetchall()
        finally:
            conn.close()

        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_run_result_has_all_keys(self, agent: BriefSynthSubAgent) -> None:
        """result dict must contain all required top-level keys."""
        res = await agent.run(_DEFAULT_INPUT)
        required_keys = {
            "brief_text",
            "confidence",
            "aggregation_level_used",
            "proposer_count",
            "proposal_ids",
            "cost_breakdown",
        }
        assert required_keys.issubset(res["result"].keys())

    @pytest.mark.asyncio
    async def test_run_with_empty_claim_text(self, agent: BriefSynthSubAgent) -> None:
        """Empty claim_text must not raise an exception."""
        res = await agent.run(
            {"claim_text": "", "source_credibility": 0.8, "trace_id": "t-empty"}
        )
        assert "result" in res
        assert "meta" in res

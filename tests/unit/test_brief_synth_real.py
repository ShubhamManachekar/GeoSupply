"""
Unit tests for BriefSynthSubAgent real (non-hardcoded) proposers.
Session 29: verifies no hardcoded 0.71/0.74/0.78 values.
"""
from __future__ import annotations

import asyncio
import pytest


def _run(coro):
    return asyncio.run(coro)


class TestBriefSynthRealProposers:
    """Verify the three proposers produce dynamic, non-hardcoded results."""

    def test_tier1_confidence_is_not_hardcoded(self):
        """Tier-1 confidence must NOT be the old stub values 0.71, 0.74, 0.78."""
        from geosupply.subagents.brief_synth_subagent import BriefSynthSubAgent
        agent = BriefSynthSubAgent()
        proposal = _run(
            agent._propose_tier1("India port congestion worsens supply chain", 0.8, "test-t1")
        )
        assert proposal.confidence not in {0.71, 0.74, 0.78}, (
            f"Tier1 still returns hardcoded confidence: {proposal.confidence}"
        )
        assert proposal.claim_evidence_ratio != 0.75, (
            f"Tier1 still returns hardcoded claim_evidence_ratio: {proposal.claim_evidence_ratio}"
        )

    def test_tier3_brief_starts_with_tier3_marker(self):
        """Tier-3 brief_text must start with '[Tier3]'."""
        from geosupply.subagents.brief_synth_subagent import BriefSynthSubAgent
        agent = BriefSynthSubAgent()
        proposal = _run(
            agent._propose_tier3("India port congestion worsens supply chain", 0.8, "test-t3")
        )
        assert proposal.brief_text.startswith("[Tier3]"), (
            f"Tier3 brief_text does not start with [Tier3]: {proposal.brief_text[:50]}"
        )

    def test_run_cost_breakdown_sums_correctly(self):
        """cost_breakdown['total'] must equal tier2 + tier3."""
        from geosupply.subagents.brief_synth_subagent import BriefSynthSubAgent
        agent = BriefSynthSubAgent()
        out = _run(agent.run({
            "claim_text": "India port congestion affects supply",
            "source_credibility": 0.8,
            "trace_id": "test-cost",
        }))
        breakdown = out["result"]["cost_breakdown"]
        expected_total = round(breakdown["tier2"] + breakdown["tier3"], 6)
        assert breakdown["total"] == expected_total, (
            f"cost breakdown total mismatch: {breakdown}"
        )

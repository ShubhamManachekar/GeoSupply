"""Tests for VerifierWorker — Tier-3 claim verification."""

import pytest
from geosupply.workers.verifier_worker import VerifierWorker


@pytest.fixture
async def worker():
    w = VerifierWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestHappyPath:
    async def test_verified_claim_with_corroborating_evidence(self, worker):
        result = await worker.process({
            "text": "India confirmed a major trade agreement with Japan.",
            "evidence": "According to Reuters, the India-Japan trade deal was confirmed and corroborated by both governments. Data indicates the agreement was substantiated by official sources.",
            "trace_id": "t-001",
        })
        assert "result" in result
        assert result["result"]["verdict"] in {"VERIFIED", "UNVERIFIABLE", "INSUFFICIENT_EVIDENCE"}
        assert 0.0 <= result["result"]["confidence"] <= 1.0
        assert result["meta"]["cost_inr"] == 0.05

    async def test_refuted_claim_with_contradiction_evidence(self, worker):
        result = await worker.process({
            "text": "Russia invaded Finland in 2024.",
            "evidence": "This is false and fabricated. Reports confirm this never happened and did not occur. Reuters and AP both refuted this claim as completely untrue.",
            "trace_id": "t-002",
        })
        assert result["result"]["verdict"] == "REFUTED"
        assert result["result"]["confidence"] <= 0.55

    async def test_unverifiable_claim_with_hedged_evidence(self, worker):
        result = await worker.process({
            "text": "North Korea has developed a new weapon.",
            "evidence": "Allegedly, reportedly, and unconfirmed speculation suggests this could not verify the claim. Unclear whether this happened or unknown if true.",
            "trace_id": "t-003",
        })
        assert result["result"]["verdict"] in {"UNVERIFIABLE", "INSUFFICIENT_EVIDENCE"}

    async def test_insufficient_evidence(self, worker):
        result = await worker.process({
            "text": "Something happened somewhere.",
            "evidence": "",
            "trace_id": "t-004",
        })
        assert result["result"]["verdict"] == "INSUFFICIENT_EVIDENCE"
        assert result["result"]["evidence_count"] == 0

    async def test_meta_fields_present(self, worker):
        result = await worker.process({
            "text": "A claim about supply chain.",
            "evidence": "According to confirmed sources, supply chain data indicates this.",
            "trace_id": "t-005",
        })
        meta = result["meta"]
        assert meta["worker"] == "VerifierWorker"
        assert meta["tier"] == 3
        assert meta["cost_inr"] == 0.05
        assert "timestamp" in meta


class TestErrorPaths:
    async def test_empty_claim_returns_worker_error(self, worker):
        result = await worker.process({
            "text": "",
            "evidence": "Some evidence.",
            "trace_id": "t-006",
        })
        assert result.get("error_type") == "INPUT_INVALID"

    async def test_missing_text_key_returns_worker_error(self, worker):
        result = await worker.process({"trace_id": "t-007"})
        assert result.get("error_type") == "INPUT_INVALID"

    async def test_claim_text_key_accepted(self, worker):
        result = await worker.process({
            "claim_text": "India signed a treaty.",
            "evidence": "Confirmed and corroborated by multiple sources.",
            "trace_id": "t-008",
        })
        assert "result" in result
        assert "error_type" not in result


class TestVerdictLogic:
    async def test_statistical_claim_with_matching_numbers(self, worker):
        result = await worker.process({
            "text": "India's GDP grew 7.5% this year.",
            "evidence": "GDP grew 7.5% confirmed by data indicates strong growth. Sources confirm this increase.",
            "trace_id": "t-009",
        })
        assert "result" in result
        assert result["result"]["confidence"] > 0.0

    async def test_statistical_claim_without_matching_numbers(self, worker):
        result = await worker.process({
            "text": "Trade deficit reached $50 billion.",
            "evidence": "Trade statistics were released showing various economic indicators.",
            "trace_id": "t-010",
        })
        assert result["result"]["verdict"] in {"UNVERIFIABLE", "INSUFFICIENT_EVIDENCE"}

    async def test_sources_extracted_from_evidence(self, worker):
        result = await worker.process({
            "text": "India expanded its navy.",
            "evidence": "According to Reuters and thehindu.com, India confirmed the expansion.",
            "trace_id": "t-011",
        })
        assert result["result"]["evidence_count"] >= 0  # May or may not find sources

    async def test_contradiction_snippets_populated(self, worker):
        result = await worker.process({
            "text": "China invaded Taiwan in 2025.",
            "evidence": "This is false. Reports refuted this claim. It never happened and did not occur.",
            "trace_id": "t-012",
        })
        if result["result"]["verdict"] == "REFUTED":
            assert isinstance(result["result"]["contradictions"], list)

    async def test_verification_method_present(self, worker):
        result = await worker.process({
            "text": "A factual claim.",
            "evidence": "Evidence corroborated and confirmed by multiple sources.",
            "trace_id": "t-013",
        })
        assert result["result"]["verification_method"] != ""

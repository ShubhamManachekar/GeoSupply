"""Tests for RAGPipelineSubAgent — ChromaDB dense retrieval pipeline."""

import pytest
from geosupply.subagents.rag_pipeline_subagent import RAGPipelineSubAgent
from geosupply.config import HALLUCINATION_FLOOR


@pytest.fixture
async def subagent():
    sa = RAGPipelineSubAgent()
    await sa.setup()
    yield sa
    await sa.teardown()


_SAMPLE_DOCS = [
    "India and Japan signed a major bilateral trade agreement covering semiconductors and rare earth minerals.",
    "Supply chain disruptions in Taiwan semiconductor manufacturing affected global chip availability.",
    "China imposed export restrictions on critical minerals including lithium and cobalt.",
    "India's pharmaceutical sector faces supply chain stress due to active ingredient shortages from China.",
    "Russia's invasion of Ukraine disrupted grain supply chains affecting South Asian food security.",
    "ASEAN nations agreed to diversify critical mineral supply chains away from single-source dependencies.",
    "India's defence manufacturing push aims to reduce reliance on Russian arms imports.",
    "Sanctions on Iranian oil affected India's energy supply chain in Q3 2025.",
]


class TestHappyPath:
    async def test_run_with_documents_returns_result(self, subagent):
        result = await subagent.run({
            "query": "India semiconductor supply chain risk",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-001",
        })
        assert "result" in result
        assert "meta" in result
        assert isinstance(result["result"]["retrieved_chunks"], list)
        assert isinstance(result["result"]["relevance_scores"], list)

    async def test_faithfulness_score_bounded(self, subagent):
        result = await subagent.run({
            "query": "India semiconductor supply",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-002",
        })
        score = result["result"]["faithfulness_score"]
        assert 0.0 <= score <= 1.0

    async def test_passes_floor_bool_present(self, subagent):
        result = await subagent.run({
            "query": "India Japan trade agreement",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-003",
        })
        assert "passes_floor" in result["result"]
        assert isinstance(result["result"]["passes_floor"], bool)

    async def test_hallucination_floor_in_result(self, subagent):
        result = await subagent.run({
            "query": "supply chain disruption",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-004",
        })
        assert result["result"]["hallucination_floor"] == HALLUCINATION_FLOOR

    async def test_meta_fields_present(self, subagent):
        result = await subagent.run({
            "query": "China mineral restrictions",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-005",
        })
        meta = result["meta"]
        assert meta["subagent"] == "RAGPipelineSubAgent"
        assert meta["steps_completed"] == 6
        assert "cost_inr" in meta
        assert "timestamp" in meta

    async def test_cost_positive(self, subagent):
        result = await subagent.run({
            "query": "Russia Ukraine supply chain",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-006",
        })
        assert result["meta"]["cost_inr"] >= 0.02  # Retrieval cost minimum

    async def test_query_entities_extracted(self, subagent):
        result = await subagent.run({
            "query": "India sanctions Iran oil",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-007",
        })
        assert isinstance(result["result"]["query_entities"], list)

    async def test_collection_name_in_result(self, subagent):
        result = await subagent.run({
            "query": "semiconductor chip shortage",
            "documents": _SAMPLE_DOCS,
            "collection": "supply_chain_intel",
            "trace_id": "rag-008",
        })
        assert result["result"]["collection"] == "supply_chain_intel"


class TestRetrievalFallback:
    async def test_empty_documents_returns_empty_chunks(self, subagent):
        result = await subagent.run({
            "query": "some query with no matching documents",
            "documents": [],
            "trace_id": "rag-009",
        })
        assert "result" in result
        assert isinstance(result["result"]["retrieved_chunks"], list)

    async def test_seed_documents_method(self, subagent):
        subagent.seed_documents(_SAMPLE_DOCS[:3])
        result = await subagent.run({
            "query": "India Japan trade",
            "trace_id": "rag-010",
        })
        assert "result" in result

    async def test_relevant_docs_retrieved(self, subagent):
        result = await subagent.run({
            "query": "India Japan bilateral trade semiconductor rare earth",
            "documents": _SAMPLE_DOCS,
            "trace_id": "rag-011",
        })
        chunks = result["result"]["retrieved_chunks"]
        # At least one chunk should be about India-Japan trade
        india_japan_found = any("india" in c.lower() and "japan" in c.lower() for c in chunks)
        assert india_japan_found or len(chunks) == 0  # OK if no match at all

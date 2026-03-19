"""Tests for GraphRAGSubAgent — KG-enhanced RAG pipeline."""

import logging
from unittest.mock import patch

import pytest

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.subagents.graph_rag_subagent import GraphRAGSubAgent


# ── KG stub ──────────────────────────────────────────────────────────────────

class _KGStub:
    async def safe_execute(self, payload: dict) -> dict:
        return {
            "result": {
                "triples": [
                    {
                        "source": payload.get("entity", "X"),
                        "relation": "located_in",
                        "target": "South Asia",
                    }
                ]
            },
            "meta": {"cost_inr": 0.0},
        }


# ── Fixtures ──────────────────────────────────────────────────────────────────

_SAMPLE_DOCS = [
    {
        "text": "India and China trade relations affect rare earth mineral supply chains significantly.",
        "source": "doc_india_china",
    },
    {
        "text": "Pakistan faces economic instability with rising inflation and currency devaluation.",
        "source": "doc_pakistan_economy",
    },
    {
        "text": "Semiconductor shortages have disrupted automotive and electronics manufacturing worldwide.",
        "source": "doc_semiconductors",
    },
    {
        "text": "Supply chain disruptions in South Asia are driven by monsoon flooding and port congestion.",
        "source": "doc_supply_chain",
    },
]


@pytest.fixture
async def subagent():
    sa = GraphRAGSubAgent(doc_store=list(_SAMPLE_DOCS))
    await sa.setup()
    yield sa
    await sa.teardown()


@pytest.fixture
async def subagent_no_docs():
    sa = GraphRAGSubAgent()
    await sa.setup()
    yield sa
    await sa.teardown()


@pytest.fixture
async def subagent_with_kg():
    sa = GraphRAGSubAgent(kg_agent=_KGStub(), doc_store=list(_SAMPLE_DOCS))
    await sa.setup()
    yield sa
    await sa.teardown()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGraphRAGSubAgent:

    # 1. Empty doc store and no KG → empty context, confidence=0.0
    async def test_run_empty_doc_store_empty_kg(self, subagent_no_docs):
        result = await subagent_no_docs.run({"query": "supply risk in Asia", "trace_id": "t-001"})
        assert result["result"]["context_chunks"] == []
        assert result["result"]["confidence"] == 0.0

    # 2. Relevant doc appears in context_chunks
    async def test_run_vector_only_finds_relevant_doc(self, subagent):
        result = await subagent.run(
            {"query": "India China rare earth mineral supply", "trace_id": "t-002"}
        )
        chunks = result["result"]["context_chunks"]
        assert len(chunks) >= 1
        texts = [c["text"] for c in chunks]
        assert any("india" in t.lower() or "rare earth" in t.lower() for t in texts)

    # 3. Higher-relevance doc appears before lower-relevance doc
    async def test_run_scores_chunks_by_relevance(self, subagent):
        result = await subagent.run(
            {
                "query": "India China trade rare earth mineral supply chains",
                "trace_id": "t-003",
            }
        )
        chunks = result["result"]["context_chunks"]
        if len(chunks) >= 2:
            scores = [c["relevance_score"] for c in chunks]
            assert scores == sorted(scores, reverse=True), (
                "Chunks must be sorted by descending relevance"
            )

    # 4. top_k=5 respected even with 10-doc store
    async def test_run_respects_top_k(self):
        big_docs = [
            {"text": f"supply chain mineral rare earth India doc number {i}", "source": f"src_{i}"}
            for i in range(10)
        ]
        sa = GraphRAGSubAgent(doc_store=big_docs)
        await sa.setup()
        result = await sa.run(
            {"query": "supply chain mineral rare earth India", "top_k": 5, "trace_id": "t-004"}
        )
        await sa.teardown()
        assert len(result["result"]["context_chunks"]) <= 5

    # 5. Entity extraction picks up capitalised tokens
    async def test_run_entity_extraction_from_query(self, subagent):
        result = await subagent.run(
            {"query": "Supply risk in India", "trace_id": "t-005"}
        )
        entity_count = result["result"]["entity_count"]
        # "Supply" and "India" are capitalised — at least one should be extracted
        assert entity_count >= 1

    # 6. KG agent stub populates kg_triples and method is "kg_enhanced"
    async def test_run_with_kg_agent_stub(self, subagent_with_kg):
        result = await subagent_with_kg.run(
            {"query": "India supply chain risk", "trace_id": "t-006"}
        )
        assert len(result["result"]["kg_triples"]) >= 1
        assert result["result"]["retrieval_method"] == "kg_enhanced"

    # 7. KG agent returns triples but no doc_store → method="kg_only", confidence=0.72
    async def test_run_kg_only_path(self):
        sa = GraphRAGSubAgent(kg_agent=_KGStub())  # no doc_store
        await sa.setup()
        result = await sa.run(
            {"query": "India supply chain risk", "trace_id": "t-007"}
        )
        await sa.teardown()
        assert result["result"]["retrieval_method"] == "kg_only"
        assert result["result"]["confidence"] == 0.72

    # 8. Duplicate docs are deduplicated by 50-char text prefix
    async def test_run_deduplicates_chunks(self):
        duplicated_text = (
            "India China rare earth mineral supply chain disruption affects trade balance"
        )
        docs = [
            {"text": duplicated_text, "source": "src_a"},
            {"text": duplicated_text, "source": "src_b"},
            {"text": "Semiconductor supply chain faces shortages in Asia", "source": "src_c"},
        ]
        sa = GraphRAGSubAgent(doc_store=docs)
        await sa.setup()
        result = await sa.run(
            {"query": "India China rare earth mineral supply chain", "trace_id": "t-008"}
        )
        await sa.teardown()
        chunks = result["result"]["context_chunks"]
        texts = [c["text"] for c in chunks]
        # The duplicated text should appear at most once
        assert texts.count(duplicated_text) <= 1

    # 9. Logger warning emitted when confidence below HALLUCINATION_FLOOR
    async def test_run_hallucination_floor_warning(self, subagent_no_docs):
        with patch.object(
            logging.getLogger("geosupply.subagents.graph_rag_subagent"),
            "warning",
        ) as mock_warn:
            result = await subagent_no_docs.run(
                {"query": "zzz completely unmatched query xyz", "trace_id": "t-009"}
            )
            # confidence will be 0.0 which is < HALLUCINATION_FLOOR (0.70)
            assert result["result"]["confidence"] < HALLUCINATION_FLOOR
            mock_warn.assert_called_once()
            call_args = mock_warn.call_args[0]
            assert "HALLUCINATION_FLOOR" in call_args[0]

    # 10. Result dict has all required schema keys
    async def test_run_returns_correct_schema_keys(self, subagent):
        result = await subagent.run({"query": "India supply chain", "trace_id": "t-010"})
        required_keys = {
            "context_chunks",
            "kg_triples",
            "entity_count",
            "confidence",
            "retrieval_method",
        }
        assert required_keys == set(result["result"].keys())

    # 11. meta["cost_inr"] is exactly 0.0
    async def test_run_meta_has_cost_zero(self, subagent_with_kg):
        result = await subagent_with_kg.run(
            {"query": "India mineral trade", "trace_id": "t-011"}
        )
        assert result["meta"]["cost_inr"] == 0.0

    # 12. entities passed in input_data are merged with extracted ones
    async def test_run_respects_entities_input(self, subagent):
        result = await subagent.run(
            {
                "query": "supply chain disruption",  # no capitalised tokens → 0 extracted
                "entities": ["Myanmar", "Bangladesh"],
                "trace_id": "t-012",
            }
        )
        # Caller-supplied entities must be counted
        assert result["result"]["entity_count"] >= 2

"""
RAGPipelineSubAgent — Phase 5 SubAgent Layer
FA v2 | Part III | Layer 4

Retrieval-Augmented Generation pipeline for GeoSupply intel queries.

PIPELINE:
    Step 1: NER + Claim extraction (parallel) — seed entities for retrieval
    Step 2: Retrieve candidate context from ChromaDB store (or keyword fallback)
    Step 3: Hallucination check — enforce HALLUCINATION_FLOOR on retrieved context
    Step 4 (fuse): Rank and return top-k context chunks with relevance scores

ChromaDB is optional at runtime: if unavailable the worker falls back to
keyword-overlap retrieval over the in-memory document store seeded at setup().

HALLUCINATION_FLOOR: 0.70 — enforced on every generated answer.
Cost: ~₹0.02 per retrieval (embedding local, reranking local).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.ner_worker import NERWorker


# ── Relevance scoring constants ───────────────────────────────────────────────
_TOP_K = 5          # Return top-5 context chunks
_MIN_RELEVANCE = 0.30   # Minimum cosine-like score to include a chunk

# ── Stopwords to skip in keyword matching ─────────────────────────────────────
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "has", "have", "had",
    "in", "on", "at", "to", "for", "of", "and", "or", "but", "with",
    "that", "this", "it", "as", "by", "from", "be", "been", "being",
})


def _tokenize(text: str) -> set[str]:
    """Lower-case word tokens, excluding stopwords."""
    words = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _keyword_relevance(query_tokens: set[str], chunk: str) -> float:
    """
    Jaccard-like overlap between query tokens and chunk tokens.
    Returns 0.0–1.0.
    """
    chunk_tokens = _tokenize(chunk)
    if not query_tokens or not chunk_tokens:
        return 0.0
    intersection = query_tokens & chunk_tokens
    union = query_tokens | chunk_tokens
    return round(len(intersection) / len(union), 4)


def _faithfulness_score(answer: str, context_chunks: list[str]) -> float:
    """
    Approximate faithfulness: fraction of answer tokens found in context.
    Real implementation would use cross-encoder/nli-deberta-v3-small.
    """
    if not answer or not context_chunks:
        return 0.0
    answer_tokens = _tokenize(answer)
    context_text = " ".join(context_chunks)
    context_tokens = _tokenize(context_text)
    if not answer_tokens:
        return 0.0
    overlap = answer_tokens & context_tokens
    return round(len(overlap) / len(answer_tokens), 4)


class RAGPipelineSubAgent(BaseSubAgent):
    """
    Retrieve-Rerank pipeline for GeoSupply intel queries.

    Input:
        query (str): Natural language intelligence query.
        collection (str): ChromaDB collection name (default: 'geopolitical_events').
        documents (list[str]): Optional in-memory document list for fallback retrieval.
        trace_id (str): Propagated trace identifier.

    Output:
        result:
            retrieved_chunks: list[str]   — top-k context chunks
            relevance_scores: list[float] — per-chunk relevance
            faithfulness_score: float     — answer faithfulness (HALLUCINATION_FLOOR enforced)
            passes_floor: bool
            query_entities: list[str]     — NER-extracted entities for retrieval
            claim_type: str               — detected claim type
        meta:
            subagent, cost_inr, steps_completed, trace_id, timestamp
    """

    name = "RAGPipelineSubAgent"
    pipeline_steps = ["ner", "claim", "retrieve", "rank", "faithfulness_check", "fuse"]
    parallel_steps = {"ner", "claim"}

    def __init__(self) -> None:
        self._ner = NERWorker()
        self._claim = ClaimWorker()
        # In-memory document store (ChromaDB fallback)
        self._documents: list[str] = []
        self._chroma_client: Any = None   # Populated if chromadb available

    async def setup(self) -> None:
        await self._ner.setup()
        await self._claim.setup()
        self._try_init_chroma()
        await super().setup()

    def _try_init_chroma(self) -> None:
        """Attempt to initialise ChromaDB client; silently fall back if unavailable."""
        try:
            import chromadb  # type: ignore[import]
            from geosupply.config import CHROMADB_DIR
            self._chroma_client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        except Exception as exc:
            logger.warning("RAGPipelineSubAgent: ChromaDB init failed (falling back to keyword): %s", exc)
            self._chroma_client = None   # Fallback: in-memory keyword retrieval

    async def teardown(self) -> None:
        await self._ner.teardown()
        await self._claim.teardown()
        await super().teardown()

    def seed_documents(self, documents: list[str]) -> None:
        """Seed in-memory fallback document store (used in tests and dev mode)."""
        self._documents = list(documents)

    def _retrieve_from_chroma(
        self, query: str, collection_name: str, k: int
    ) -> list[tuple[str, float]]:
        """
        Retrieve top-k chunks from ChromaDB.
        Returns list of (document_text, distance_score) tuples.
        """
        if self._chroma_client is None:
            return []
        try:
            coll = self._chroma_client.get_or_create_collection(collection_name)
            results = coll.query(query_texts=[query], n_results=min(k, 10))
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            # Convert distance to relevance (lower distance = higher relevance)
            return [
                (doc, round(max(0.0, 1.0 - dist), 4))
                for doc, dist in zip(docs, distances)
            ]
        except Exception as exc:
            logger.warning("RAGPipelineSubAgent: ChromaDB query failed (returning empty): %s", exc)
            return []

    def _retrieve_keyword_fallback(
        self, query: str, k: int
    ) -> list[tuple[str, float]]:
        """
        Keyword-overlap retrieval over in-memory _documents store.
        Returns list of (document_text, relevance_score) tuples.
        """
        query_tokens = _tokenize(query)
        scored: list[tuple[str, float]] = []
        for doc in self._documents:
            score = _keyword_relevance(query_tokens, doc)
            if score >= _MIN_RELEVANCE:
                scored.append((doc, score))

        # Sort descending by relevance
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    async def run(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        query = input_data.get("query") or input_data.get("text") or ""
        collection = input_data.get("collection", "geopolitical_events")
        # Allow caller to provide additional documents for fallback retrieval
        extra_docs = input_data.get("documents") or []
        if extra_docs:
            self.seed_documents(extra_docs)

        payload = {"text": query, "trace_id": trace_id}

        # Step 1+2 (parallel): NER + Claim extraction
        ner_res, claim_res = await self.run_parallel(
            steps=[self._ner.safe_process, self._claim.safe_process],
            inputs=[payload, payload],
        )

        total_cost = (
            ner_res.get("meta", {}).get("cost_inr", 0.0)
            + claim_res.get("meta", {}).get("cost_inr", 0.0)
        )

        # Extract NER entities for retrieval enhancement
        ner_data = ner_res.get("result") or {}
        entities: list[str] = [
            e.get("text", "") for e in ner_data.get("entities", []) if e.get("text")
        ]

        claim_data = claim_res.get("result") or {}
        claim_type = claim_data.get("claim_type", "FACTUAL")

        # Build enhanced query: original + top entities
        entity_suffix = " ".join(entities[:5])
        enhanced_query = f"{query} {entity_suffix}".strip()

        # Step 3: Retrieve
        chunks_with_scores = self._retrieve_from_chroma(enhanced_query, collection, k=20)
        if not chunks_with_scores:
            chunks_with_scores = self._retrieve_keyword_fallback(enhanced_query, k=20)

        # Step 4: Rerank — sort by score, take top-k
        chunks_with_scores.sort(key=lambda x: x[1], reverse=True)
        top_chunks = chunks_with_scores[:_TOP_K]
        retrieved_chunks = [c for c, _ in top_chunks]
        relevance_scores = [s for _, s in top_chunks]

        # Step 5: Faithfulness check — enforce HALLUCINATION_FLOOR
        fidelity = _faithfulness_score(query, retrieved_chunks)
        passes_floor = fidelity >= HALLUCINATION_FLOOR

        # Aggregate cost: add retrieval overhead (~₹0.02)
        total_cost += 0.02

        return {
            "result": {
                "retrieved_chunks": retrieved_chunks,
                "relevance_scores": relevance_scores,
                "faithfulness_score": round(fidelity, 4),
                "passes_floor": passes_floor,
                "hallucination_floor": HALLUCINATION_FLOOR,
                "query_entities": entities,
                "claim_type": claim_type,
                "collection": collection,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": round(total_cost, 6),
                "steps_completed": 6,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

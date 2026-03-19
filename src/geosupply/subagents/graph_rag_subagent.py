"""
GraphRAGSubAgent — Layer 4 SubAgent
FA v2 | Part III | §3.2 — KG-enhanced RAG

Enhances vector retrieval by first traversing the Knowledge Graph
entity neighborhood to build an entity-enriched query context,
then combining KG triples with vector search results.

PIPELINE:
    Step 1: extract_entities  — NER-lite: extract entity names from query
    Step 2: kg_traversal      — KnowledgeGraphAgent.execute(KG_QUERY) per entity (parallel)
    Step 3: enrich_query      — merge entity neighborhood into enriched query string
    Step 4: vector_search     — keyword-overlap retrieval over doc_store
    Step 5: merge_and_rerank  — combine KG triples + vector results, deduplicate
    Step 6: hallucination_gate — confidence ≥ HALLUCINATION_FLOOR

Cost: ₹0.0 — all Tier-0 (no LLM calls)
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_subagent import BaseSubAgent

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "has", "have",
    "in", "on", "at", "to", "for", "of", "and", "or", "but", "with",
    "that", "this", "it", "as", "by", "from", "be", "been",
})

_DEFAULT_TOP_K = 5
_DEFAULT_KG_DEPTH = 1
_MIN_RELEVANCE = 0.20


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _keyword_relevance(query_tokens: set[str], chunk: str) -> float:
    chunk_tokens = _tokenize(chunk)
    if not query_tokens or not chunk_tokens:
        return 0.0
    intersection = query_tokens & chunk_tokens
    union = query_tokens | chunk_tokens
    return round(len(intersection) / len(union), 4)


class GraphRAGSubAgent(BaseSubAgent):
    """
    KG-enhanced RAG pipeline for GeoSupply intel queries.

    Input:
        query (str): Natural language intelligence query.
        entities (list[str]): Optional pre-extracted entities to merge.
        top_k (int): Maximum context chunks to return (default: 5).
        kg_depth (int): KG traversal depth per entity (default: 1).
        trace_id (str): Propagated trace identifier.

    Output:
        result:
            context_chunks: list[dict]   — top-k enriched context chunks
            kg_triples: list[dict]       — triples retrieved from KG
            entity_count: int            — number of entities extracted/merged
            confidence: float            — mean relevance score
            retrieval_method: str        — "kg_enhanced" | "vector_only" | "kg_only"
        meta:
            subagent, cost_inr, trace_id, timestamp
    """

    name = "GraphRAGSubAgent"
    pipeline_steps = [
        "extract_entities",
        "kg_traversal",
        "enrich_query",
        "vector_search",
        "merge_and_rerank",
        "hallucination_gate",
    ]
    parallel_steps = {"kg_traversal"}

    def __init__(
        self,
        kg_agent=None,                     # KnowledgeGraphAgent or stub — optional
        doc_store: list[dict] | None = None,  # list of {"text": str, "source": str}
    ) -> None:
        self._kg_agent = kg_agent
        self._doc_store: list[dict] = doc_store or []

    # ── Step 1: extract_entities ──────────────────────────────────────────────

    def _extract_entities(self, query: str) -> list[str]:
        """
        NER-lite: extract capitalised words (2+ chars) and quoted phrases
        from the query string.
        """
        # Quoted phrases (preserve original casing)
        quoted: list[str] = re.findall(r'"([^"]+)"', query)

        # Capitalised words that are not sentence-initial stopwords
        capitalised: list[str] = re.findall(r'\b([A-Z][a-zA-Z]{1,})\b', query)

        # Deduplicate while preserving order
        seen: set[str] = set()
        entities: list[str] = []
        for e in quoted + capitalised:
            key = e.lower()
            if key not in seen:
                seen.add(key)
                entities.append(e)
        return entities

    # ── Step 2: kg_traversal (parallel) ──────────────────────────────────────

    async def _kg_traverse_entity(self, entity: str, kg_depth: int) -> list[dict]:
        """Traverse KG for a single entity and return its triples."""
        if self._kg_agent is None:
            return []
        try:
            result = await self._kg_agent.safe_execute(
                {"action": "KG_QUERY", "entity": entity, "depth": kg_depth}
            )
            return result.get("result", {}).get("triples", [])
        except Exception as exc:
            logger.warning(
                "GraphRAGSubAgent: KG traversal failed for entity %r: %s", entity, exc
            )
            return []

    async def _kg_traversal_parallel(
        self, entities: list[str], kg_depth: int
    ) -> list[dict]:
        """Run KG traversal for all entities in parallel and flatten results."""
        if not entities:
            return []
        triple_lists: list[list[dict]] = await asyncio.gather(
            *[self._kg_traverse_entity(entity, kg_depth) for entity in entities],
            return_exceptions=False,
        )
        all_triples: list[dict] = []
        for triples in triple_lists:
            all_triples.extend(triples)
        return all_triples

    # ── Step 3: enrich_query ─────────────────────────────────────────────────

    @staticmethod
    def _enrich_query(query: str, kg_triples: list[dict]) -> str:
        """Build enriched query by appending KG triple text."""
        if not kg_triples:
            return query
        triple_text = " ".join(
            f"{t['source']} {t['relation']} {t['target']}" for t in kg_triples
        )
        return f"{query} {triple_text}"

    # ── Step 4: vector_search ─────────────────────────────────────────────────

    def _vector_search(
        self, enriched_query: str, top_k: int
    ) -> list[dict]:
        """
        Keyword-overlap retrieval over self._doc_store.
        Returns scored chunks sorted descending, capped at top_k.
        """
        query_tokens = _tokenize(enriched_query)
        scored: list[dict] = []
        for doc in self._doc_store:
            score = _keyword_relevance(query_tokens, doc.get("text", ""))
            if score >= _MIN_RELEVANCE:
                scored.append({
                    "text": doc.get("text", ""),
                    "source": doc.get("source", ""),
                    "relevance_score": score,
                })
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    # ── Step 5: merge_and_rerank ──────────────────────────────────────────────

    @staticmethod
    def _deduplicate_chunks(chunks: list[dict]) -> list[dict]:
        """Deduplicate context chunks by their first 50 characters."""
        seen_prefixes: set[str] = set()
        unique: list[dict] = []
        for chunk in chunks:
            prefix = chunk.get("text", "")[:50]
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                unique.append(chunk)
        return unique

    # ── Main pipeline ─────────────────────────────────────────────────────────

    async def run(self, input_data: dict) -> dict:
        query: str = input_data.get("query") or input_data.get("text") or ""
        top_k: int = int(input_data.get("top_k", _DEFAULT_TOP_K))
        kg_depth: int = int(input_data.get("kg_depth", _DEFAULT_KG_DEPTH))
        trace_id: str = input_data.get("trace_id", "")

        # ── Step 1: extract_entities ─────────────────────────────────────────
        extracted_entities = self._extract_entities(query)
        extra_entities: list[str] = input_data.get("entities") or []
        # Merge: start from extra_entities (caller-supplied), then append
        # extracted ones that aren't already present (case-insensitive).
        seen_lower: set[str] = {e.lower() for e in extra_entities}
        for e in extracted_entities:
            if e.lower() not in seen_lower:
                extra_entities = list(extra_entities) + [e]
                seen_lower.add(e.lower())
        entities: list[str] = extra_entities

        # ── Step 2: kg_traversal (parallel) ──────────────────────────────────
        all_kg_triples = await self._kg_traversal_parallel(entities, kg_depth)

        # ── Step 3: enrich_query ──────────────────────────────────────────────
        enriched_query = self._enrich_query(query, all_kg_triples)

        # ── Step 4: vector_search ──────────────────────────────────────────────
        context_chunks = self._vector_search(enriched_query, top_k)

        # ── Step 5: merge_and_rerank ───────────────────────────────────────────
        context_chunks = self._deduplicate_chunks(context_chunks)

        # Determine confidence and retrieval_method
        if not self._doc_store and all_kg_triples:
            # KG-only path: no documents, but KG returned triples
            retrieval_method = "kg_only"
            confidence = 0.72
        else:
            retrieval_method = "kg_enhanced" if all_kg_triples else "vector_only"
            if context_chunks:
                confidence = round(
                    sum(c["relevance_score"] for c in context_chunks) / len(context_chunks),
                    4,
                )
            else:
                confidence = 0.0

        # ── Step 6: hallucination_gate ─────────────────────────────────────────
        if confidence < HALLUCINATION_FLOOR:
            logger.warning(
                "GraphRAGSubAgent: confidence %.2f below HALLUCINATION_FLOOR", confidence
            )
            # Do NOT raise — return with low confidence flagged

        return {
            "result": {
                "context_chunks": context_chunks,
                "kg_triples": all_kg_triples,
                "entity_count": len(entities),
                "confidence": confidence,
                "retrieval_method": retrieval_method,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

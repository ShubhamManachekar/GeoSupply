---
name: rag-architect
description: RAG pipeline design and optimization for GeoSupply's GraphRAG, ChromaDB, and SubAgent layer. Covers chunking, embedding, retrieval, reranking, evaluation, and GraphRAG patterns — all within GeoSupply's Pydantic-strict, cost-INR, hallucination-floored architecture.
---

# RAG Architect — GeoSupply Edition

> Upstream source: alirezarezvani/claude-skills · engineering/rag-architect
> Adapted for: GeoSupply FA v3 SubAgent layer, ChromaDB, Pydantic v2, INR cost tracking

## GeoSupply RAG Context

GeoSupply SubAgent Layer (Phase 5 — COMPLETE):
- ✅ `NLPPipelineSubAgent` — parallel Sentiment+NER+Claim enrichment pipeline
- ✅ `HallucinationCheckSubAgent` — composite confidence + HALLUCINATION_FLOOR gate
- ✅ `AuditSampleSubAgent` — probabilistic QA sampling with claim+sentiment scoring
- ✅ `SourceFeedbackSubAgent` — credibility feedback loop with 3-strike penalty system
- ✅ `RAGPipelineSubAgent` — ChromaDB dense retrieval + keyword fallback; NER+Claim entity-enhanced query; top-k rerank; HALLUCINATION_FLOOR faithfulness check

Planned RAG SubAgents (Phase 8+):
- ⬜ `GraphRAGSubAgent` — NetworkX KG traversal + vector hybrid
- ⬜ `BriefSynthSubAgent` — Final brief generation from ranked context chunks

All RAG workers feed into SubAgents through the EventBus. The `HALLUCINATION_FLOOR = 0.70` must be enforced at every generation step.

---

## 1. Chunking Strategy for GeoSupply Intel Docs

### Recommended: Semantic + Paragraph Hybrid
```python
# For geopolitical articles (GDELT, ACLED, news)
chunk_size = 512          # tokens
chunk_overlap = 64        # ~12% overlap for context continuity
strategy = "paragraph"    # Respect article structure

# For government reports / long-form docs
chunk_size = 256
chunk_overlap = 32
strategy = "semantic"     # Topic-boundary aware
```

**Never** split mid-sentence for NER or claim extraction feeds — the ClaimWorker requires complete grammatical units.

---

## 2. Embedding Model Selection (Tier Mapping)

| Tier | Model | Use Case | Cost |
|------|-------|----------|------|
| Tier 0 | `all-MiniLM-L6-v2` (384d) | Fast ingestion dedup | ₹0 (local) |
| Tier 1 | `all-mpnet-base-v2` (768d) | Standard retrieval | ₹0 (local) |
| Tier 2 | `multilingual-e5-large` (1024d) | Hindi/Urdu/Tamil docs | ₹0 (local) |
| Tier 3 | `text-embedding-ada-002` (1536d) | High-stakes briefs only | ~₹0.08/1K tokens |

Always use `sentence-transformers` for Tier 0–2 (zero API cost, local).

---

## 3. ChromaDB Collection Architecture

```python
# GeoSupply ChromaDB collections
COLLECTIONS = {
    "geopolitical_events":  {"dim": 768, "hnsw_M": 16, "ef_construction": 200},
    "supply_chain_intel":   {"dim": 768, "hnsw_M": 16},
    "source_credibility":   {"dim": 384, "hnsw_M": 8},   # Smaller — faster lookup
    "knowledge_graph_docs": {"dim": 768, "hnsw_M": 32},  # Higher M for graph traversal
    "india_specific":       {"dim": 1024, "hnsw_M": 16}, # Multilingual embeddings
}
```

**Metadata always include**: `source_id`, `credibility_score`, `event_date`, `language`, `region`, `schema_version`.

---

## 4. Retrieval Strategies

### Default: Hybrid Retrieval (Dense + BM25)
```python
# Reciprocal Rank Fusion weights for GeoSupply
DENSE_WEIGHT = 0.65    # Semantic similarity
SPARSE_WEIGHT = 0.35   # BM25 keyword match (entity names, country codes)
```

### GraphRAG Pattern (for KnowledgeGraph layer)
```python
# 1. Entity extraction via NERWorker (Tier 1 STATIC)
# 2. Graph traversal: find k-hop neighbors in NetworkX KG
# 3. Retrieve embeddings for all neighbor nodes
# 4. Merge with standard dense retrieval results
# 5. Rerank with cross-encoder
```

### Reranking
Use `cross-encoder/ms-marco-MiniLM-L-6-v2` — zero API cost, local, handles geopolitical entity pairs well.

---

## 5. Query Transformation

### HyDE for Intelligence Queries
```python
# When user asks: "What are the risks to Indian pharma supply chain?"
# HyDE generates: "Article discussing [specific threat], [country], [commodity]..."
# Then embed the hypothetical article, not the raw query
```

### Multi-Query for Uncertain Entities
Use when entity resolution is ambiguous (e.g., "PMC Wagner" vs "Wagner Group").

---

## 6. Hallucination Control (LOCKED: floor = 0.70)

```python
# Every RAG generation step MUST:
# 1. Include retrieved chunks in prompt as grounding context
# 2. Score faithfulness: NLI entailment(answer, context) >= 0.70
# 3. If score < 0.70 → return WorkerError, do NOT return answer
# 4. Include source attribution in every BriefSynthSubAgent output

FAITHFULNESS_CHECK = {
    "model": "cross-encoder/nli-deberta-v3-small",  # Local, zero cost
    "threshold": HALLUCINATION_FLOOR,  # 0.70 from config.py
    "fallback": "return WorkerError(error_type='HALLUCINATION', ...)"
}
```

---

## 7. Cost Management (INR)

```python
# Tier 0-2 embeddings: ₹0 (local sentence-transformers)
# Tier 3 embeddings: ~₹0.08/1K tokens — use only for final brief synthesis
# Reranking: ₹0 (local cross-encoder)
# ChromaDB: ₹0 (local SQLite backend)

# Budget allocation recommendation:
# 60% of ₹500/month → Tier-3 LLM calls (brief synthesis, verification)
# 40% → external data API ingestion
# 0% → embeddings (all local)
```

---

## 8. SubAgent Implementation Pattern

```python
class RAGSubAgent(BaseSubAgent):
    """Retrieve-Rerank-Generate pipeline for GeoSupply intel."""
    name = "rag_sub"
    tier = LLMTier.LARGE_20B  # Generation only; retrieval is Tier 0

    async def run(self, query: str, collection: str) -> dict:
        # Step 1: Embed query (Tier 1 local)
        q_emb = await self._embed(query, tier=LLMTier.MEDIUM_14B)

        # Step 2: Hybrid retrieve
        dense = await self._chroma_search(q_emb, collection, k=20)
        sparse = await self._bm25_search(query, collection, k=20)
        merged = reciprocal_rank_fusion(dense, sparse)

        # Step 3: Rerank top 20 → top 5
        reranked = await self._rerank(query, merged[:20])[:5]

        # Step 4: Generate with faithfulness check
        answer = await self._generate(query, reranked)
        score = await self._faithfulness_score(answer, reranked)
        if score < HALLUCINATION_FLOOR:
            return WorkerError(error_type="HALLUCINATION", ...)

        return {"result": answer, "sources": reranked, "meta": {"cost_inr": ...}}
```

---

## 9. Evaluation Metrics

| Metric | Target | Tool |
|--------|--------|------|
| Context Relevance | > 0.80 | embedding cosine sim |
| Faithfulness | > 0.70 (LOCKED floor) | NLI cross-encoder |
| Answer Relevance | > 0.85 | LLM-as-judge |
| Retrieval Precision@5 | > 0.75 | synthetic QA pairs |
| Latency P95 | < 3s | structlog timers |

---

## Related Skills
- `knowledge-graph` — When GraphRAG traversal is needed
- `worker-factory` — To scaffold RAGWorker implementations
- `supervisor-designer` — NLPSupervisor manages RAG SubAgents
- `loophole-hunter` — Audit RAG pipeline for injection vulnerabilities

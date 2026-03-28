---
name: knowledge-graph
description: Knowledge graph construction, deduplication, NetworkX traversal, GraphRAG integration, and KG maintenance for GeoSupply's intelligence layer. Covers KnowledgeUpdateRequest schema, dedup keys, entity linking, and graph-aware retrieval.
---

# Knowledge Graph — GeoSupply Intelligence Layer

> Custom GeoSupply skill — KG design, dedup, GraphRAG, and NetworkX patterns

## KG Architecture

```
KnowledgeGraphAgent   ← Owns write authority to KG (Layer 3) [IMPLEMENTED ✅]
In-memory dict        ← Primary graph store (adjacency dict) [IMPLEMENTED ✅]
SQLite edge store     ← Edge metadata + dedup keys + provenance [IMPLEMENTED ✅ Session 21]
ChromaDB              ← Vector embeddings for nodes (planned)
NetworkX              ← Graph traversal for GraphRAG (planned)
```

**SQLite persistence (Session 21)**: Pass `db_path=Path(...)` to `KnowledgeGraphAgent.__init__()`, call `await agent.setup()`. On startup, `_load_from_db()` restores all edges. `_persist_edge()` is called on every `_write_triple()`. On `teardown()`, pending buffer is flushed.

```python
# With persistence:
agent = KnowledgeGraphAgent(db_path=Path("data/kg.db"))
await agent.setup()   # loads existing edges from SQLite

# Without persistence (test/in-memory mode):
agent = KnowledgeGraphAgent()   # no db_path → pure in-memory
```

**Single-writer rule**: Only `KnowledgeGraphAgent` writes to the KG. Workers send `KG_ADD_TRIPLE` tasks — the agent batches them (G5 write-buffer, size 50) and deduplicates within a 1-hour sliding window.

## Implementation Status (2026-03-19)
`KnowledgeGraphAgent` is implemented at `src/geosupply/agents/knowledge_graph_agent.py`:
- ✅ In-memory adjacency dict graph (source → target → relation → weight)
- ✅ Write-buffer batching (`KG_WRITE_BUFFER_BATCH_SIZE = 50`)
- ✅ Dedup key = `(source.lower(), target.lower(), relation.upper())` — FA v1 G5
- ✅ 1-hour dedup window (`KG_DEDUP_WINDOW_SECONDS = 3600`)
- ✅ Canary sampling (last `KG_CANARY_SAMPLE_SIZE = 10` triples)
- ✅ Task types: `KG_ADD_TRIPLE`, `KG_QUERY`, `KG_FLUSH`, `KG_CANARY`, `KG_STATS`
- ⬜ NetworkX integration (planned Phase 7 full)
- ⬜ ChromaDB vector embeddings
- ⬜ SQLite provenance store

## Task API
```python
# Add a triple
await agent.safe_execute({"task_type": "KG_ADD_TRIPLE", "source": "India", "relation": "TRADE", "target": "Japan", "weight": 1.0})
# Query neighbours
await agent.safe_execute({"task_type": "KG_QUERY", "entity": "India", "relation_filter": "TRADE"})
# Force flush buffer
await agent.safe_execute({"task_type": "KG_FLUSH"})
# Get stats
await agent.safe_execute({"task_type": "KG_STATS"})
# Canary sample
await agent.safe_execute({"task_type": "KG_CANARY"})
```

---

## 1. Entity Types (GeoSupply KG Ontology)

```python
ENTITY_TYPES = {
    # Geopolitical
    "COUNTRY":        {"id_format": "ISO-3", "example": "IND"},
    "REGION":         {"id_format": "country:region", "example": "IND:Punjab"},
    "CONFLICT_ZONE":  {"id_format": "cz:{name}", "example": "cz:manipur_2023"},
    "PORT":           {"id_format": "LOCODE", "example": "INNSA"},  # JNPT

    # Supply Chain
    "SUPPLIER":       {"id_format": "sup:{domain}", "example": "sup:tata-steel.com"},
    "COMMODITY":      {"id_format": "HSN:{code}", "example": "HSN:720711"},
    "SHIPPING_ROUTE": {"id_format": "rt:{from}_{to}", "example": "rt:INCOK_CNSHA"},
    "SANCTIONS_LIST": {"id_format": "sl:{list}", "example": "sl:ofac_sdn"},

    # Intelligence
    "SOURCE":         {"id_format": "src:{domain}", "example": "src:thehindu.com"},
    "EVENT":          {"id_format": "evt:{uuid}", "example": "evt:abc123"},
    "ACTOR":          {"id_format": "act:{name_normalized}", "example": "act:pmnarendra_modi"},
    "CLAIM":          {"id_format": "clm:{hash}", "example": "clm:sha256[:8]"},
}

RELATION_TYPES = [
    "LOCATED_IN",       # Supplier LOCATED_IN Region
    "OPERATES_PORT",    # Country OPERATES_PORT Port
    "AFFECTS",          # Event AFFECTS Supplier/Route/Commodity
    "SANCTIONED_BY",    # Supplier SANCTIONED_BY SanctionsList
    "REPORTED_BY",      # Claim REPORTED_BY Source
    "CORROBORATES",     # Claim CORROBORATES Claim
    "CONTRADICTS",      # Claim CONTRADICTS Claim
    "SUPPLIED_BY",      # Commodity SUPPLIED_BY Supplier
    "TRANSITS_VIA",     # Commodity TRANSITS_VIA Port
    "INVOLVES_ACTOR",   # Event INVOLVES_ACTOR Actor
]
```

---

## 2. KnowledgeUpdateRequest Schema (Schema #22)

```python
class KnowledgeUpdateRequest(BaseModel):
    schema_version: int = 1
    update_id: str            # UUID
    operation: Literal["UPSERT", "DELETE", "MERGE"]
    entity_type: str          # From ENTITY_TYPES
    entity_id: str            # Canonical ID using id_format above
    attributes: dict          # Entity properties
    relations: list[dict]     # [{"type": "AFFECTS", "target_id": "sup:..."}]

    # Dedup key (G5 mitigation) — prevents duplicate edges
    dedup_key: str            # f"{source_entity}:{relation}:{target_entity}"
    source_id: str            # Which worker/source generated this update
    confidence: float         # Must be >= 0.50 (below this, skip)
    trace_id: str
    created_at: datetime
```

---

## 3. Deduplication Strategy (G5)

```python
# Dedup window from config.py
KG_DEDUP_WINDOW_SECONDS = 3600   # 1 hour

# Dedup key construction (LOCKED pattern)
def make_dedup_key(source: str, relation: str, target: str) -> str:
    """Canonical dedup key for KG edges."""
    return f"{source.lower()}:{relation.upper()}:{target.lower()}"

# Dedup check before write
async def _is_duplicate(self, request: KnowledgeUpdateRequest) -> bool:
    window_start = datetime.now(timezone.utc) - timedelta(seconds=KG_DEDUP_WINDOW_SECONDS)
    existing = await self._db.query(
        "SELECT 1 FROM kg_edges WHERE dedup_key = ? AND created_at > ?",
        (request.dedup_key, window_start)
    )
    return len(existing) > 0
```

---

## 4. Batch Write Pattern

```python
# config.py: KG_WRITE_BUFFER_BATCH_SIZE = 50
# Accumulate updates, flush every 50 or every 60 seconds

class KnowledgeGraphAgent(BaseAgent):
    _write_buffer: list[KnowledgeUpdateRequest] = []
    _last_flush: datetime = datetime.now(timezone.utc)

    FLUSH_INTERVAL_SECONDS = 60
    FLUSH_BATCH_SIZE = KG_WRITE_BUFFER_BATCH_SIZE  # 50

    async def _maybe_flush(self) -> None:
        age = (datetime.now(timezone.utc) - self._last_flush).total_seconds()
        if len(self._write_buffer) >= self.FLUSH_BATCH_SIZE or age > self.FLUSH_INTERVAL_SECONDS:
            await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Deduplicate, validate, write batch to NetworkX + SQLite."""
        unique = {req.dedup_key: req for req in self._write_buffer}
        for req in unique.values():
            if not await self._is_duplicate(req):
                self._graph.add_edge(
                    req.entity_id,
                    [r["target_id"] for r in req.relations],
                    attr=req.attributes,
                )
                await self._persist_edge(req)
        self._write_buffer.clear()
        self._last_flush = datetime.now(timezone.utc)
```

---

## 5. GraphRAG Traversal Pattern

```python
async def graph_rag_retrieve(self, seed_entities: list[str], k_hops: int = 2) -> list[str]:
    """
    GraphRAG: start from seed entities, traverse k hops, return all node IDs.
    These node IDs are then used to fetch embeddings from ChromaDB.
    """
    visited = set(seed_entities)
    frontier = set(seed_entities)

    for hop in range(k_hops):
        neighbors = set()
        for node in frontier:
            if self._graph.has_node(node):
                neighbors.update(self._graph.neighbors(node))
        new_nodes = neighbors - visited
        visited.update(new_nodes)
        frontier = new_nodes

    # Filter by confidence and recency
    confident_nodes = [
        n for n in visited
        if self._graph.nodes[n].get("confidence", 0) >= HALLUCINATION_FLOOR
        and self._is_recent(n, days=90)
    ]

    # Fetch embeddings for confident nodes
    return await self._chroma.get(
        ids=list(confident_nodes),
        include=["embeddings", "documents", "metadatas"]
    )
```

---

## 6. Entity Linking (Cross-Source Dedup)

```python
# Problem: "Tata Steel" in NewsAPI and "TATA STEEL LTD" in sanctions list
# Solution: Normalize + fuzzy match → merge to canonical ID

ENTITY_NORMALIZATION = {
    "remove_legal_suffixes": [" Ltd", " Limited", " Corp", " Inc", " LLC", " Pvt"],
    "lowercase": True,
    "remove_punctuation": True,
    "normalize_unicode": True,  # Hindi → romanized
}

ENTITY_MERGE_THRESHOLD = 0.85   # Fuzzy similarity → treat as same entity
```

---

## 7. KG Health Metrics

```python
# Monitor these in HealthCheckAgent
KG_HEALTH_METRICS = {
    "total_nodes":              "Target > 10_000 after Phase 3",
    "total_edges":              "Target > 50_000 after Phase 3",
    "avg_confidence":           "Target > 0.75",
    "stale_nodes_pct":          "Flag if > 20% nodes older than 30 days",
    "dedup_collision_rate":     "Expected 5-15% (normal for news sources)",
    "write_buffer_age_seconds": "Alert if > 300 (5 min without flush)",
    "orphan_nodes":             "Alert if > 5% (nodes with no edges)",
}
```

---

## 8. KG Implementation Checklist

- [ ] NetworkX DiGraph (directed) — not undirected Graph
- [ ] All edges have `dedup_key`, `confidence`, `created_at`
- [ ] `KG_WRITE_BUFFER_BATCH_SIZE = 50` flush respected
- [ ] `KG_DEDUP_WINDOW_SECONDS = 3600` dedup window applied
- [ ] GraphRAG traversal filters by confidence >= HALLUCINATION_FLOOR
- [ ] Entity normalization applied before dedup key creation
- [ ] `KnowledgeGraphAgent` is only writer (single-writer rule)
- [ ] Test: batch of 100 updates → exactly 50 flushed at batch size
- [ ] Test: duplicate edge within 1-hour window → only 1 edge written
- [ ] Test: k-hop traversal returns correct neighbor set

---

## Related Skills
- `rag-architect` — GraphRAG integration with ChromaDB embeddings
- `agent-designer` — KnowledgeGraphAgent BaseAgent patterns
- `supply-chain-analyst` — Supplier entities written to KG
- `india-intel` — India-specific entities (states, districts, ports)

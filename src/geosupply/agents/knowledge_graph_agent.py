"""
KnowledgeGraphAgent - Phase 7
FA v2 | Part VI | Layer 3

Maintains an in-memory knowledge graph of geopolitical entities and
their relationships. Implements FA v1 G5:
    - Dedup key = (entity_source, entity_target, relation_type)
    - Write-buffer batching (KG_WRITE_BUFFER_BATCH_SIZE = 50)
    - 1-hour sliding dedup window (KG_DEDUP_WINDOW_SECONDS = 3600)
    - Canary sampling (KG_CANARY_SAMPLE_SIZE = 10) for quality checks

Capabilities: KG_BUILD, KG_QUERY, KG_DEDUP, KG_STATS
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from geosupply.config import (
    AgentState,
    KG_CANARY_SAMPLE_SIZE,
    KG_DEDUP_WINDOW_SECONDS,
    KG_WRITE_BUFFER_BATCH_SIZE,
)
from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class KGTriple:
    """An (entity_source, relation_type, entity_target) triple."""

    __slots__ = ("source", "relation", "target", "weight", "timestamp")

    def __init__(
        self,
        source: str,
        relation: str,
        target: str,
        weight: float = 1.0,
    ) -> None:
        self.source = source
        self.relation = relation
        self.target = target
        self.weight = weight
        self.timestamp = datetime.now(timezone.utc)

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """FA v1 G5: dedup key = (source, target, relation)."""
        return (self.source.lower(), self.target.lower(), self.relation.upper())

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat(),
        }


class KnowledgeGraphAgent(BaseAgent):
    """
    In-memory knowledge graph with write-buffer, dedup window, and
    canary sampling (FA v1 G5).

    The graph is stored as an adjacency dict:
        _graph[source][target] = {relation: weight}

    Task types handled (via execute()):
        KG_ADD_TRIPLE  → add a (source, relation, target, weight) triple
        KG_QUERY       → query neighbours of an entity
        KG_STATS       → return graph statistics
        KG_FLUSH       → force flush write buffer
        KG_CANARY      → return canary sample of recent triples
    """

    name = "KnowledgeGraphAgent"
    domain = "intelligence"
    capabilities = {"KG_BUILD", "KG_QUERY", "KG_DEDUP", "KG_STATS"}
    max_concurrent = 1   # single-writer invariant (FA v1 G5)

    def __init__(self) -> None:
        # Graph storage: source → target → relation → weight
        self._graph: dict[str, dict[str, dict[str, float]]] = {}
        # Write buffer (G5)
        self._write_buffer: list[KGTriple] = []
        # Dedup window: dedup_key → timestamp
        self._dedup_window: dict[tuple[str, str, str], datetime] = {}
        # Canary: last N triples added
        self._canary: deque[KGTriple] = deque(maxlen=KG_CANARY_SAMPLE_SIZE)
        # Stats
        self._total_added = 0
        self._total_deduped = 0

    # ── Write path ────────────────────────────────────────────────────────────

    def _is_duplicate(self, triple: KGTriple) -> bool:
        """FA v1 G5: check dedup window (sliding 1-hour window)."""
        key = triple.dedup_key
        now = datetime.now(timezone.utc)
        last = self._dedup_window.get(key)
        if last is None:
            return False
        age = (now - last).total_seconds()
        return age < KG_DEDUP_WINDOW_SECONDS

    def _write_triple(self, triple: KGTriple) -> bool:
        """Write a triple to the graph. Returns True if written, False if deduped."""
        if self._is_duplicate(triple):
            self._total_deduped += 1
            return False

        src = triple.source.lower()
        tgt = triple.target.lower()
        rel = triple.relation.upper()

        self._graph.setdefault(src, {}).setdefault(tgt, {})[rel] = triple.weight
        self._dedup_window[triple.dedup_key] = triple.timestamp
        self._canary.append(triple)
        self._total_added += 1
        return True

    def _flush_buffer(self) -> int:
        """Flush write buffer to graph. Returns count of triples written."""
        written = 0
        for triple in self._write_buffer:
            if self._write_triple(triple):
                written += 1
        self._write_buffer.clear()
        logger.debug("%s: flushed %d triples to graph", self.name, written)
        return written

    def _buffer_or_flush(self, triple: KGTriple) -> int:
        """Add to buffer; flush when batch size reached."""
        self._write_buffer.append(triple)
        if len(self._write_buffer) >= KG_WRITE_BUFFER_BATCH_SIZE:
            return self._flush_buffer()
        return 0

    # ── Query path ────────────────────────────────────────────────────────────

    def _query_neighbours(self, entity: str, relation_filter: str | None = None) -> list[dict]:
        """Return all neighbours of an entity, optionally filtered by relation."""
        entity_lower = entity.lower()
        targets = self._graph.get(entity_lower, {})
        results: list[dict] = []
        for target, relations in targets.items():
            for rel, weight in relations.items():
                if relation_filter and rel != relation_filter.upper():
                    continue
                results.append({
                    "source": entity_lower,
                    "relation": rel,
                    "target": target,
                    "weight": weight,
                })
        return results

    def _stats(self) -> dict:
        node_count = len(self._graph)
        edge_count = sum(
            len(rels)
            for targets in self._graph.values()
            for rels in targets.values()
        )
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "buffer_depth": len(self._write_buffer),
            "total_added": self._total_added,
            "total_deduped": self._total_deduped,
            "canary_size": len(self._canary),
            "dedup_window_size": len(self._dedup_window),
        }

    # ── BaseAgent interface ────────────────────────────────────────────────────

    async def execute(self, task: dict) -> dict:
        task_type = task.get("task_type", "KG_STATS")
        trace_id = task.get("trace_id", "unknown")

        if task_type == "KG_ADD_TRIPLE":
            source = str(task.get("source", "")).strip()
            relation = str(task.get("relation", "RELATED")).strip()
            target = str(task.get("target", "")).strip()
            weight = float(task.get("weight", 1.0))

            if not source or not target:
                return {
                    "result": {"status": "error", "reason": "source and target required"},
                    "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
                }

            triple = KGTriple(source=source, relation=relation, target=target, weight=weight)
            flushed = self._buffer_or_flush(triple)

            return {
                "result": {
                    "status": "buffered",
                    "buffer_depth": len(self._write_buffer),
                    "flushed_count": flushed,
                    "dedup_key": list(triple.dedup_key),
                },
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        elif task_type == "KG_QUERY":
            entity = str(task.get("entity", "")).strip()
            relation_filter = task.get("relation_filter")
            neighbours = self._query_neighbours(entity, relation_filter)
            return {
                "result": {"entity": entity, "neighbours": neighbours, "count": len(neighbours)},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        elif task_type == "KG_FLUSH":
            written = self._flush_buffer()
            return {
                "result": {"flushed": written, **self._stats()},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        elif task_type == "KG_CANARY":
            sample = [t.to_dict() for t in self._canary]
            return {
                "result": {"canary_sample": sample, "sample_size": len(sample)},
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        else:  # KG_STATS or unknown
            return {
                "result": self._stats(),
                "meta": {"agent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

    def __repr__(self) -> str:
        stats = self._stats()
        return (
            f"<KnowledgeGraphAgent nodes={stats['node_count']} "
            f"edges={stats['edge_count']} buffer={stats['buffer_depth']}>"
        )

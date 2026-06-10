"""
GeoSupply AI — Live OSINT Knowledge Graph.

Entity co-occurrence graph built from the live wire: countries, chokepoints
and ports that are reported together form weighted `co_reported` edges.
Weights are reinforced on every observation and decay each cycle, so the
graph always reflects the *current* geopolitical narrative, not history.

Follows the swarm KG conventions: G5 dedup key = (source, target, relation),
sorted node pair so A→B and B→A merge. Pure CPU — cost_inr = 0.
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations

from geosupply.osint.models import KGEdge, NewsItem

DECAY_PER_CYCLE = 0.92        # ~50% weight after 8 quiet cycles
PRUNE_BELOW = 0.15            # forget edges that decayed to noise
MAX_CONTEXTS = 3


class OsintKnowledgeGraph:
    """In-memory co-occurrence KG over tagged wire headlines."""

    def __init__(self) -> None:
        self._edges: dict[tuple[str, str, str], KGEdge] = {}

    # ── properties ────────────────────────────────────────────────────
    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def node_count(self) -> int:
        nodes: set[str] = set()
        for src, tgt, _ in self._edges:
            nodes.add(src)
            nodes.add(tgt)
        return len(nodes)

    # ── ingestion ─────────────────────────────────────────────────────
    def observe(self, news: list[NewsItem]) -> int:
        """
        Reinforce edges from entity co-occurrence in headlines.
        Higher-priority headlines reinforce harder. Returns edges touched.
        """
        touched = 0
        now = datetime.now(timezone.utc)
        for item in news:
            ents = sorted(set(item.entities))
            if len(ents) < 2:
                continue
            boost = 1.0 + 0.5 * item.priority
            for a, b in combinations(ents, 2):
                key = (a, b, "co_reported")
                edge = self._edges.get(key)
                if edge is None:
                    edge = KGEdge(source=a, target=b, weight=0.0)
                    self._edges[key] = edge
                edge.weight = round(edge.weight + boost, 3)
                edge.observations += 1
                edge.last_seen = now
                if item.title not in edge.contexts:
                    edge.contexts = (edge.contexts + [item.title])[-MAX_CONTEXTS:]
                touched += 1
        return touched

    def decay(self) -> int:
        """Apply per-cycle decay; prune edges below the noise floor."""
        dead = []
        for key, edge in self._edges.items():
            edge.weight = round(edge.weight * DECAY_PER_CYCLE, 3)
            if edge.weight < PRUNE_BELOW:
                dead.append(key)
        for key in dead:
            del self._edges[key]
        return len(dead)

    # ── queries ───────────────────────────────────────────────────────
    def top_edges(self, limit: int = 15) -> list[KGEdge]:
        return sorted(self._edges.values(), key=lambda e: e.weight, reverse=True)[:limit]

    def neighbors(self, entity: str) -> list[tuple[str, float]]:
        """Entities most strongly linked to `entity`, by current weight."""
        out: dict[str, float] = {}
        for (a, b, _), edge in self._edges.items():
            if a == entity:
                out[b] = out.get(b, 0.0) + edge.weight
            elif b == entity:
                out[a] = out.get(a, 0.0) + edge.weight
        return sorted(out.items(), key=lambda kv: kv[1], reverse=True)

    def edges_for(self, entity: str) -> list[KGEdge]:
        return [e for (a, b, _), e in self._edges.items() if entity in (a, b)]

    # ── persistence (state survives restarts — autonomous loop) ──────
    def to_state(self) -> list[dict]:
        return [e.model_dump(mode="json") for e in self._edges.values()]

    def load_state(self, state: list[dict]) -> None:
        for row in state:
            try:
                edge = KGEdge(**row)
            except (TypeError, ValueError):
                continue
            self._edges[edge.dedup_key] = edge

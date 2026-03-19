"""
SourceClusterSubAgent — Layer 4 SubAgent
FA v2 | Part III | v10 New SubAgents

Detects coordinated source networks by clustering sources across
multiple dimensions: domain, style similarity, and penalty history.

Fixes: v9 GAP 3 — SourceFeedbackSubAgent couldn't detect source clusters.

CLUSTERING DIMENSIONS:
    1. Domain / subdomain match (exact)
    2. Style marker overlap (cosine-approximated via set intersection)
    3. Shared penalty flag (both sources have been flagged)

OUTPUT:
    cluster_id → [source_names]
    Sources in the same cluster share penalty escalation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_subagent import BaseSubAgent

logger = logging.getLogger(__name__)

# Minimum style-marker overlap fraction to consider two sources same cluster
STYLE_CLUSTER_THRESHOLD: float = 0.50


def _extract_domain(source_id: str) -> str:
    """Extract root domain from source identifier (e.g. 'src:thehindu.com' → 'thehindu.com')."""
    clean = source_id.lower()
    if clean.startswith("src:"):
        clean = clean[4:]
    # Strip subdomain: take last two parts
    parts = clean.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else clean


def _style_overlap(markers_a: list[str], markers_b: list[str]) -> float:
    """Jaccard similarity between two style-marker lists."""
    if not markers_a or not markers_b:
        return 0.0
    a, b = set(markers_a), set(markers_b)
    return len(a & b) / len(a | b)


def _cluster_sources(
    sources: list[dict],
) -> dict[str, list[str]]:
    """
    Union-Find clustering across domain + style + penalty dimensions.

    Each source dict has keys:
        source_id   str          — canonical source ID
        domain      str          — optional; extracted from source_id if absent
        style_markers list[str]  — optional
        is_flagged  bool         — optional

    Returns cluster_id (representative source_id) → [source_ids].
    """
    n = len(sources)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            si, sj = sources[i], sources[j]
            di = si.get("domain") or _extract_domain(si["source_id"])
            dj = sj.get("domain") or _extract_domain(sj["source_id"])

            # Dimension 1: same root domain
            if di == dj and di:
                union(i, j)
                continue

            # Dimension 2: style marker overlap
            overlap = _style_overlap(
                si.get("style_markers", []),
                sj.get("style_markers", []),
            )
            if overlap >= STYLE_CLUSTER_THRESHOLD:
                union(i, j)
                continue

            # Dimension 3: both permanently flagged
            if si.get("is_flagged") and sj.get("is_flagged"):
                union(i, j)

    # Build cluster map
    clusters: dict[int, list[str]] = {}
    for i, src in enumerate(sources):
        root = find(i)
        clusters.setdefault(root, []).append(src["source_id"])

    # Use smallest source_id as cluster key
    return {sources[root]["source_id"]: members for root, members in clusters.items()}


class SourceClusterSubAgent(BaseSubAgent):
    """
    Detects coordinated source networks across domain, style, and penalty data.

    PIPELINE:
        validate_input → cluster_sources → apply_penalties → build_report

    USAGE:
        result = await subagent.run({
            "sources": [
                {"source_id": "src:thehindu.com", "style_markers": ["formal", "political"]},
                {"source_id": "src:ndtv.com", "style_markers": ["formal", "political"]},
            ],
            "trace_id": "sc-001",
        })
    """

    name = "SourceClusterSubAgent"
    pipeline_steps = ["validate_input", "cluster_sources", "apply_penalties", "build_report"]

    def __init__(self) -> None:
        self._total_runs: int = 0
        self._total_clusters_found: int = 0

    async def run(self, input_data: dict) -> dict:
        """
        Cluster sources and identify coordinated networks.

        Input:
            sources    list[dict]  — source objects (source_id required)
            propagate_penalty bool — if True, flag entire cluster when any member flagged
            trace_id   str

        Output:
            clusters        dict  — cluster_id → [source_ids]
            flagged_clusters list — cluster_ids where penalty should propagate
            singleton_count int   — sources with no cluster partner
        """
        trace_id = input_data.get("trace_id", "unknown")
        sources: list[dict] = input_data.get("sources", [])
        propagate = input_data.get("propagate_penalty", False)

        if not sources:
            return {
                "result": {"clusters": {}, "flagged_clusters": [], "singleton_count": 0},
                "meta": {"subagent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        # Validate — require source_id
        valid = [s for s in sources if s.get("source_id")]
        if not valid:
            return {
                "result": {"error": "No sources with source_id provided"},
                "meta": {"subagent": self.name, "cost_inr": 0.0, "trace_id": trace_id},
            }

        clusters = _cluster_sources(valid)

        # Identify clusters with at least one flagged source
        flagged_clusters: list[str] = []
        if propagate:
            for cluster_id, members in clusters.items():
                source_map = {s["source_id"]: s for s in valid}
                if any(source_map.get(m, {}).get("is_flagged") for m in members):
                    flagged_clusters.append(cluster_id)

        singleton_count = sum(1 for members in clusters.values() if len(members) == 1)
        multi_source_count = len(clusters) - singleton_count

        self._total_runs += 1
        self._total_clusters_found += multi_source_count

        if multi_source_count > 0:
            logger.warning(
                "%s: found %d multi-source clusters [trace=%s]",
                self.name, multi_source_count, trace_id,
            )

        return {
            "result": {
                "clusters": clusters,
                "cluster_count": len(clusters),
                "multi_source_clusters": multi_source_count,
                "singleton_count": singleton_count,
                "flagged_clusters": flagged_clusters,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

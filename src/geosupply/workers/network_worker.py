"""NetworkWorker - Tier-2 narrative network analysis and cluster detection."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

# Relationship signal patterns (entity_a) → relation → (entity_b)
_RELATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(ally|allied|alliance|partner|cooperat)\b", re.I), "ALLY"),
    (re.compile(r"\b(enemy|adversar|hostile|oppos|sanction)\b", re.I), "ADVERSARY"),
    (re.compile(r"\b(trade|export\w*|import\w*|supply|ship\w*)\b", re.I), "TRADE"),
    (re.compile(r"\b(invest|fund|financ|loan|aid)\b", re.I), "FINANCIAL"),
    (re.compile(r"\b(attack|strike|bomb|invad|conflict|war)\b", re.I), "CONFLICT"),
    (re.compile(r"\b(negotiat|talk|diplomac|deal|agreement|treaty)\b", re.I), "DIPLOMATIC"),
]

_GPE_TERMS = {
    "india", "china", "russia", "ukraine", "pakistan",
    "usa", "united states", "iran", "israel", "taiwan",
    "saudi arabia", "turkey", "europe", "nato",
}


def _extract_entities(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for term in _GPE_TERMS:
        if term in lower:
            found.append(term.title())
    # Also grab capitalised phrases (rough NER)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text):
        name = m.group(1)
        if name not in found and len(name) > 3:
            found.append(name)
    return list(dict.fromkeys(found))[:10]   # dedup, cap at 10


def _detect_relations(text: str) -> list[str]:
    relations = []
    for pattern, label in _RELATION_PATTERNS:
        if pattern.search(text):
            relations.append(label)
    return relations


def _build_clusters(entities: list[str], relations: list[str]) -> list[dict]:
    """Group entities into clusters by dominant relation type."""
    if not entities:
        return []
    dominant = relations[0] if relations else "UNKNOWN"
    return [{"entities": entities, "relation_type": dominant, "size": len(entities)}]


class NetworkWorker(BaseWorker):
    """
    Build a lightweight narrative network from text: extract entities,
    detect relationship types, and produce cluster summary.

    Input fields:
        text (str): News or intelligence text.
        sanitised_text (str, optional): Pre-sanitised text (preferred).
    """

    name = "NetworkWorker"
    tier = 2
    use_static = False
    capabilities = {"NARRATIVE_NETWORK", "CLUSTER"}
    max_retries = 2
    timeout_seconds = 30

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("sanitised_text") or input_data.get("text")

        if not isinstance(text, str) or not text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'text' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        entities = _extract_entities(text)
        relations = _detect_relations(text)
        clusters = _build_clusters(entities, relations)

        # Edge list: every entity-pair + dominant relation
        edges: list[dict] = []
        dominant = relations[0] if relations else "UNKNOWN"
        for i, a in enumerate(entities):
            for b in entities[i + 1:]:
                edges.append({"source": a, "target": b, "relation": dominant})

        return {
            "result": {
                "entities": entities,
                "relations": relations,
                "clusters": clusters,
                "edges": edges[:20],          # cap output size
                "node_count": len(entities),
                "edge_count": len(edges),
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

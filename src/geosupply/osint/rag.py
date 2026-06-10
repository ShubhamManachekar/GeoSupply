"""
GeoSupply AI — Agentic RAG over the live OSINT snapshot.

Mirrors the v8 fixed RAG sequence, deterministically and at ₹0:

  STEP 1  PLAN       decompose the query into entity/topic sub-queries
  STEP 2  RETRIEVE   parallel lexical retrieval per sub-query over the
                     wire, map events and structured panels
  STEP 3  EXPAND     knowledge-graph hop: pull items about entities the
                     KG links to the queried entities (multi-hop context)
  STEP 4  FUSE       reciprocal-rank fusion + dedup across result sets
  STEP 5  SYNTHESISE extractive answer with inline citations + confidence

No LLM on this path (infrastructure stays off the critical DAG); a Tier-3
swarm escalation can be layered on top later. Pure CPU — cost_inr = 0.
"""
from __future__ import annotations

import re

from geosupply.osint.knowledge_graph import OsintKnowledgeGraph
from geosupply.osint.models import IntelAnswer, IntelCitation, OsintSnapshot
from geosupply.osint.registry import CHOKEPOINTS, COUNTRY_GAZETTEER

_STOPWORDS = frozenset(
    "the a an is are was were be been being what which who whom whose when "
    "where why how do does did has have had of in on at to from for with "
    "about and or not no any all there their it its this that these those "
    "latest current today now status update tell me show give".split()
)

_TOPIC_SYNONYMS: dict[str, list[str]] = {
    "risk": ["risk", "tension", "conflict", "escalation", "threat"],
    "shipping": ["shipping", "maritime", "vessel", "tanker", "freight", "port"],
    "trade": ["trade", "tariff", "export", "import", "sanctions", "embargo"],
    "energy": ["oil", "crude", "gas", "energy", "opec", "brent"],
    "weather": ["monsoon", "cyclone", "storm", "rain", "flood", "weather"],
}


def _extract_entities(query: str) -> list[str]:
    low = f" {query.lower()} "
    found: list[str] = []
    for _, (name, aliases) in COUNTRY_GAZETTEER.items():
        if any(alias in low for alias in aliases):
            found.append(name)
    for cp in CHOKEPOINTS:
        if cp["name"].lower() in low or cp["id"] in low:
            found.append(cp["name"])
    return found


def _keywords(query: str) -> list[str]:
    words = re.findall(r"[a-z][a-z'-]+", query.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def plan(query: str, kg: OsintKnowledgeGraph | None = None) -> tuple[list[str], list[str]]:
    """STEP 1+3: sub-queries from entities/topics, expanded one KG hop."""
    entities = _extract_entities(query)
    keywords = _keywords(query)

    sub_queries: list[str] = []
    for ent in entities:
        sub_queries.append(ent.lower())
    for topic, synonyms in _TOPIC_SYNONYMS.items():
        if any(kw in synonyms or kw == topic for kw in keywords):
            sub_queries.append(topic)
    # KG expansion: strongest neighbour of each queried entity
    if kg is not None:
        for ent in list(entities):
            for neighbor, _ in kg.neighbors(ent)[:2]:
                if neighbor not in entities:
                    entities.append(neighbor)
                    sub_queries.append(neighbor.lower())
    if not sub_queries:
        sub_queries = keywords[:5] or [query.lower()]
    return sub_queries, entities


def _score(text: str, terms: list[str]) -> float:
    low = text.lower()
    hits = sum(1 for t in terms if t in low)
    return hits / len(terms) if terms else 0.0


def retrieve(snapshot: OsintSnapshot, sub_queries: list[str],
             entities: list[str]) -> list[IntelCitation]:
    """STEP 2+4: per-sub-query retrieval, fused with reciprocal-rank fusion."""
    rrf: dict[str, float] = {}
    pool: dict[str, IntelCitation] = {}

    def consider(key: str, citation: IntelCitation, rank: int) -> None:
        rrf[key] = rrf.get(key, 0.0) + 1.0 / (10 + rank)
        if key not in pool or citation.score > pool[key].score:
            pool[key] = citation

    for sq in sub_queries:
        terms = [sq] + _TOPIC_SYNONYMS.get(sq, [])
        ranked: list[tuple[float, str, IntelCitation]] = []
        for n in snapshot.news:
            s = _score(n.title, terms)
            if any(e in n.entities for e in entities):
                s += 0.5
            if s > 0:
                ranked.append((s, f"news:{n.id}", IntelCitation(
                    kind="news", text=n.title, source=n.source, url=n.url, score=s)))
        for e in snapshot.events:
            s = _score(e.title, terms)
            if s > 0:
                ranked.append((s, f"event:{e.id}", IntelCitation(
                    kind="event", text=e.title, source=e.source, url=e.url, score=s)))
        ranked.sort(key=lambda r: r[0], reverse=True)
        for rank, (s, key, cit) in enumerate(ranked[:8]):
            consider(key, cit, rank)

    # structured panels keyed by entity
    for r in snapshot.country_risk:
        if r.name in entities:
            consider(f"risk:{r.iso2}", IntelCitation(
                kind="risk", source="Risk Index", score=1.0,
                text=(f"{r.name} risk {r.score:.0f}/100 ({r.trend}, "
                      f"{r.mentions} signals, CI {r.ci_low:.0f}–{r.ci_high:.0f}, "
                      f"drivers: {', '.join(r.drivers) or 'n/a'})")), 0)
    for c in snapshot.chokepoints:
        if c.name in entities:
            consider(f"choke:{c.id}", IntelCitation(
                kind="chokepoint", source="Chokepoint Monitor", score=1.0,
                text=(f"{c.name} stress {c.stress_index:.0%} ({c.level}, {c.trend}, "
                      f"{c.recent_events} nearby events)")), 0)
    for p in snapshot.india_ports:
        if any(e.lower() in p.name.lower() for e in entities) or "India" in entities:
            consider(f"port:{p.name}", IntelCitation(
                kind="port", source="India Ports", score=0.8,
                text=f"{p.name} port {p.status}, monsoon {p.monsoon_risk}"), 2)

    fused = sorted(pool.items(), key=lambda kv: rrf[kv[0]], reverse=True)
    return [cit for _, cit in fused[:10]]


def synthesize(query: str, sub_queries: list[str], entities: list[str],
               citations: list[IntelCitation]) -> IntelAnswer:
    """STEP 5: extractive synthesis with explicit epistemic confidence."""
    if not citations:
        return IntelAnswer(
            query=query, sub_queries=sub_queries, entities=entities,
            answer="No live signals match this query in the current window. "
                   "The monitored wire has no relevant reporting right now.",
            confidence=0.0,
        )
    structured = [c for c in citations if c.kind in ("risk", "chokepoint", "port")]
    wire = [c for c in citations if c.kind in ("news", "event")]
    lines: list[str] = []
    if structured:
        lines.append("Current assessment: " + " ".join(c.text + "." for c in structured[:3]))
    if wire:
        lines.append("Live reporting: " + " ".join(
            f"{c.text} [{c.source}]." for c in wire[:4]))
    confidence = round(min(1.0, 0.25 + 0.12 * len(citations)
                           + (0.15 if structured else 0.0)), 2)
    return IntelAnswer(
        query=query, sub_queries=sub_queries, entities=entities,
        answer=" ".join(lines), citations=citations, confidence=confidence,
    )


def answer_query(query: str, snapshot: OsintSnapshot,
                 kg: OsintKnowledgeGraph | None = None) -> IntelAnswer:
    """Full agentic pipeline: plan → retrieve → expand → fuse → synthesise."""
    sub_queries, entities = plan(query, kg)
    citations = retrieve(snapshot, sub_queries, entities)
    return synthesize(query, sub_queries, entities, citations)

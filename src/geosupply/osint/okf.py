"""
GeoSupply AI — Open Knowledge Format (OKF 0.1) knowledge engine.

Replaces chunk-retrieval RAG on the /osint/ask path with the OKF pattern
(github.com/GoogleCloudPlatform/knowledge-catalog): every refresh cycle the
live snapshot is compiled into a *knowledge bundle* — markdown concept
documents with YAML frontmatter — and questions are answered by loading the
matched concept documents whole, not by scoring text chunks.

Bundle layout (spec §4-§7):
    index.md                  okf_version + directory listing (no other fm)
    log.md                    ISO-8601 dated update history
    concepts/global-risk.md   type: risk-index
    concepts/chokepoints.md   type: chokepoint-monitor
    concepts/war-zones.md     type: warzone-monitor
    concepts/india-ports.md   type: port-status
    concepts/markets.md       type: market-watch
    concepts/wire.md          type: news-wire
    concepts/countries/<iso2>.md   type: country-risk (top risks)

Every concept carries the recommended fields (title, description, tags,
timestamp) plus producer-specific ones (confidence, sources). Cross-links
are standard markdown links → untyped directed edges (spec §5).

The RagFeedback learner still applies: learned per-source weights decide
which wire facts are prominent inside concept documents, so the feedback
loop survives the format change. Pure CPU — cost_inr = 0.
"""
from __future__ import annotations

from datetime import datetime, timezone

from geosupply.osint.knowledge_graph import OsintKnowledgeGraph
from geosupply.osint.models import IntelAnswer, IntelCitation, OsintSnapshot
from geosupply.osint.rag import plan  # entity/topic routing is reused for doc selection

OKF_VERSION = "0.1"
MAX_COUNTRY_DOCS = 8
MAX_WIRE_FACTS = 25


# ── frontmatter ──────────────────────────────────────────────────────
def _fm(fields: dict) -> str:
    """Serialise a flat dict to a YAML frontmatter block (spec §3)."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {v}" for v in value)
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_frontmatter(doc: str) -> dict:
    """Minimal parser for OKF frontmatter (conformance checks + routing).

    Fences are matched as standalone `---` LINES (a later horizontal rule
    in the body cannot terminate the block early or be mistaken for one).
    """
    lines_all = doc.splitlines()
    if not lines_all or lines_all[0].strip() != "---":
        return {}
    try:
        end = next(i for i, ln in enumerate(lines_all[1:], start=1)
                   if ln.strip() == "---")
    except StopIteration:
        return {}
    block = "\n".join(lines_all[1:end])
    fields: dict = {}
    current_list: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list:
            fields.setdefault(current_list, []).append(line[4:].strip())
        elif ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val:
                fields[key] = val.strip('"')
                current_list = None
            else:
                fields[key] = []
                current_list = key
    return fields


# ── bundle builder ───────────────────────────────────────────────────
def build_bundle(snapshot: OsintSnapshot, kg: OsintKnowledgeGraph | None = None,
                 source_weight=None) -> dict[str, str]:
    """Compile the live snapshot into an OKF 0.1 bundle (path → markdown)."""
    now = (snapshot.generated_at or datetime.now(timezone.utc)).isoformat()

    def w(src: str) -> float:
        return source_weight(src) if source_weight is not None else 1.0

    docs: dict[str, str] = {}

    # concepts/global-risk.md
    risk_lines = []
    for r in snapshot.country_risk:
        proj = f", projected {r.projected_score:.0f}" if r.projected_score is not None else ""
        risk_lines.append(
            f"- **{r.name}** ({r.iso2}): risk {r.score:.0f}/100 "
            f"[CI {r.ci_low:.0f}–{r.ci_high:.0f}, {r.data_density}] {r.trend}{proj}; "
            f"{r.mentions} signals; drivers: {', '.join(r.drivers) or 'n/a'}")
    docs["concepts/global-risk.md"] = _fm({
        "type": "risk-index", "title": "Global Risk Index",
        "description": "Live country risk scores with confidence intervals and projections",
        "tags": ["risk", "geopolitics"] + [r.name for r in snapshot.country_risk[:5]],
        "timestamp": now,
    }) + ("\n# Global Risk Index\n\nSee also [chokepoints](/concepts/chokepoints.md) "
          "and [war zones](/concepts/war-zones.md).\n\n## Key facts\n"
          + "\n".join(risk_lines or ["- No live risk signals this cycle."]) + "\n")

    # concepts/chokepoints.md
    cp_lines = [
        f"- **{c.name}**: stress {c.stress_index:.0%} ({c.level}, {c.trend}); "
        f"{c.recent_events} nearby events; ~{c.daily_transits} transits/day — {c.description}"
        for c in snapshot.chokepoints]
    docs["concepts/chokepoints.md"] = _fm({
        "type": "chokepoint-monitor", "title": "Maritime Chokepoint Monitor",
        "description": "Stress index for the 9 monitored maritime chokepoints",
        "tags": ["shipping", "maritime", "supply-chain"] + [c.name for c in snapshot.chokepoints[:4]],
        "timestamp": now,
    }) + "\n# Maritime Chokepoint Monitor\n\n## Key facts\n" + "\n".join(cp_lines or ["- No data."]) + "\n"

    # concepts/war-zones.md
    wz_lines = [
        f"- **{z.name}** ({z.kind.upper()}): intensity {z.intensity:.0%}, "
        f"{z.recent_events} events (24h) — {z.description}"
        for z in snapshot.war_zones]
    docs["concepts/war-zones.md"] = _fm({
        "type": "warzone-monitor", "title": "War Zones & Blockades",
        "description": "Active war, blockade and exclusion zones with live intensity",
        "tags": ["conflict", "war", "blockade"] + [z.name for z in snapshot.war_zones[:4]],
        "timestamp": now,
    }) + "\n# War Zones & Blockades\n\n## Key facts\n" + "\n".join(wz_lines or ["- No data."]) + "\n"

    # concepts/india-ports.md
    port_lines = [
        f"- **{p.name}** ({p.state}): {p.status}, monsoon {p.monsoon_risk}"
        + (f", 3-day rain {p.rain_3d_mm}mm" if p.rain_3d_mm is not None else "")
        + (f" — {p.note}" if p.note else "")
        for p in snapshot.india_ports]
    docs["concepts/india-ports.md"] = _fm({
        "type": "port-status", "title": "India Major Port Status",
        "description": "Operational status of India's 12 major ports (weather + monsoon)",
        "tags": ["India", "ports", "monsoon", "supply-chain"],
        "timestamp": now,
    }) + "\n# India Major Port Status\n\n## Key facts\n" + "\n".join(port_lines or ["- No data."]) + "\n"

    # concepts/markets.md
    mkt_lines = [
        f"- **{m.symbol}** ({m.name}): {m.value}"
        + (f" ({m.change_pct:+.2f}%)" if m.change_pct is not None else "")
        for m in snapshot.markets]
    docs["concepts/markets.md"] = _fm({
        "type": "market-watch", "title": "Market Watch",
        "description": "FX (INR focus), crypto and commodity quotes",
        "tags": ["markets", "INR", "oil", "fx"],
        "timestamp": now,
    }) + "\n# Market Watch\n\n## Key facts\n" + "\n".join(mkt_lines or ["- No data."]) + "\n"

    # concepts/wire.md — feedback-weighted headline facts
    ranked_news = sorted(
        snapshot.news, key=lambda n: (n.priority * w(n.source)), reverse=True)
    wire_lines = [
        f"- [{n.priority}] {n.title} — *{n.source}*"
        + (f" ({', '.join(n.entities)})" if n.entities else "")
        + (f" <{n.url}>" if n.url else "")
        for n in ranked_news[:MAX_WIRE_FACTS]]
    docs["concepts/wire.md"] = _fm({
        "type": "news-wire", "title": "Live Intelligence Wire",
        "description": "Priority-and-trust ranked live headlines with entity tags",
        "tags": ["news", "wire", "osint"],
        "timestamp": now,
    }) + "\n# Live Intelligence Wire\n\n## Key facts\n" + "\n".join(wire_lines or ["- Wire quiet."]) + "\n"

    # concepts/countries/<iso2>.md — top risks, KG-linked
    for r in snapshot.country_risk[:MAX_COUNTRY_DOCS]:
        related = [n for n, _ in (kg.neighbors(r.name)[:4] if kg else [])]
        headlines = [n for n in snapshot.news if r.name in n.entities][:6]
        body = [f"\n# {r.name} — Risk Assessment\n",
                f"Risk **{r.score:.0f}/100** (CI {r.ci_low:.0f}–{r.ci_high:.0f}, "
                f"{r.data_density} density, trend {r.trend}"
                + (f", projected {r.projected_score:.0f}" if r.projected_score is not None else "")
                + f"). Drivers: {', '.join(r.drivers) or 'n/a'}.\n",
                "Related: [Global Risk Index](/concepts/global-risk.md), "
                "[War Zones](/concepts/war-zones.md)"
                + (" — co-reported with " + ", ".join(related) if related else "") + ".\n",
                "## Key facts"]
        body += [f"- {n.title} — *{n.source}*" + (f" <{n.url}>" if n.url else "")
                 for n in headlines] or ["- No country-specific wire this cycle."]
        docs[f"concepts/countries/{r.iso2.lower()}.md"] = _fm({
            "type": "country-risk", "title": f"{r.name} Risk Assessment",
            "description": f"Live risk profile for {r.name}",
            "tags": [r.name, r.iso2] + r.drivers,
            "timestamp": now, "confidence": f"{r.ci_low:.0f}-{r.ci_high:.0f}",
        }) + "\n".join(body) + "\n"

    # index.md — only non-concept file allowed frontmatter (okf_version, §11)
    concept_paths = sorted(p for p in docs)
    index_lines = ["# GeoSupply OSINT Knowledge Bundle", "",
                   "Live geopolitical supply-chain knowledge, rebuilt every cycle.", "",
                   "## Concepts"]
    for path in concept_paths:
        meta = parse_frontmatter(docs[path])
        index_lines.append(f"* [{meta.get('title', path)}](/{path}) - {meta.get('description', '')}")
    docs["index.md"] = _fm({"okf_version": f'"{OKF_VERSION}"'}) + "\n".join(index_lines) + "\n"

    # log.md — dated update history (§7)
    docs["log.md"] = (f"# Log\n\n## {now[:10]}\n\n"
                      f"**Update**: bundle rebuilt from live snapshot at {now}; "
                      f"{len(concept_paths)} concepts.\n")
    return docs


# ── knowledge-first answering (replaces lexical RAG retrieval) ───────
_DOC_KIND = {"risk-index": "risk", "chokepoint-monitor": "chokepoint",
             "warzone-monitor": "event", "port-status": "port",
             "market-watch": "risk", "news-wire": "news", "country-risk": "risk"}


def select_concepts(query: str, bundle: dict[str, str],
                    kg: OsintKnowledgeGraph | None = None) -> list[str]:
    """Frontmatter-first routing: match query entities/terms to concept docs."""
    sub_queries, entities = plan(query, kg)
    terms = {t.lower() for t in sub_queries} | {e.lower() for e in entities}
    matched: list[tuple[int, str]] = []
    for path, doc in bundle.items():
        if path in ("index.md", "log.md"):
            continue
        meta = parse_frontmatter(doc)
        hay = " ".join([meta.get("title", ""), meta.get("description", ""),
                        str(meta.get("type", "")),
                        " ".join(meta.get("tags", []) if isinstance(meta.get("tags"), list) else [])]).lower()
        score = sum(1 for t in terms if t and t in hay)
        if score:
            matched.append((score, path))
    matched.sort(reverse=True)
    return [p for _, p in matched[:4]]


def answer_from_bundle(query: str, bundle: dict[str, str],
                       kg: OsintKnowledgeGraph | None = None) -> IntelAnswer:
    """
    OKF answering: load the matched concept documents *whole* and compose
    from their `## Key facts` sections — no chunk scoring, no reranking.
    """
    sub_queries, entities = plan(query, kg)
    paths = select_concepts(query, bundle, kg)
    if not paths:
        return IntelAnswer(
            query=query, sub_queries=sub_queries, entities=entities,
            answer="No knowledge concepts match this query in the current "
                   "bundle. The monitored domains have no relevant knowledge right now.",
            confidence=0.0)

    citations: list[IntelCitation] = []
    lines: list[str] = []
    terms = [t.lower() for t in sub_queries] + [e.lower() for e in entities]
    for path in paths:
        doc = bundle[path]
        meta = parse_frontmatter(doc)
        kind = _DOC_KIND.get(str(meta.get("type", "")), "news")
        # Only bullets under "## Key facts" are facts — other bulleted
        # sections (links, indexes) must not leak into citations.
        facts: list[str] = []
        in_facts = False
        for ln in doc.splitlines():
            if ln.startswith("## "):
                in_facts = ln.strip().lower() == "## key facts"
            elif in_facts and ln.startswith("- "):
                facts.append(ln[2:].strip())
        relevant = [f for f in facts if any(t in f.lower() for t in terms)] or facts[:2]
        for fact in relevant[:3]:
            url = ""
            if "<http" in fact:
                fact, _, tail = fact.partition("<")
                url = tail.rstrip(">").strip()
            citations.append(IntelCitation(
                kind=kind, text=fact.strip().rstrip("—* "),
                source=str(meta.get("title", path)), url=url, score=1.0))
        lines.append(f"{meta.get('title', path)}: "
                     + " ".join(f.split(" — ")[0].strip("*") + "." for f in relevant[:2]))

    confidence = round(min(1.0, 0.3 + 0.15 * len(paths) + 0.03 * len(citations)), 2)
    return IntelAnswer(
        query=query, sub_queries=sub_queries, entities=entities,
        answer=" ".join(lines), citations=citations[:10], confidence=confidence)

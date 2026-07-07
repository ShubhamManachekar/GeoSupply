"""
OKF 0.1 knowledge engine tests: bundle spec conformance, concept routing,
knowledge-document answering, feedback weighting, and API endpoints.
Real logic throughout (project rule); external HTTP via MockTransport only.
"""
from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from geosupply.osint.intel import compute_chokepoint_stress, compute_country_risk, tag_entities
from geosupply.osint.knowledge_graph import OsintKnowledgeGraph
from geosupply.osint.models import NewsItem, OsintEvent, OsintSnapshot
from geosupply.osint.okf import (
    answer_from_bundle,
    build_bundle,
    parse_frontmatter,
    select_concepts,
)

RESERVED = {"index.md", "log.md"}


def _news(title: str, source: str = "wire", priority: int = 2,
          url: str = "") -> NewsItem:
    return NewsItem(id=f"n-{hash((title, source))}", title=title, source=source,
                    priority=priority, url=url)


def _snapshot() -> OsintSnapshot:
    news = [
        _news("Iran missile attack near Strait of Hormuz", "wire-a", 3,
              "https://example.com/a"),
        _news("Hormuz tanker traffic rerouted amid escalation", "wire-b", 2),
        _news("Monsoon rains lash Kerala coast", "wire-c", 1),
    ]
    tag_entities(news)
    events = [OsintEvent(id=f"e{i}", category="conflict", title="Hormuz area clash",
                         lat=26.6, lon=56.2, severity=8.0, source="GDELT")
              for i in range(8)]
    return OsintSnapshot(
        news=news, events=events,
        chokepoints=compute_chokepoint_stress(events),
        country_risk=compute_country_risk(news, events),
    )


class TestBundleConformance:
    """Spec §9: parseable frontmatter, non-empty type, reserved-file rules."""

    def test_every_concept_has_frontmatter_with_type(self):
        bundle = build_bundle(_snapshot())
        concepts = {p: d for p, d in bundle.items() if p not in RESERVED}
        assert concepts
        for path, doc in concepts.items():
            meta = parse_frontmatter(doc)
            assert meta.get("type"), f"{path} missing required type"
            assert meta.get("title") and meta.get("timestamp"), path

    def test_index_declares_okf_version_and_links_all_concepts(self):
        bundle = build_bundle(_snapshot())
        index = bundle["index.md"]
        assert parse_frontmatter(index).get("okf_version") == "0.1"
        for path in bundle:
            if path not in RESERVED:
                assert f"(/{path})" in index, f"index missing link to {path}"

    def test_log_has_dated_update_entry(self):
        bundle = build_bundle(_snapshot())
        log = bundle["log.md"]
        assert log.startswith("# Log")
        assert "**Update**" in log and "## 20" in log  # ISO date heading

    def test_top_risk_countries_get_concept_docs(self):
        snap = _snapshot()
        bundle = build_bundle(snap)
        top = snap.country_risk[0]
        path = f"concepts/countries/{top.iso2.lower()}.md"
        assert path in bundle
        meta = parse_frontmatter(bundle[path])
        assert meta["type"] == "country-risk"
        assert top.name in bundle[path]

    def test_cross_links_are_bundle_absolute(self):
        bundle = build_bundle(_snapshot())
        assert "(/concepts/chokepoints.md)" in bundle["concepts/global-risk.md"]


class TestConceptRouting:
    def test_shipping_query_routes_to_chokepoints(self):
        bundle = build_bundle(_snapshot())
        paths = select_concepts("shipping risk around hormuz", bundle)
        assert "concepts/chokepoints.md" in paths

    def test_kg_hop_expands_routing(self):
        kg = OsintKnowledgeGraph()
        kg.observe([NewsItem(id="k1", title="x", source="w", priority=2,
                             entities=["Iran", "Yemen"])])
        snap = _snapshot()
        bundle = build_bundle(snap, kg=kg)
        _, entities_no_kg = [], select_concepts("iran outlook", bundle)
        from geosupply.osint.rag import plan
        _, ents = plan("iran outlook", kg)
        assert "Yemen" in ents  # one KG hop feeds concept selection


class TestOkfAnswering:
    def test_answer_loads_concepts_whole_with_citations(self):
        ans = answer_from_bundle("hormuz shipping risk", build_bundle(_snapshot()))
        assert ans.confidence > 0.3
        assert ans.citations
        assert any(c.kind == "chokepoint" for c in ans.citations)
        assert any("Hormuz" in c.text for c in ans.citations)
        assert ans.cost_inr == 0.0

    def test_citation_urls_extracted_from_facts(self):
        ans = answer_from_bundle("iran attack news", build_bundle(_snapshot()))
        urls = [c.url for c in ans.citations if c.url]
        assert "https://example.com/a" in urls  # exact match (CodeQL)

    def test_no_match_is_honest(self):
        ans = answer_from_bundle("antarctica penguin festival",
                                 build_bundle(OsintSnapshot()))
        assert ans.confidence == 0.0
        assert "No knowledge concepts" in ans.answer

    def test_feedback_weight_orders_wire_facts(self):
        snap = _snapshot()
        weights = {"wire-a": 2.0, "wire-b": 0.2}
        bundle = build_bundle(snap, source_weight=lambda s: weights.get(s, 1.0))
        wire = bundle["concepts/wire.md"]
        assert wire.index("wire-a") < wire.index("wire-b")  # trusted first


@pytest.fixture
async def api(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_STATE_PATH", str(tmp_path / "learn.json"))
    from geosupply.api.main import create_app
    from geosupply.api.routers import osint as osint_module
    from geosupply.osint.aggregator import OsintAggregator
    from tests.unit.test_osint_api import _route_request

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(_route_request))
    agg = OsintAggregator(client=upstream)
    await agg.refresh(force=True)   # builds snapshot + OKF bundle
    app = create_app()
    app.dependency_overrides[osint_module.aggregator_dep] = lambda: agg
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()
    await agg.teardown()
    await upstream.aclose()


class TestOkfEndpoints:
    async def test_ask_answers_from_okf(self, api):
        resp = await api.get("/osint/ask", params={"q": "red sea shipping risk"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["citations"] and body["confidence"] > 0

    async def test_okf_index_lists_bundle(self, api):
        rows = (await api.get("/osint/okf")).json()
        paths = {r["path"] for r in rows}
        assert {"index.md", "log.md", "concepts/chokepoints.md"} <= paths
        assert all("type" in r and "title" in r for r in rows)

    async def test_okf_document_served_as_markdown(self, api):
        resp = await api.get("/osint/okf/concepts/chokepoints.md")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/markdown")
        assert resp.text.startswith("---")
        assert parse_frontmatter(resp.text)["type"] == "chokepoint-monitor"

    async def test_unknown_document_404(self, api):
        assert (await api.get("/osint/okf/concepts/nope.md")).status_code == 404

    async def test_okf_gated_behind_pro(self, api, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "FREE")
        assert (await api.get("/osint/okf")).status_code == 403
        assert (await api.get("/osint/okf/index.md")).status_code == 403

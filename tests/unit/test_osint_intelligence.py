"""
Intelligence-suite tests: knowledge graph, agentic RAG, bias handler,
self-improving projections, war zones. All real logic, no mocks.
"""
from __future__ import annotations

from geosupply.osint.bias import SourceBiasTracker
from geosupply.osint.intel import compute_war_zones, geo_circle
from geosupply.osint.knowledge_graph import OsintKnowledgeGraph
from geosupply.osint.models import NewsItem, OsintEvent, OsintSnapshot
from geosupply.osint.projection import RiskProjector
from geosupply.osint.rag import answer_query, plan


def _news(title: str, source: str = "wire", priority: int = 0,
          entities: list[str] | None = None) -> NewsItem:
    return NewsItem(id=f"n-{hash((title, source))}", title=title, source=source,
                    priority=priority, entities=entities or [])


def _ev(lat: float, lon: float, severity: float = 5.0,
        category: str = "conflict", title: str = "clash reported") -> OsintEvent:
    return OsintEvent(id=f"t-{lat}-{lon}-{title[:8]}", category=category,
                      title=title, lat=lat, lon=lon, severity=severity, source="test")


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------

class TestKnowledgeGraph:
    def test_cooccurrence_builds_weighted_edges(self):
        kg = OsintKnowledgeGraph()
        kg.observe([
            _news("India China border talks", priority=2, entities=["India", "China"]),
            _news("India China trade row", priority=0, entities=["India", "China"]),
        ])
        assert kg.edge_count == 1
        edge = kg.top_edges(1)[0]
        assert {edge.source, edge.target} == {"China", "India"}
        assert edge.observations == 2
        assert edge.weight == 3.0  # (1+0.5*2) + 1.0
        assert edge.dedup_key == ("China", "India", "co_reported")  # G5 sorted pair

    def test_single_entity_headlines_ignored(self):
        kg = OsintKnowledgeGraph()
        kg.observe([_news("India update", entities=["India"])])
        assert kg.edge_count == 0

    def test_decay_prunes_stale_edges(self):
        kg = OsintKnowledgeGraph()
        kg.observe([_news("a b", entities=["A", "B"])])
        for _ in range(30):
            kg.decay()
        assert kg.edge_count == 0  # decayed below noise floor and pruned

    def test_neighbors_ranked_by_weight(self):
        kg = OsintKnowledgeGraph()
        kg.observe([
            _news("india china clash", priority=3, entities=["India", "China"]),
            _news("india lanka ferry", priority=0, entities=["India", "Sri Lanka"]),
        ])
        neighbors = kg.neighbors("India")
        assert neighbors[0][0] == "China"

    def test_state_roundtrip(self):
        kg = OsintKnowledgeGraph()
        kg.observe([_news("x", entities=["India", "Iran"], priority=1)])
        kg2 = OsintKnowledgeGraph()
        kg2.load_state(kg.to_state())
        assert kg2.edge_count == 1
        assert kg2.top_edges(1)[0].weight == kg.top_edges(1)[0].weight


# ---------------------------------------------------------------------------
# Bias handler
# ---------------------------------------------------------------------------

class TestBiasHandler:
    def test_uncorroborated_flash_source_penalised(self):
        tracker = SourceBiasTracker()
        wire = [
            _news("Massive missile attack claim", "LoneWolf", 3, ["Iran"]),
            _news("Calm markets today", "SteadyWire", 0, []),
        ]
        profiles = tracker.analyze(wire)
        lone = next(p for p in profiles if p.source == "LoneWolf")
        assert lone.credibility < 0.5            # -0.05 penalty applied
        assert "UNCORROBORATED" in lone.bias_flags
        assert lone.sensationalism == 1.0

    def test_corroborated_source_recovers(self):
        tracker = SourceBiasTracker()
        wire = [
            _news("Missile attack on tanker", "A-Wire", 3, ["Yemen"]),
            _news("Tanker hit near coast, Yemen blamed", "B-Wire", 2, ["Yemen"]),
        ]
        profiles = tracker.analyze(wire)
        a = next(p for p in profiles if p.source == "A-Wire")
        assert a.corroboration_rate == 1.0
        assert a.credibility > 0.5               # +0.02 recovery

    def test_floor_never_silences_source(self):
        tracker = SourceBiasTracker()
        wire = [_news("Huge invasion claim", "LoneWolf", 3, ["Iran"])]
        for _ in range(30):
            tracker.analyze(wire)
        assert tracker.weight("LoneWolf") == 0.10  # floor, not zero

    def test_state_roundtrip(self):
        tracker = SourceBiasTracker()
        tracker.analyze([_news("missile strike", "X", 3, ["Iran"])])
        restored = SourceBiasTracker()
        restored.load_state(tracker.to_state())
        assert restored.weight("X") == tracker.weight("X")


# ---------------------------------------------------------------------------
# Self-improving projections
# ---------------------------------------------------------------------------

class TestRiskProjector:
    def test_no_forecast_until_min_samples(self):
        proj = RiskProjector()
        assert proj.observe({"IN": 50.0}) == {}
        assert proj.observe({"IN": 55.0}) == {}
        forecasts = proj.observe({"IN": 60.0})
        assert "IN" in forecasts

    def test_learns_alpha_from_errors_and_tracks_mae(self):
        proj = RiskProjector()
        # steadily rising series → higher alpha (fast tracking) wins
        for score in (10, 20, 30, 40, 50, 60, 70, 80):
            proj.observe({"IN": float(score)})
        assert proj.best_alpha >= 0.6
        assert proj.mae is not None and proj.mae > 0
        assert proj.samples == 8
        f = proj.forecast_for("IN")
        assert f is not None and 50 <= f <= 80

    def test_forecast_clamped_0_100(self):
        proj = RiskProjector()
        for _ in range(4):
            forecasts = proj.observe({"IN": 100.0})
        assert forecasts["IN"] <= 100.0

    def test_state_roundtrip(self):
        proj = RiskProjector()
        for s in (30, 40, 50, 60):
            proj.observe({"IN": float(s)})
        restored = RiskProjector()
        restored.load_state(proj.to_state())
        assert restored.samples == proj.samples
        assert restored.best_alpha == proj.best_alpha


# ---------------------------------------------------------------------------
# War zones
# ---------------------------------------------------------------------------

class TestWarZones:
    def test_baseline_without_events(self):
        zones = compute_war_zones([])
        assert len(zones) == 11
        ukraine = next(z for z in zones if z.id == "ukraine")
        assert ukraine.intensity == 0.85          # structural baseline
        assert ukraine.kind == "war"
        assert len(ukraine.polygon) >= 48         # map-ready ring

    def test_live_events_lift_intensity(self):
        events = [_ev(14.5, 42.5, severity=8.0) for _ in range(10)]
        zones = compute_war_zones(events)
        redsea = next(z for z in zones if z.id == "redsea")
        assert redsea.recent_events == 10
        assert redsea.intensity > 0.7             # lifted above baseline
        assert redsea.kind == "blockade"

    def test_geo_circle_ring_closed(self):
        ring = geo_circle(20.0, 70.0, 100.0)
        assert ring[0] == ring[-1]


# ---------------------------------------------------------------------------
# Agentic RAG
# ---------------------------------------------------------------------------

def _snapshot() -> OsintSnapshot:
    from geosupply.osint.intel import (
        compute_chokepoint_stress, compute_country_risk, tag_entities)
    news = [
        _news("Iran missile attack near Strait of Hormuz", "wire-a", 3),
        _news("Hormuz tanker traffic rerouted amid escalation", "wire-b", 2),
        _news("Quiet day in European markets", "wire-c", 0),
    ]
    tag_entities(news)
    events = [_ev(26.6, 56.2, severity=8.0, title="Hormuz area clash") for _ in range(8)]
    return OsintSnapshot(
        news=news, events=events,
        chokepoints=compute_chokepoint_stress(events),
        country_risk=compute_country_risk(news, events),
    )

class TestAgenticRag:
    def test_plan_extracts_entities_and_topics(self):
        sub_queries, entities = plan("What is the shipping risk around Iran and Hormuz?")
        assert "Iran" in entities
        assert "Strait of Hormuz" in entities
        assert "shipping" in sub_queries and "risk" in sub_queries

    def test_kg_expansion_adds_neighbor(self):
        kg = OsintKnowledgeGraph()
        kg.observe([_news("iran yemen axis", priority=2, entities=["Iran", "Yemen"])])
        _, entities = plan("iran outlook", kg)
        assert "Yemen" in entities                # one KG hop

    def test_answer_cites_wire_and_panels(self):
        ans = answer_query("hormuz risk", _snapshot())
        assert ans.confidence > 0.3
        assert ans.citations
        kinds = {c.kind for c in ans.citations}
        assert "chokepoint" in kinds              # structured panel retrieved
        assert "news" in kinds or "event" in kinds
        assert "Hormuz" in ans.answer
        assert ans.cost_inr == 0.0

    def test_no_signal_query_is_honest(self):
        ans = answer_query("antarctica penguin festival", OsintSnapshot())
        assert ans.confidence == 0.0
        assert "No live signals" in ans.answer

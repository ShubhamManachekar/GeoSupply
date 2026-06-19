"""
Derived OSINT analytics tests — pure deterministic functions, real logic.
"""
from __future__ import annotations

from geosupply.osint.intel import (
    apply_trends,
    build_highlights,
    compute_chokepoint_stress,
    compute_country_risk,
    detect_convergence,
    haversine_km,
    risk_confidence,
    tag_entities,
)
from geosupply.osint.models import MarketQuote, NewsItem, OsintEvent, PortStatus
from geosupply.osint.registry import CHOKEPOINTS


def _ev(lat: float, lon: float, severity: float = 5.0,
        category: str = "conflict", title: str = "clash reported") -> OsintEvent:
    return OsintEvent(
        id=f"t-{lat}-{lon}-{title[:8]}", category=category, title=title,
        lat=lat, lon=lon, severity=severity, source="test",
    )


def _news(title: str, priority: int = 0) -> NewsItem:
    return NewsItem(id=f"n-{hash(title)}", title=title, source="wire", priority=priority)


class TestHaversine:
    def test_known_distance(self):
        # Mumbai → Delhi ≈ 1150 km
        d = haversine_km(18.95, 72.84, 28.61, 77.21)
        assert 1100 < d < 1200

    def test_zero_distance(self):
        assert haversine_km(10.0, 20.0, 10.0, 20.0) == 0.0


class TestChokepointStress:
    def test_no_events_all_low(self):
        statuses = compute_chokepoint_stress([])
        assert len(statuses) == len(CHOKEPOINTS)
        assert all(s.level == "LOW" and s.stress_index == 0.0 for s in statuses)

    def test_events_near_hormuz_raise_its_stress(self):
        # 12 high-severity conflict events right at Hormuz
        events = [_ev(26.6, 56.2, severity=8.0) for _ in range(12)]
        statuses = compute_chokepoint_stress(events)
        hormuz = next(s for s in statuses if s.id == "hormuz")
        panama = next(s for s in statuses if s.id == "panama")
        assert hormuz.stress_index > 0.9
        assert hormuz.level == "CRITICAL"
        assert hormuz.recent_events == 12
        assert panama.stress_index == 0.0
        assert statuses[0].id == "hormuz"  # sorted by stress desc

    def test_non_conflict_events_ignored(self):
        events = [_ev(26.6, 56.2, severity=9.0, category="earthquake")]
        statuses = compute_chokepoint_stress(events)
        hormuz = next(s for s in statuses if s.id == "hormuz")
        assert hormuz.recent_events == 0


class TestCountryRisk:
    def test_empty_inputs(self):
        assert compute_country_risk([], []) == []

    def test_crisis_keywords_drive_score(self):
        news = [
            _news("Iran missile attack escalation in strait", priority=3),
            _news("Iran sanctions tightened", priority=2),
            _news("France hosts cultural festival", priority=0),
        ]
        risks = compute_country_risk(news, [])
        names = [r.name for r in risks]
        assert names[0] == "Iran"
        iran = risks[0]
        assert iran.score == 100.0  # normalised top
        assert iran.mentions == 2
        assert "missile" in iran.drivers or "attack" in iran.drivers
        france = next(r for r in risks if r.name == "France")
        assert france.score < iran.score

    def test_conflict_events_count_as_signals(self):
        events = [_ev(50.45, 30.52, title="Kyiv, Ukraine — 42 conflict mentions (24h)")]
        risks = compute_country_risk([], events)
        assert any(r.iso2 == "UA" for r in risks)


class TestHighlights:
    def test_full_brief(self):
        news = [_news("China blockade drill near Taiwan strait", priority=2)]
        events = [
            _ev(24.0, 119.5, severity=9.0),
            _ev(28.2, 84.7, severity=7.1, category="earthquake", title="M 7.1 - Nepal"),
        ] + [_ev(24.0 + i * 0.1, 119.0, severity=8.0) for i in range(15)]
        risks = compute_country_risk(news, events)
        chokepoints = compute_chokepoint_stress(events)
        ports = [PortStatus(name="Chennai", state="TN", lat=13.1, lon=80.3, status="DISRUPTED")]
        markets = [MarketQuote(symbol="USD/INR", name="USD/INR", value=83.5, unit="INR")]

        hl = build_highlights(risks, chokepoints, events, ports, markets)
        kinds = {h.kind for h in hl}
        assert {"risk", "chokepoint", "seismic", "india", "market"} <= kinds
        india = next(h for h in hl if h.kind == "india")
        assert "Chennai" in india.text
        market = next(h for h in hl if h.kind == "market")
        assert "₹" in market.text  # INR rule — never USD for rupee quotes

    def test_quiet_world(self):
        ports = [PortStatus(name="Kochi", state="KL", lat=9.97, lon=76.27)]
        hl = build_highlights([], compute_chokepoint_stress([]), [], ports, [])
        assert any("LOW/ELEVATED" in h.text for h in hl)
        assert any("operational" in h.text for h in hl)
        assert all(h.severity == 0 for h in hl)

    def test_inr_stress_highlight(self):
        markets = [MarketQuote(symbol="USD/INR", name="USD/INR", value=84.6,
                               change_pct=1.1, unit="INR")]
        hl = build_highlights([], [], [], [], markets)
        market = next(h for h in hl if h.kind == "market")
        assert "INR stress" in market.text
        assert "weakened" in market.text
        assert market.severity == 2

    def test_convergence_alerts_lead_the_brief(self):
        from geosupply.osint.models import ConvergenceAlert
        alert = ConvergenceAlert(
            id="conv-cp-hormuz", title="CONVERGENCE — Strait of Hormuz",
            lat=26.57, lon=56.25, asset_kind="chokepoint",
            signals=["conflict", "seismic"], severity=3, detail="test detail",
        )
        hl = build_highlights([], [], [], [], [], alerts=[alert])
        assert hl[0].kind == "convergence"
        assert hl[0].severity == 3
        assert "Hormuz" in hl[0].text


class TestRiskConfidence:
    """v8.0 CI propagation: ci_low/ci_high + data_density on every score."""

    def test_ci_narrows_with_more_signals(self):
        lo_s, hi_s, density_s = risk_confidence(50.0, 1)
        lo_d, hi_d, density_d = risk_confidence(50.0, 30)
        assert (hi_s - lo_s) > (hi_d - lo_d)
        assert density_s == "SPARSE"
        assert density_d == "HIGH"

    def test_ci_clamped_to_0_100(self):
        lo, hi, _ = risk_confidence(98.0, 1)
        assert 0.0 <= lo and hi <= 100.0

    def test_density_bands(self):
        assert risk_confidence(50, 2)[2] == "SPARSE"
        assert risk_confidence(50, 5)[2] == "LOW"
        assert risk_confidence(50, 10)[2] == "MEDIUM"
        assert risk_confidence(50, 20)[2] == "HIGH"

    def test_compute_country_risk_carries_ci(self):
        news = [_news("Iran missile attack", priority=3)]
        risks = compute_country_risk(news, [])
        iran = risks[0]
        assert iran.ci_low < iran.score <= iran.ci_high
        assert iran.data_density == "SPARSE"   # single mention


class TestTrends:
    def _risk(self, score: float):
        from geosupply.osint.models import CountryRisk
        return CountryRisk(iso2="IR", name="Iran", score=score)

    def test_new_until_two_observations(self):
        risk = self._risk(60.0)
        apply_trends([risk], [], [{"IR": 55.0}], [])
        assert risk.trend == "NEW"

    def test_rising_falling_flat(self):
        history = [{"IR": 40.0}, {"IR": 45.0}]   # baseline mean 42.5
        rising = self._risk(60.0)
        apply_trends([rising], [], history, [])
        assert rising.trend == "RISING"
        falling = self._risk(20.0)
        apply_trends([falling], [], history, [])
        assert falling.trend == "FALLING"
        flat = self._risk(44.0)
        apply_trends([flat], [], history, [])
        assert flat.trend == "FLAT"

    def test_chokepoint_trend(self):
        events = [_ev(26.6, 56.2, severity=8.0) for _ in range(12)]
        chokepoints = compute_chokepoint_stress(events)
        history = [{"hormuz": 0.1}, {"hormuz": 0.2}]
        apply_trends([], chokepoints, [], history)
        hormuz = next(c for c in chokepoints if c.id == "hormuz")
        assert hormuz.trend == "RISING"


class TestConvergence:
    def test_conflict_plus_quake_at_chokepoint_alerts(self):
        events = (
            [_ev(26.6, 56.2, severity=8.0) for _ in range(15)]           # conflict stress
            + [_ev(26.5, 56.0, severity=6.2, category="earthquake",
                   title="M 6.2 - Strait of Hormuz region")]             # seismic
        )
        chokepoints = compute_chokepoint_stress(events)
        alerts = detect_convergence(events, chokepoints, [])
        hormuz = next(a for a in alerts if a.id == "conv-cp-hormuz")
        assert hormuz.asset_kind == "chokepoint"
        assert set(hormuz.signals) == {"conflict", "seismic"}
        assert hormuz.severity == 3
        assert "M 6.2" in hormuz.detail

    def test_single_signal_is_not_convergence(self):
        events = [_ev(26.6, 56.2, severity=8.0) for _ in range(15)]      # conflict only
        chokepoints = compute_chokepoint_stress(events)
        assert detect_convergence(events, chokepoints, []) == []

    def test_disrupted_port_near_conflict_alerts(self):
        port = PortStatus(name="Kandla (Deendayal)", state="Gujarat",
                          lat=23.03, lon=70.22, status="DISRUPTED")
        events = [_ev(23.2, 70.5, severity=5.0, title="border clash reported")]
        alerts = detect_convergence(events, [], [port])
        assert len(alerts) == 1
        assert alerts[0].asset_kind == "port"
        assert "weather" in alerts[0].signals and "conflict" in alerts[0].signals
        assert alerts[0].severity == 3

    def test_operational_calm_port_no_alert(self):
        port = PortStatus(name="Kochi", state="Kerala", lat=9.97, lon=76.27)
        events = [_ev(10.0, 76.3, severity=5.0)]
        assert detect_convergence(events, [], [port]) == []


class TestEntityTagging:
    def test_headline_tagged_with_countries_and_chokepoints(self):
        items = [_news("China warships transit Taiwan Strait amid drills")]
        tag_entities(items)
        assert "China" in items[0].entities
        assert "Taiwan Strait" in items[0].entities

    def test_no_match_leaves_empty(self):
        items = [_news("Quarterly results beat analyst expectations")]
        tag_entities(items)
        assert items[0].entities == []

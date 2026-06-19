"""
GeoSupply AI — Derived OSINT analytics (middleware layer).

Pure, deterministic functions that turn raw source items into the
dashboard's intelligence panels:

  - chokepoint stress index  (conflict-event density near each chokepoint)
  - country risk index       (gazetteer-weighted headline scoring)
  - situation highlights     (rule-based brief — no LLM on this path,
                              keeping infrastructure off the critical DAG)

All logic is local CPU — cost_inr = 0.0.
"""
from __future__ import annotations

import math
from collections import Counter

from geosupply.osint.models import (
    ChokepointStatus,
    ConvergenceAlert,
    CountryRisk,
    IntelHighlight,
    MarketQuote,
    NewsItem,
    OsintEvent,
    PortStatus,
)
from geosupply.osint.models import WarZone
from geosupply.osint.registry import CHOKEPOINTS, COUNTRY_GAZETTEER, WAR_ZONES

_EARTH_RADIUS_KM = 6371.0

# Crisis keyword weights for country risk scoring
_CRISIS_WEIGHTS: dict[str, float] = {
    "war": 3.0, "invasion": 3.0, "missile": 3.0, "airstrike": 3.0, "nuclear": 3.0,
    "attack": 2.5, "killed": 2.5, "coup": 2.5, "blockade": 2.5, "strike": 1.5,
    "sanctions": 2.0, "conflict": 2.0, "escalation": 2.0, "warship": 2.0,
    "troops": 1.5, "tension": 1.5, "protest": 1.0, "tariff": 1.0,
    "shortage": 1.0, "disruption": 1.0, "embargo": 2.0, "ceasefire": 1.0,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _stress_level(index: float) -> str:
    if index >= 0.75:
        return "CRITICAL"
    if index >= 0.5:
        return "HIGH"
    if index >= 0.25:
        return "ELEVATED"
    return "LOW"


def compute_chokepoint_stress(events: list[OsintEvent]) -> list[ChokepointStatus]:
    """
    Stress = saturating function of severity-weighted conflict events
    within each chokepoint's monitoring radius.
    """
    statuses: list[ChokepointStatus] = []
    conflict_events = [e for e in events if e.category in ("conflict", "maritime")]
    for cp in CHOKEPOINTS:
        weight = 0.0
        nearby = 0
        for ev in conflict_events:
            if haversine_km(cp["lat"], cp["lon"], ev.lat, ev.lon) <= cp["radius_km"]:
                nearby += 1
                weight += max(ev.severity, 1.0)
        # Saturating curve: ~0.39 at weight 10, ~0.86 at weight 40
        index = round(1.0 - math.exp(-weight / 20.0), 3)
        statuses.append(ChokepointStatus(
            id=cp["id"], name=cp["name"], lat=cp["lat"], lon=cp["lon"],
            stress_index=index, level=_stress_level(index),
            recent_events=nearby, daily_transits=cp["daily_transits"],
            description=cp["description"],
        ))
    statuses.sort(key=lambda s: s.stress_index, reverse=True)
    return statuses


def compute_country_risk(
    news: list[NewsItem],
    events: list[OsintEvent],
    source_weights: dict[str, float] | None = None,
) -> list[CountryRisk]:
    """
    Gazetteer scan over live headlines: each country mention scores by the
    crisis keywords co-occurring in the same headline. Normalised 0-100.

    source_weights (bias handler): learned credibility per outlet — a
    chronically uncorroborated source moves the index less.
    """
    raw: dict[str, float] = {}
    mentions: Counter[str] = Counter()
    drivers: dict[str, Counter[str]] = {}

    titles = [
        (n.title.lower(), n.priority,
         0.5 + (source_weights or {}).get(n.source, 0.5))
        for n in news
    ]
    titles += [(e.title.lower(), 2, 1.0) for e in events if e.category == "conflict"]

    for title, priority, weight in titles:
        kw_score = sum(w for kw, w in _CRISIS_WEIGHTS.items() if kw in title)
        base = (0.5 + 0.5 * priority + kw_score) * weight
        for iso2, (_, aliases) in COUNTRY_GAZETTEER.items():
            if any(alias in title for alias in aliases):
                raw[iso2] = raw.get(iso2, 0.0) + base
                mentions[iso2] += 1
                drv = drivers.setdefault(iso2, Counter())
                for kw, w in _CRISIS_WEIGHTS.items():
                    if kw in title:
                        drv[kw] += 1

    if not raw:
        return []
    top = max(raw.values())
    risks = []
    for iso2, score in raw.items():
        pct = round(100.0 * score / top, 1)
        ci_low, ci_high, density = risk_confidence(pct, mentions[iso2])
        risks.append(CountryRisk(
            iso2=iso2,
            name=COUNTRY_GAZETTEER[iso2][0],
            score=pct,
            ci_low=ci_low,
            ci_high=ci_high,
            data_density=density,
            mentions=mentions[iso2],
            drivers=[kw for kw, _ in drivers.get(iso2, Counter()).most_common(3)],
        ))
    risks.sort(key=lambda r: r.score, reverse=True)
    return risks[:15]


def risk_confidence(score: float, mentions: int) -> tuple[float, float, str]:
    """
    v8.0 CI propagation: confidence interval narrows with signal volume
    (half-width ∝ 1/√n) and a data_density band rides along so the
    dashboard can label SPARSE scores as LOW CONFIDENCE. Epistemic
    honesty over false precision.
    """
    half_width = min(40.0, 45.0 / math.sqrt(mentions + 1))
    if mentions >= 15:
        density = "HIGH"
    elif mentions >= 8:
        density = "MEDIUM"
    elif mentions >= 3:
        density = "LOW"
    else:
        density = "SPARSE"
    return (
        round(max(0.0, score - half_width), 1),
        round(min(100.0, score + half_width), 1),
        density,
    )


def apply_trends(
    risks: list[CountryRisk],
    chokepoints: list[ChokepointStatus],
    risk_history: list[dict[str, float]],
    choke_history: list[dict[str, float]],
) -> None:
    """
    Drift-vector style trend per entity: compare current value with the mean
    of its recent history. NEW until at least 2 prior observations exist.
    Mutates in place (presentation enrichment, not a data rewrite).
    """
    def trend_for(key: str, current: float, history: list[dict[str, float]],
                  delta: float) -> str:
        past = [h[key] for h in history if key in h]
        if len(past) < 2:
            return "NEW"
        baseline = sum(past) / len(past)
        if current > baseline + delta:
            return "RISING"
        if current < baseline - delta:
            return "FALLING"
        return "FLAT"

    for r in risks:
        r.trend = trend_for(r.iso2, r.score, risk_history, delta=5.0)
    for c in chokepoints:
        c.trend = trend_for(c.id, c.stress_index, choke_history, delta=0.05)


def detect_convergence(
    events: list[OsintEvent],
    chokepoints: list[ChokepointStatus],
    ports: list[PortStatus],
) -> list[ConvergenceAlert]:
    """
    Convergence alerting (v8 Phase 9): one signal is noise — ≥2 independent
    signal types co-located around a supply-chain asset is a story.

    Chokepoints: conflict stress + (disaster|earthquake) within radius.
    Ports: weather disruption + (conflict|disaster|earthquake) within 300 km.
    """
    alerts: list[ConvergenceAlert] = []

    cp_radius = {cp["id"]: cp["radius_km"] for cp in CHOKEPOINTS}
    for cp in chokepoints:
        signals: list[str] = []
        if cp.level in ("HIGH", "CRITICAL"):
            signals.append("conflict")
        hazards = [
            e for e in events
            if e.category in ("disaster", "earthquake") and e.severity >= 5.0
            and haversine_km(cp.lat, cp.lon, e.lat, e.lon) <= cp_radius.get(cp.id, 500)
        ]
        if hazards:
            signals.append("disaster" if any(e.category == "disaster" for e in hazards)
                           else "seismic")
        if len(signals) >= 2:
            worst = max(hazards, key=lambda e: e.severity)
            alerts.append(ConvergenceAlert(
                id=f"conv-cp-{cp.id}",
                title=f"CONVERGENCE — {cp.name}",
                lat=cp.lat, lon=cp.lon, asset_kind="chokepoint",
                signals=signals,
                severity=3 if cp.level == "CRITICAL" else 2,
                detail=f"{cp.level} conflict stress ({cp.recent_events} events) + "
                       f"{worst.title}",
            ))

    for port in ports:
        if port.status == "OPERATIONAL" and port.monsoon_risk in ("LOW", "MODERATE"):
            continue
        nearby = [
            e for e in events
            if e.severity >= 4.0
            and haversine_km(port.lat, port.lon, e.lat, e.lon) <= 300.0
        ]
        if not nearby:
            continue
        signals = ["weather"] + sorted({e.category for e in nearby})
        worst = max(nearby, key=lambda e: e.severity)
        alerts.append(ConvergenceAlert(
            id=f"conv-port-{port.name.lower().replace(' ', '-')}",
            title=f"CONVERGENCE — {port.name} Port",
            lat=port.lat, lon=port.lon, asset_kind="port",
            signals=signals,
            severity=3 if port.status == "DISRUPTED" else 2,
            detail=f"Port {port.status}/{port.monsoon_risk} monsoon + {worst.title}",
        ))

    alerts.sort(key=lambda a: a.severity, reverse=True)
    return alerts


def geo_circle(lat: float, lon: float, radius_km: float, points: int = 48) -> list[list[float]]:
    """Geographically-correct circle ring [[lon,lat],...] for map polygons."""
    ring: list[list[float]] = []
    dlat = radius_km / 111.32
    coslat = max(0.01, math.cos(math.radians(lat)))
    dlon = radius_km / (111.32 * coslat)
    for i in range(points + 1):
        theta = 2 * math.pi * i / points
        ring.append([round(lon + dlon * math.cos(theta), 4),
                     round(lat + dlat * math.sin(theta), 4)])
    return ring


def compute_war_zones(events: list[OsintEvent]) -> list[WarZone]:
    """
    Live intensity per registered war/blockade/exclusion zone:
    baseline (structural fact) lifted by severity-weighted conflict-event
    density inside the zone radius this cycle.
    """
    zones: list[WarZone] = []
    conflict = [e for e in events if e.category in ("conflict", "maritime")]
    for wz in WAR_ZONES:
        weight = 0.0
        nearby = 0
        for ev in conflict:
            if haversine_km(wz["lat"], wz["lon"], ev.lat, ev.lon) <= wz["radius_km"]:
                nearby += 1
                weight += max(ev.severity, 1.0)
        live_lift = (1.0 - wz["baseline"]) * (1.0 - math.exp(-weight / 25.0))
        zones.append(WarZone(
            id=wz["id"], name=wz["name"], lat=wz["lat"], lon=wz["lon"],
            radius_km=wz["radius_km"], kind=wz["kind"],
            intensity=round(min(1.0, wz["baseline"] + live_lift), 3),
            recent_events=nearby, description=wz["description"],
            polygon=geo_circle(wz["lat"], wz["lon"], wz["radius_km"]),
        ))
    zones.sort(key=lambda z: z.intensity, reverse=True)
    return zones


def tag_entities(news: list[NewsItem]) -> None:
    """Tag each headline with matched countries + chokepoints (NER-lite)."""
    choke_names = [(cp["name"], cp["name"].lower()) for cp in CHOKEPOINTS]
    for item in news:
        low = item.title.lower()
        tags: list[str] = []
        for _, (name, aliases) in COUNTRY_GAZETTEER.items():
            if any(alias in low for alias in aliases):
                tags.append(name)
        for display, needle in choke_names:
            if needle in low:
                tags.append(display)
        item.entities = tags[:4]


def build_highlights(
    risks: list[CountryRisk],
    chokepoints: list[ChokepointStatus],
    events: list[OsintEvent],
    ports: list[PortStatus],
    markets: list[MarketQuote],
    alerts: list[ConvergenceAlert] | None = None,
) -> list[IntelHighlight]:
    """Rule-based situation brief — top signal per panel, deterministic."""
    hl: list[IntelHighlight] = []

    for alert in (alerts or [])[:3]:
        hl.append(IntelHighlight(
            kind="convergence", severity=alert.severity,
            text=f"{alert.title}: {alert.detail}",
        ))

    if risks:
        top = risks[0]
        hl.append(IntelHighlight(
            kind="risk", severity=3 if top.score >= 80 else 2,
            text=f"{top.name} leads global risk index at {top.score:.0f} "
                 f"({top.mentions} signals; drivers: {', '.join(top.drivers) or 'n/a'})",
        ))

    hot = [c for c in chokepoints if c.level in ("HIGH", "CRITICAL")]
    if hot:
        names = ", ".join(c.name for c in hot[:3])
        hl.append(IntelHighlight(
            kind="chokepoint", severity=3 if any(c.level == "CRITICAL" for c in hot) else 2,
            text=f"Chokepoint stress elevated: {names}",
        ))
    elif chokepoints:
        hl.append(IntelHighlight(
            kind="chokepoint", severity=0,
            text=f"All {len(chokepoints)} monitored chokepoints at LOW/ELEVATED stress",
        ))

    quakes = [e for e in events if e.category == "earthquake" and e.severity >= 5.5]
    if quakes:
        q = max(quakes, key=lambda e: e.severity)
        hl.append(IntelHighlight(
            kind="seismic", severity=2 if q.severity >= 6.5 else 1,
            text=f"Significant seismic activity: {q.title}",
        ))

    disrupted = [p for p in ports if p.status == "DISRUPTED"]
    watch = [p for p in ports if p.status == "WATCH"]
    if disrupted:
        hl.append(IntelHighlight(
            kind="india", severity=2,
            text=f"India port disruption: {', '.join(p.name for p in disrupted[:4])}",
        ))
    elif watch:
        hl.append(IntelHighlight(
            kind="india", severity=1,
            text=f"India ports on weather watch: {', '.join(p.name for p in watch[:4])}",
        ))
    elif ports:
        hl.append(IntelHighlight(
            kind="india", severity=0,
            text=f"All {len(ports)} major Indian ports operational",
        ))

    usdinr = next((m for m in markets if m.symbol == "USD/INR"), None)
    brent = next((m for m in markets if m.symbol == "CB.F"), None)
    if usdinr:
        txt = f"USD/INR at ₹{usdinr.value:.2f}"
        severity = 0
        if usdinr.change_pct is not None and abs(usdinr.change_pct) >= 0.5:
            direction = "weakened" if usdinr.change_pct > 0 else "strengthened"
            txt = (f"INR stress: rupee {direction} {abs(usdinr.change_pct):.2f}% — "
                   f"USD/INR at ₹{usdinr.value:.2f}")
            severity = 2 if abs(usdinr.change_pct) >= 1.0 else 1
        if brent:
            txt += f"; Brent at {brent.value:.1f} USD/bbl"
        hl.append(IntelHighlight(kind="market", severity=severity, text=txt))

    return hl

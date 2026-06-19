"""
GeoSupply AI — OSINT Dashboard Models
Pydantic v2 schemas for every panel the dashboard renders.

These are presentation-layer contracts between the aggregation middleware
and the frontend. They are versioned independently of the swarm message
schemas in geosupply.schemas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

EventCategory = Literal[
    "earthquake", "disaster", "conflict", "news", "maritime", "cyber"
]
StressLevel = Literal["LOW", "ELEVATED", "HIGH", "CRITICAL"]
PortState = Literal["OPERATIONAL", "WATCH", "DISRUPTED"]
Trend = Literal["RISING", "FLAT", "FALLING", "NEW"]
DataDensity = Literal["HIGH", "MEDIUM", "LOW", "SPARSE"]
MonsoonRisk = Literal["LOW", "MODERATE", "HEAVY", "EXTREME"]


def utcnow() -> datetime:
    """Timezone-aware UTC now (project rule: never datetime.utcnow())."""
    return datetime.now(timezone.utc)


class OsintEvent(BaseModel):
    """A geolocated event rendered as a map marker."""
    schema_version: int = 1
    id: str
    category: EventCategory
    title: str
    summary: str = ""
    lat: float
    lon: float
    severity: float = Field(default=0.0, ge=0.0, le=10.0)
    source: str
    url: str = ""
    ts: datetime = Field(default_factory=utcnow)
    country: str = ""


class NewsItem(BaseModel):
    """A headline in the live intel feed."""
    schema_version: int = 1
    id: str
    title: str
    source: str
    url: str = ""
    published: datetime = Field(default_factory=utcnow)
    category: EventCategory = "news"
    region: str = ""
    priority: int = Field(default=0, ge=0, le=3)  # 0=info 1=notice 2=alert 3=flash
    entities: list[str] = Field(default_factory=list)  # gazetteer/chokepoint tags


class MarketQuote(BaseModel):
    """One row of the market watch panel."""
    schema_version: int = 1
    symbol: str
    name: str
    value: float
    change_pct: float | None = None
    unit: str = ""
    ts: datetime = Field(default_factory=utcnow)


class ChokepointStatus(BaseModel):
    """Maritime chokepoint with a derived stress index."""
    schema_version: int = 1
    id: str
    name: str
    lat: float
    lon: float
    stress_index: float = Field(ge=0.0, le=1.0)
    level: StressLevel
    trend: Trend = "NEW"
    recent_events: int = 0
    daily_transits: int = 0
    description: str = ""


class CountryRisk(BaseModel):
    """
    Country risk score derived from live event/news density.

    v8.0 CI propagation rule: every risk score carries ci_low/ci_high and a
    data_density band — SPARSE + wide CI must surface as LOW CONFIDENCE.
    """
    schema_version: int = 2
    iso2: str
    name: str
    score: float = Field(ge=0.0, le=100.0)
    ci_low: float = Field(default=0.0, ge=0.0, le=100.0)
    ci_high: float = Field(default=100.0, ge=0.0, le=100.0)
    data_density: DataDensity = "SPARSE"
    trend: Trend = "NEW"
    mentions: int = 0
    drivers: list[str] = Field(default_factory=list)
    projected_score: float | None = None   # self-improving next-cycle forecast


class PortStatus(BaseModel):
    """Indian major port operational status (weather-driven)."""
    schema_version: int = 1
    name: str
    state: str
    lat: float
    lon: float
    status: PortState = "OPERATIONAL"
    wind_kmh: float | None = None
    precipitation_mm: float | None = None
    rain_3d_mm: float | None = None       # 3-day forecast accumulation
    monsoon_risk: MonsoonRisk = "LOW"
    note: str = ""


class SourceHealth(BaseModel):
    """Health of one upstream OSINT source (System panel)."""
    schema_version: int = 1
    name: str
    ok: bool
    breaker_state: str = "CLOSED"
    last_refresh: datetime | None = None
    latency_ms: float | None = None
    items: int = 0
    error: str = ""


class IntelHighlight(BaseModel):
    """One line of the rule-based situation brief."""
    schema_version: int = 1
    kind: Literal["risk", "chokepoint", "seismic", "disaster", "market", "india",
                  "convergence"]
    text: str
    severity: int = Field(default=0, ge=0, le=3)


class ConvergenceAlert(BaseModel):
    """
    Multi-signal convergence: ≥2 independent signal types co-located around
    a supply-chain asset (chokepoint or Indian port). The highest-value alert
    the dashboard produces — one signal is noise, convergence is a story.
    """
    schema_version: int = 1
    id: str
    title: str
    lat: float
    lon: float
    asset_kind: Literal["chokepoint", "port"]
    signals: list[str]                   # e.g. ["conflict", "disaster", "weather"]
    severity: int = Field(ge=1, le=3)
    detail: str = ""


class KGEdge(BaseModel):
    """One weighted relation in the live OSINT knowledge graph."""
    schema_version: int = 1
    source: str
    target: str
    relation: str = "co_reported"
    weight: float = Field(ge=0.0)
    observations: int = 0
    last_seen: datetime = Field(default_factory=utcnow)
    contexts: list[str] = Field(default_factory=list)  # sample headline(s)

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """G5 convention: (entity_source, entity_target, relation_type)."""
        return (self.source, self.target, self.relation)


class SourceBias(BaseModel):
    """
    Per-outlet news-analysis profile with a learned credibility weight.

    Credibility follows the v8 SourceFeedback loop: uncorroborated flash
    reporting is penalised (-0.05), corroborated reporting recovers (+0.02),
    floor 0.10 — a source is downweighted, never silenced.
    """
    schema_version: int = 1
    source: str
    items: int = 0
    avg_priority: float = 0.0
    sensationalism: float = Field(default=0.0, ge=0.0, le=1.0)
    corroboration_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    credibility: float = Field(default=0.5, ge=0.1, le=1.0)
    bias_flags: list[str] = Field(default_factory=list)


class IntelCitation(BaseModel):
    """A retrieved item backing one statement of an intel answer."""
    schema_version: int = 1
    kind: Literal["news", "event", "graph", "risk", "chokepoint", "port"]
    text: str
    source: str = ""
    url: str = ""
    score: float = 0.0


class IntelAnswer(BaseModel):
    """Agentic RAG output: plan → retrieve (+KG expansion) → synthesise."""
    schema_version: int = 1
    query: str
    answer: str
    sub_queries: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    citations: list[IntelCitation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=utcnow)
    cost_inr: float = 0.0


class WarZone(BaseModel):
    """Active war / blockade / exclusion zone with live intensity."""
    schema_version: int = 1
    id: str
    name: str
    lat: float
    lon: float
    radius_km: float
    kind: Literal["war", "blockade", "exclusion"]
    intensity: float = Field(ge=0.0, le=1.0)
    recent_events: int = 0
    description: str = ""
    polygon: list[list[float]] = Field(default_factory=list)  # [[lon,lat],...] ring


class LiveStream(BaseModel):
    """Curated live stream (official 24/7 news channels / public cams)."""
    schema_version: int = 1
    id: str
    name: str
    kind: Literal["news", "cam"]
    region: str = "GLOBAL"
    embed_url: str


class FocusCountry(BaseModel):
    """Focus-mode entry: country + map centroid."""
    schema_version: int = 1
    iso2: str
    name: str
    lat: float
    lon: float
    zoom: float = 4.0


class LearningStats(BaseModel):
    """Self-improvement telemetry for the autonomous loop (System panel)."""
    schema_version: int = 1
    cycles: int = 0
    refresh_interval_s: float = 120.0
    surge_mode: bool = False
    projection_mae: float | None = None     # mean abs error of risk forecasts
    projection_samples: int = 0
    kg_nodes: int = 0
    kg_edges: int = 0
    penalised_sources: int = 0


class OsintSnapshot(BaseModel):
    """Full dashboard payload — everything the frontend needs in one shot."""
    schema_version: int = 2
    generated_at: datetime = Field(default_factory=utcnow)
    alerts: list[ConvergenceAlert] = Field(default_factory=list)
    events: list[OsintEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    markets: list[MarketQuote] = Field(default_factory=list)
    chokepoints: list[ChokepointStatus] = Field(default_factory=list)
    country_risk: list[CountryRisk] = Field(default_factory=list)
    india_ports: list[PortStatus] = Field(default_factory=list)
    highlights: list[IntelHighlight] = Field(default_factory=list)
    war_zones: list[WarZone] = Field(default_factory=list)
    graph_edges: list[KGEdge] = Field(default_factory=list)      # top relations
    source_bias: list[SourceBias] = Field(default_factory=list)
    learning: LearningStats = Field(default_factory=LearningStats)
    health: list[SourceHealth] = Field(default_factory=list)
    cost_inr: float = 0.0  # all sources are free — INR 0

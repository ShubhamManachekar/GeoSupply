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
    health: list[SourceHealth] = Field(default_factory=list)
    cost_inr: float = 0.0  # all sources are free — INR 0

---
name: disaster-tracking
description: FA v2 guidelines for the DisasterWorker and processing USGS, NASA EONET, and GDACS disaster intelligence data.
---

# Disaster Tracking Skill (FA v2)

## Architecture Context

The `disaster-tracking` skill is centered around Phase 15 processing of real-time multi-source disaster Intelligence. It primarily relies on `DisasterWorker` to ingest, deduplicate, and normalize warnings/alerts from natural disasters globally, but specifically focusing on implications for supply chains crossing the Indian Subcontinent and associated maritime chokepoints.

## Supported Data Sources (Tier 1 Ingestion)
1.  **USGS Earthquake Data**: Real-time earthquake information. Focus on Magnitude >= 4.5.
2.  **NASA EONET v3**: Environmental Open Alerts (wildfires, storms, volcanoes). 
3.  **GDACS (Global Disaster Alert and Coordination System)**: Multi-hazard alert system.

## Data Ingestion & Fallback Rules
-   **Rate Limits**:
    -   USGS: unlimited
    -   NASA EONET: unlimited
    -   GDACS: unlimited
-   **XML Fragility (Risk 19)**:
    -   GDACS returns RSS/XML feeds. Parsers MUST use `xml.etree.ElementTree` with proper namespace handling.
    -   FALLBACK: Always fall back to RSS GeoJSON alternatives if the primary GDACS XML schema drifts or breaks.
    -   Ensure the `process()` function captures all XML ParseErrors and translates them to `WorkerError(provider="GDACS")`.

## Required Output Schema
The `DisasterWorker` must output a standardized `DisasterEvent` schema.

```python
class DisasterEvent(BaseModel):
    schema_version: int = 1
    source: Literal["usgs", "eonet", "gdacs"]
    event_id: str
    event_type: str
    severity: str
    coordinates: tuple[float, float]
    timestamp: datetime
    impact_radius_km: Optional[float] = None
    affected_countries: list[str] = Field(default_factory=list)
    raw_data: dict
```

## Worker Implementation Notes
-   Follow the zero-mock rule when writing tests for `DisasterWorker`. Build real SQLite temp tables if you implement localized caching.
-   Disaster workers SHOULD execute with a `@breaker(timeout=60, failures=3)` decorator as USGS/EONET feeds can occasionally hang.
-   De-duplication happens downstream in the `KnowledgeGraphAgent`, but the worker should ensure unique `event_id` generation for identical events reported by different APIs using SHA-256 hashing if necessary.

---
name: aviation-military-intel
description: FA v2 guidelines for AviationWorker and AISWorker, focusing on OpenSky OAuth2, maritime data, and military/cargo intelligence processing.
---

# Aviation & Military Intel Skill (FA v2)

## Architecture Context

The `aviation-military-intel` skill manages the critical ingestion of aviation and maritime telemetry (ADS-B and AIS data) directly linked to supply chain stability. This falls under Phase 15 upgrades using the `AviationWorker` and the `AISWorker`.

## Primary Components

### 1. AviationWorker (OpenSky Network)
-   **CRITICAL FA v2 RISK (R16)**: OpenSky OAuth2 Migration. Basic Auth is DEAD as of March 18, 2026. All code MUST use OAuth2.
-   **Token Management**: Use the `OpenSkyTokenManager` class to retrieve and refresh tokens 30s before expiry.
-   **API Block Detection (R21)**: Monitor HTTP 403 and `X-Rate-Limit-Remaining`. Implement block detection pattern. If blocked, log `BLOCKED` status, fallback to anonymous mode, and alert admin.
-   **Schema**: Requires transformation of OpenSky 18-element state vectors into `AviationTrack` (Schema #27).

### 2. AISWorker (AISStream)
-   **CRITICAL FA v2 RISK (R3)**: AISStream WebSocket Instability.
-   **Auto-reconnect**: Implement 30s exponential backoff.
-   **Data Buffering**: Use SQLite for last-known positions to handle data gaps gracefully.
-   **Heartbeats**: Ping the websocket connection every 60 seconds to keep it alive.
-   **Target Metrics**: Validate MMSI values. Filter out invalid values (e.g., 91, 181, 511, 102.3).
-   **Classification Rule**: Tag tracks accurately based on military, cargo, or tanker ship status.

## Required Output Schemas
### AviationTrack (Schema #27)
```python
class AviationTrack(BaseModel):
    schema_version: int = 1
    icao24: str
    callsign: Optional[str]
    origin_country: str
    coordinates: Optional[tuple[float, float]]
    velocity: Optional[float]
    true_track: Optional[float]
    category: int # Enums mapped per OpenSky protocol
    timestamp: datetime
```

## Security Rule Enforcement
- All OAuth Client IDs and Secrets MUST be securely loaded via `SecurityAgent.get_key()`. Hardcoding OpenSky credentials is a severe violation.
- All geospatial bounding boxes should cover explicitly designated Indian strategic and EEZ (Exclusive Economic Zone) maritime / airspace boundaries as defined in your global `config.py`.

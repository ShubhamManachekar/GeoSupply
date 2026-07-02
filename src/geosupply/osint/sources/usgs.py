"""
USGS Earthquake feed — free, key-free GeoJSON.
https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from geosupply.osint.models import OsintEvent
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"


def parse_usgs(payload: dict) -> list[OsintEvent]:
    """Normalize a USGS GeoJSON FeatureCollection into OsintEvents.

    Each feature is parsed defensively — one malformed record is skipped,
    never aborting the whole feed.
    """
    events: list[OsintEvent] = []
    for feat in payload.get("features", []):
        try:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            mag = props.get("mag")
            ts_ms = props.get("time")
            events.append(OsintEvent(
                id=f"usgs-{feat.get('id', '')}",
                category="earthquake",
                title=props.get("title") or f"M{mag} earthquake",
                summary=props.get("place") or "",
                lat=float(coords[1]),
                lon=float(coords[0]),
                severity=min(float(mag or 0.0), 10.0),
                source="USGS",
                url=props.get("url") or "",
                ts=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                if isinstance(ts_ms, (int, float))
                else datetime.now(timezone.utc),
            ))
        except (TypeError, ValueError):
            continue  # skip the bad record, keep the rest
    return events


class UsgsQuakeSource(BaseSource):
    """Earthquakes M2.5+ in the past 24h."""

    name = "USGS Earthquakes"
    ttl_s = 300.0

    async def fetch(self, client: httpx.AsyncClient) -> list[OsintEvent]:
        resp = await client.get(USGS_URL, timeout=DEFAULT_TIMEOUT_S, headers=http_headers())
        resp.raise_for_status()
        return parse_usgs(resp.json())

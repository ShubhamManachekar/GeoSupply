"""
NASA EONET v3 — open natural disaster events. Free, key-free.
https://eonet.gsfc.nasa.gov/api/v3/events
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from geosupply.osint.models import OsintEvent
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=80"

# EONET category id → severity weight (0-10 scale)
_CATEGORY_SEVERITY = {
    "volcanoes": 7.0,
    "severeStorms": 6.5,
    "wildfires": 5.0,
    "floods": 6.0,
    "seaLakeIce": 2.0,
    "earthquakes": 6.0,
    "drought": 4.0,
    "landslides": 5.0,
    "snow": 3.0,
    "dustHaze": 3.0,
    "manmade": 5.0,
    "waterColor": 1.0,
    "tempExtremes": 4.0,
}


def parse_eonet(payload: dict) -> list[OsintEvent]:
    """Normalize EONET v3 events into OsintEvents (latest geometry wins)."""
    events: list[OsintEvent] = []
    for ev in payload.get("events", []):
        geoms = ev.get("geometry") or []
        if not geoms:
            continue
        geom = geoms[-1]
        coords = geom.get("coordinates") or []
        gtype = geom.get("type", "Point")
        if gtype == "Polygon" and coords and coords[0]:
            lon, lat = coords[0][0][0], coords[0][0][1]
        elif gtype == "Point" and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        else:
            continue
        cats = ev.get("categories") or []
        cat_id = cats[0].get("id", "") if cats else ""
        cat_title = cats[0].get("title", "Disaster") if cats else "Disaster"
        date_str = geom.get("date", "")
        try:
            ts = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(timezone.utc)
        sources = ev.get("sources") or []
        events.append(OsintEvent(
            id=f"eonet-{ev.get('id', '')}",
            category="disaster",
            title=ev.get("title", "Natural event"),
            summary=cat_title,
            lat=float(lat),
            lon=float(lon),
            severity=_CATEGORY_SEVERITY.get(cat_id, 4.0),
            source="NASA EONET",
            url=sources[0].get("url", "") if sources else "",
            ts=ts,
        ))
    return events


class EonetDisasterSource(BaseSource):
    """Open natural disasters (storms, volcanoes, wildfires, floods...)."""

    name = "NASA EONET"
    ttl_s = 900.0

    async def fetch(self, client: httpx.AsyncClient) -> list[OsintEvent]:
        resp = await client.get(EONET_URL, timeout=DEFAULT_TIMEOUT_S, headers=http_headers())
        resp.raise_for_status()
        return parse_eonet(resp.json())

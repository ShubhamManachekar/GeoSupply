"""
GDELT 2.0 — global event & news monitoring. Free, key-free.

GdeltConflictSource — GEO 2.0 API: geolocated conflict/unrest mention
                      clusters over the last 24h (map hotspots).
GdeltNewsSource     — DOC 2.0 API: latest geopolitical/supply-chain
                      headlines (intel feed).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from geosupply.osint.models import NewsItem, OsintEvent
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers

GDELT_GEO_URL = "https://api.gdeltproject.org/api/v2/geo/geo"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

CONFLICT_QUERY = (
    '(conflict OR military OR airstrike OR missile OR blockade OR insurgency '
    'OR ceasefire OR artillery OR drone attack) sourcelang:eng'
)
NEWS_QUERY = (
    '(geopolitics OR sanctions OR "supply chain" OR semiconductor OR tariff '
    'OR "rare earth" OR shipping OR "strait of hormuz" OR "red sea" OR opec '
    'OR "border tension") sourcelang:eng'
)

_FLASH_TERMS = ("missile", "airstrike", "invasion", "explosion", "attack", "killed")
_ALERT_TERMS = ("sanctions", "blockade", "strike", "conflict", "warship", "seized",
                "coup", "embargo", "escalation", "mobilization")
_NOTICE_TERMS = ("tariff", "export", "shortage", "disruption", "tension", "warning",
                 "drill", "protest")


def headline_priority(title: str) -> int:
    """Rule-based priority band for a headline: 0 info … 3 flash."""
    low = title.lower()
    if any(t in low for t in _FLASH_TERMS):
        return 3
    if any(t in low for t in _ALERT_TERMS):
        return 2
    if any(t in low for t in _NOTICE_TERMS):
        return 1
    return 0


def parse_gdelt_geo(payload: dict) -> list[OsintEvent]:
    """Normalize GDELT GEO GeoJSON clusters into conflict hotspot events."""
    events: list[OsintEvent] = []
    feats = payload.get("features", [])
    max_count = max(
        (int((f.get("properties") or {}).get("count", 1)) for f in feats),
        default=1,
    ) or 1
    for feat in feats:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        count = int(props.get("count", 1))
        name = props.get("name", "Unknown location")
        uid = hashlib.sha1(f"{name}:{coords[0]}:{coords[1]}".encode()).hexdigest()[:12]
        events.append(OsintEvent(
            id=f"gdelt-{uid}",
            category="conflict",
            title=f"{name} — {count} conflict mentions (24h)",
            summary=name,
            lat=float(coords[1]),
            lon=float(coords[0]),
            severity=round(min(10.0, 2.0 + 8.0 * count / max_count), 2),
            source="GDELT GEO",
            url=props.get("shareimage", "") or "",
            country=name.split(",")[-1].strip() if "," in name else name,
        ))
    events.sort(key=lambda e: e.severity, reverse=True)
    return events[:120]


def parse_gdelt_articles(payload: dict) -> list[NewsItem]:
    """Normalize GDELT DOC ArtList articles into NewsItems."""
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    for art in payload.get("articles", []):
        title = (art.get("title") or "").strip()
        if not title:
            continue
        key = title.lower()[:80]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        seendate = art.get("seendate", "")
        try:
            published = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            published = datetime.now(timezone.utc)
        uid = hashlib.sha1((art.get("url") or title).encode()).hexdigest()[:12]
        items.append(NewsItem(
            id=f"gdelt-{uid}",
            title=title,
            source=art.get("domain", "GDELT"),
            url=art.get("url", ""),
            published=published,
            region=art.get("sourcecountry", ""),
            priority=headline_priority(title),
        ))
    return items


class GdeltConflictSource(BaseSource):
    """Conflict/unrest hotspot clusters from GDELT GEO 2.0 (24h window)."""

    name = "GDELT Conflict"
    ttl_s = 900.0

    async def fetch(self, client: httpx.AsyncClient) -> list[OsintEvent]:
        resp = await client.get(
            GDELT_GEO_URL,
            params={"query": CONFLICT_QUERY, "format": "geojson", "timespan": "24h"},
            timeout=DEFAULT_TIMEOUT_S,
            headers=http_headers(),
        )
        resp.raise_for_status()
        return parse_gdelt_geo(resp.json())


class GdeltNewsSource(BaseSource):
    """Latest geopolitical / supply-chain headlines from GDELT DOC 2.0."""

    name = "GDELT News"
    ttl_s = 600.0

    async def fetch(self, client: httpx.AsyncClient) -> list[NewsItem]:
        resp = await client.get(
            GDELT_DOC_URL,
            params={
                "query": NEWS_QUERY,
                "mode": "ArtList",
                "maxrecords": "50",
                "format": "json",
                "timespan": "6h",
                "sort": "DateDesc",
            },
            timeout=DEFAULT_TIMEOUT_S,
            headers=http_headers(),
        )
        resp.raise_for_status()
        return parse_gdelt_articles(resp.json())

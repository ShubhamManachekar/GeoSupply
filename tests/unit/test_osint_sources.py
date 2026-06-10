"""
OSINT source connector tests.

ZERO MOCKS philosophy: the parsers and the BaseSource TTL/breaker logic
under test are REAL. Only the external HTTP boundary is replaced, via
httpx.MockTransport serving real recorded payload structures.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from geosupply.osint.models import NewsItem, OsintEvent
from geosupply.osint.sources.base import BaseSource
from geosupply.osint.sources.eonet import parse_eonet
from geosupply.osint.sources.gdelt import (
    headline_priority,
    parse_gdelt_articles,
    parse_gdelt_geo,
)
from geosupply.osint.sources.markets import parse_crypto, parse_fx, parse_stooq
from geosupply.osint.sources.rss import RssNewsSource, parse_feed_xml
from geosupply.osint.sources.usgs import parse_usgs
from geosupply.osint.sources.weather import classify_port, parse_open_meteo
from geosupply.osint.registry import INDIA_PORTS

# ---------------------------------------------------------------------------
# Real recorded payload structures
# ---------------------------------------------------------------------------

USGS_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "us7000mqxv",
            "properties": {
                "mag": 5.8,
                "place": "120 km SSW of Severo-Kuril'sk, Russia",
                "time": 1718000000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000mqxv",
                "title": "M 5.8 - 120 km SSW of Severo-Kuril'sk, Russia",
            },
            "geometry": {"type": "Point", "coordinates": [155.43, 49.45, 40.6]},
        },
        {  # malformed: missing coordinates — must be skipped, not crash
            "type": "Feature",
            "id": "bad1",
            "properties": {"mag": 3.0, "time": "not-a-number"},
            "geometry": {"type": "Point", "coordinates": []},
        },
    ],
}

EONET_PAYLOAD = {
    "title": "EONET Events",
    "events": [
        {
            "id": "EONET_6513",
            "title": "Tropical Cyclone Ialy",
            "categories": [{"id": "severeStorms", "title": "Severe Storms"}],
            "sources": [{"id": "GDACS", "url": "https://gdacs.org/report?eventid=1"}],
            "geometry": [
                {"date": "2024-05-16T06:00:00Z", "type": "Point", "coordinates": [55.2, -9.8]},
                {"date": "2024-05-17T06:00:00Z", "type": "Point", "coordinates": [54.9, -10.4]},
            ],
        },
        {
            "id": "EONET_6601",
            "title": "Wildfire - Alberta, Canada",
            "categories": [{"id": "wildfires", "title": "Wildfires"}],
            "sources": [],
            "geometry": [],  # no geometry — must be skipped
        },
    ],
}

GDELT_GEO_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Kyiv, Ukraine", "count": 42, "shareimage": ""},
            "geometry": {"type": "Point", "coordinates": [30.52, 50.45]},
        },
        {
            "type": "Feature",
            "properties": {"name": "Hodeidah, Yemen", "count": 7},
            "geometry": {"type": "Point", "coordinates": [42.95, 14.8]},
        },
    ],
}

GDELT_DOC_PAYLOAD = {
    "articles": [
        {
            "url": "https://example-news.com/red-sea-attack",
            "title": "Missile attack on tanker in Red Sea disrupts shipping",
            "seendate": "20260610T093000Z",
            "domain": "example-news.com",
            "sourcecountry": "United States",
            "language": "English",
        },
        {  # duplicate title — must be deduplicated
            "url": "https://mirror.com/red-sea-attack",
            "title": "Missile attack on tanker in Red Sea disrupts shipping",
            "seendate": "20260610T094500Z",
            "domain": "mirror.com",
        },
        {
            "url": "https://example.in/tariff",
            "title": "New tariff rules for electronics imports announced",
            "seendate": "bad-date",
            "domain": "example.in",
            "sourcecountry": "India",
        },
    ],
}

RSS2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Wire</title>
  <item>
    <title>Sanctions package targets shipping insurers</title>
    <link>https://wire.example/sanctions</link>
    <pubDate>Wed, 10 Jun 2026 08:15:00 GMT</pubDate>
  </item>
  <item>
    <title>Monsoon onset advances over Kerala</title>
    <link>https://wire.example/monsoon</link>
    <pubDate>Wed, 10 Jun 2026 07:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Wire</title>
  <entry>
    <title>Port congestion warning issued for transshipment hub</title>
    <link href="https://atom.example/congestion"/>
    <updated>2026-06-10T06:30:00Z</updated>
  </entry>
</feed>"""

FX_PAYLOAD = {"result": "success", "rates": {"USD": 1, "INR": 83.52, "EUR": 0.92, "CNY": 7.24}}
CRYPTO_PAYLOAD = {
    "bitcoin": {"usd": 105000.0, "usd_24h_change": -1.23},
    "ethereum": {"usd": 3900.5, "usd_24h_change": 2.41},
}
STOOQ_CSV = (
    "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    "CL.F,2026-06-10,15:30:02,68.10,68.90,67.55,68.42,123456\n"
    "CB.F,2026-06-10,15:30:02,71.95,72.60,71.20,72.18,98765\n"
    "GC.F,2026-06-10,15:30:02,3315.0,3340.0,3300.0,N/D,45678\n"
    "USDINR,2026-06-10,15:30:02,83.10,83.95,83.05,83.90,0\n"
)

OPEN_METEO_PAYLOAD = (
    [
        {"current": {"wind_speed_10m": 12.3, "precipitation": 0.0, "weather_code": 2},
         "daily": {"precipitation_sum": [2.0, 0.5, 1.0]}}
        for _ in range(len(INDIA_PORTS) - 2)
    ]
    + [{"current": {"wind_speed_10m": 18.0, "precipitation": 1.0, "weather_code": 61},
        "daily": {"precipitation_sum": [60.0, 55.0, 40.0]}}]   # HEAVY monsoon → WATCH
    + [{"current": {"wind_speed_10m": 75.0, "precipitation": 22.0, "weather_code": 95},
        "daily": {"precipitation_sum": [80.0, 90.0, 70.0]}}]   # gale + EXTREME rain
)


# ---------------------------------------------------------------------------
# Parser tests (real logic, real payload shapes)
# ---------------------------------------------------------------------------

class TestUsgsParser:
    def test_happy_path(self):
        events = parse_usgs(USGS_PAYLOAD)
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, OsintEvent)
        assert ev.category == "earthquake"
        assert ev.severity == 5.8
        assert ev.lat == 49.45 and ev.lon == 155.43
        assert ev.id == "usgs-us7000mqxv"
        assert ev.ts.year >= 2024

    def test_empty_payload(self):
        assert parse_usgs({}) == []


class TestEonetParser:
    def test_uses_latest_geometry(self):
        events = parse_eonet(EONET_PAYLOAD)
        assert len(events) == 1
        ev = events[0]
        assert ev.category == "disaster"
        assert ev.lat == -10.4 and ev.lon == 54.9
        assert ev.severity == 6.5  # severeStorms weight
        assert ev.url == "https://gdacs.org/report?eventid=1"  # exact match (CodeQL)

    def test_empty(self):
        assert parse_eonet({"events": []}) == []


class TestGdeltParsers:
    def test_geo_clusters_scaled_by_count(self):
        events = parse_gdelt_geo(GDELT_GEO_PAYLOAD)
        assert len(events) == 2
        assert events[0].severity > events[1].severity  # sorted desc
        assert events[0].category == "conflict"
        assert "Kyiv" in events[0].title

    def test_doc_articles_dedup_and_dates(self):
        items = parse_gdelt_articles(GDELT_DOC_PAYLOAD)
        assert len(items) == 2  # duplicate title removed
        flash = items[0]
        assert flash.priority == 3  # "missile" + "attack" headline
        assert flash.published.year == 2026
        assert items[1].priority == 1  # "tariff" → notice

    def test_headline_priority_bands(self):
        assert headline_priority("Missile strike kills dozens") == 3
        assert headline_priority("New sanctions on shipping firms") == 2
        assert headline_priority("Tariff review for solar imports") == 1
        assert headline_priority("Quarterly earnings beat estimates") == 0


class TestRssParser:
    def test_rss2(self):
        items = parse_feed_xml(RSS2_XML, "Test Wire", "GLOBAL")
        assert len(items) == 2
        assert items[0].title.startswith("Sanctions")
        assert items[0].priority == 2
        assert items[0].url == "https://wire.example/sanctions"
        assert items[0].published.year == 2026

    def test_atom(self):
        items = parse_feed_xml(ATOM_XML, "Atom Wire", "GLOBAL")
        assert len(items) == 1
        assert items[0].url == "https://atom.example/congestion"

    def test_invalid_xml_returns_empty(self):
        assert parse_feed_xml("<not-xml", "Bad", "GLOBAL") == []


class TestMarketParsers:
    def test_fx(self):
        quotes = parse_fx(FX_PAYLOAD)
        symbols = {q.symbol for q in quotes}
        assert {"USD/INR", "EUR/INR", "USD/CNY"} == symbols
        usdinr = next(q for q in quotes if q.symbol == "USD/INR")
        assert usdinr.value == 83.52

    def test_crypto(self):
        quotes = parse_crypto(CRYPTO_PAYLOAD)
        assert len(quotes) == 2
        btc = next(q for q in quotes if q.symbol == "BTC")
        assert btc.change_pct == -1.23

    def test_stooq_skips_nd_rows(self):
        quotes = parse_stooq(STOOQ_CSV)
        symbols = {q.symbol for q in quotes}
        assert symbols == {"CL.F", "CB.F", "USDINR"}  # GC.F Close=N/D skipped
        wti = next(q for q in quotes if q.symbol == "CL.F")
        assert wti.value == 68.42
        assert wti.change_pct is not None

    def test_inr_stress_merged_into_fx_quote(self):
        from geosupply.osint.sources.markets import merge_inr_stress
        quotes = parse_fx(FX_PAYLOAD) + parse_stooq(STOOQ_CSV)
        merged = merge_inr_stress(quotes)
        assert all(q.symbol != "USDINR" for q in merged)  # intraday row dropped
        usdinr = next(q for q in merged if q.symbol == "USD/INR")
        assert usdinr.value == 83.52              # er-api level kept
        assert usdinr.change_pct is not None      # stooq intraday change folded in
        assert usdinr.change_pct > 0.9            # (83.90-83.10)/83.10 ≈ +0.96%

    def test_inr_stress_promotes_intraday_when_fx_feed_down(self):
        from geosupply.osint.sources.markets import merge_inr_stress
        merged = merge_inr_stress(parse_stooq(STOOQ_CSV))
        usdinr = next(q for q in merged if q.symbol == "USD/INR")
        assert usdinr.value == 83.90


class TestPortWeather:
    def test_classification_bands(self):
        assert classify_port(10.0, 0.0)[0] == "OPERATIONAL"
        assert classify_port(45.0, 0.0)[0] == "WATCH"
        assert classify_port(70.0, 0.0)[0] == "DISRUPTED"
        assert classify_port(5.0, 20.0)[0] == "DISRUPTED"
        assert classify_port(None, None)[0] == "OPERATIONAL"

    def test_parse_batched_response(self):
        statuses = parse_open_meteo(OPEN_METEO_PAYLOAD, INDIA_PORTS)
        assert len(statuses) == len(INDIA_PORTS)
        assert statuses[-1].status == "DISRUPTED"
        assert statuses[0].status == "OPERATIONAL"
        assert statuses[0].name == INDIA_PORTS[0]["name"]

    def test_monsoon_bands_from_forecast(self):
        from geosupply.osint.sources.weather import classify_monsoon
        assert classify_monsoon(None) == "LOW"
        assert classify_monsoon(30.0) == "LOW"
        assert classify_monsoon(80.0) == "MODERATE"
        assert classify_monsoon(150.0) == "HEAVY"
        assert classify_monsoon(250.0) == "EXTREME"

    def test_heavy_monsoon_forecast_puts_port_on_watch(self):
        statuses = parse_open_meteo(OPEN_METEO_PAYLOAD, INDIA_PORTS)
        watch = statuses[-2]   # calm now, but 155mm forecast over 3 days
        assert watch.monsoon_risk == "HEAVY"
        assert watch.status == "WATCH"
        assert watch.rain_3d_mm == 155.0
        extreme = statuses[-1]
        assert extreme.monsoon_risk == "EXTREME"
        assert statuses[0].monsoon_risk == "LOW"


# ---------------------------------------------------------------------------
# BaseSource TTL + circuit breaker behaviour (real logic over MockTransport)
# ---------------------------------------------------------------------------

class _CountingSource(BaseSource):
    name = "Counting"
    ttl_s = 60.0

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def fetch(self, client: httpx.AsyncClient) -> list:
        self.calls += 1
        resp = await client.get("https://upstream.test/data")
        resp.raise_for_status()
        return resp.json()["items"]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestBaseSourceLifecycle:
    async def test_ttl_cache_prevents_refetch(self):
        client = _client(lambda req: httpx.Response(200, json={"items": [1, 2]}))
        src = _CountingSource()
        r1 = await src.refresh(client)
        r2 = await src.refresh(client)  # within TTL — served from cache
        assert r1.ok and r2.ok
        assert src.calls == 1
        assert r2.items == [1, 2]
        await client.aclose()

    async def test_failure_serves_last_good_payload(self):
        state = {"fail": False}

        def handler(req):
            if state["fail"]:
                return httpx.Response(503)
            return httpx.Response(200, json={"items": ["good"]})

        client = _client(handler)
        src = _CountingSource()
        ok = await src.refresh(client)
        assert ok.ok and ok.items == ["good"]
        state["fail"] = True
        bad = await src.refresh(client, force=True)
        assert not bad.ok
        assert bad.items == ["good"]  # degraded to cache, never empty-lied
        assert "503" in bad.error or "Error" in bad.error
        await client.aclose()

    async def test_breaker_opens_after_repeated_failures(self):
        client = _client(lambda req: httpx.Response(500))
        src = _CountingSource()
        for _ in range(4):
            await src.refresh(client, force=True)
        health = src.health()
        assert health.breaker_state == "OPEN"
        calls_before = src.calls
        result = await src.refresh(client, force=True)  # short-circuited
        assert src.calls == calls_before
        assert not result.ok
        assert "OPEN" in result.error
        await client.aclose()


class TestRssSourceAggregation:
    async def test_one_dead_feed_does_not_kill_wire(self):
        def handler(req):
            if "dead" in str(req.url):
                return httpx.Response(404)
            return httpx.Response(200, text=RSS2_XML)

        client = _client(handler)
        src = RssNewsSource(feeds=[
            ("Live", "GLOBAL", "https://live.example/rss"),
            ("Dead", "GLOBAL", "https://dead.example/rss"),
        ])
        result = await src.refresh(client)
        assert result.ok
        assert len(result.items) == 2
        assert all(isinstance(i, NewsItem) for i in result.items)
        await client.aclose()

    async def test_all_feeds_dead_is_a_failure(self):
        client = _client(lambda req: httpx.Response(403))
        src = RssNewsSource(feeds=[("Dead", "GLOBAL", "https://dead.example/rss")])
        result = await src.refresh(client)
        assert not result.ok
        assert "all RSS feeds failed" in result.error
        await client.aclose()

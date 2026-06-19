"""
OSINT aggregator + API endpoint tests.

The aggregator, router, and WebSocket hub under test are REAL.
Only the upstream HTTP boundary is replaced with httpx.MockTransport
serving real recorded payload structures (project rule: mock external
dependencies only).
"""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from geosupply.api.routers import osint as osint_router_module
from geosupply.osint.aggregator import OsintAggregator
from tests.unit.test_osint_sources import (
    CRYPTO_PAYLOAD,
    EONET_PAYLOAD,
    FX_PAYLOAD,
    GDELT_DOC_PAYLOAD,
    GDELT_GEO_PAYLOAD,
    OPEN_METEO_PAYLOAD,
    RSS2_XML,
    STOOQ_CSV,
    USGS_PAYLOAD,
)


def _route_request(req: httpx.Request) -> httpx.Response:
    """One MockTransport handler covering every upstream OSINT endpoint."""
    host, path = req.url.host, req.url.path
    if host == "earthquake.usgs.gov":
        return httpx.Response(200, json=USGS_PAYLOAD)
    if host == "eonet.gsfc.nasa.gov":
        return httpx.Response(200, json=EONET_PAYLOAD)
    if host == "api.gdeltproject.org" and "/geo/" in path:
        return httpx.Response(200, json=GDELT_GEO_PAYLOAD)
    if host == "api.gdeltproject.org":
        return httpx.Response(200, json=GDELT_DOC_PAYLOAD)
    if host == "open.er-api.com":
        return httpx.Response(200, json=FX_PAYLOAD)
    if host == "api.coingecko.com":
        return httpx.Response(200, json=CRYPTO_PAYLOAD)
    if host == "stooq.com":
        return httpx.Response(200, text=STOOQ_CSV)
    if host == "api.open-meteo.com":
        return httpx.Response(200, json=OPEN_METEO_PAYLOAD)
    # every remaining host is an RSS feed
    return httpx.Response(200, text=RSS2_XML)


@pytest.fixture
async def aggregator(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_STATE_PATH", str(tmp_path / "learning.json"))
    client = httpx.AsyncClient(transport=httpx.MockTransport(_route_request))
    agg = OsintAggregator(client=client)
    await agg.setup()
    yield agg
    await agg.teardown()
    await client.aclose()


class TestAggregator:
    async def test_full_refresh_builds_snapshot(self, aggregator):
        snap = await aggregator.refresh(force=True)
        assert len(snap.events) >= 4          # quakes + disasters + conflicts
        assert len(snap.news) >= 3            # RSS + GDELT articles
        assert len(snap.markets) >= 5         # FX + crypto + commodities
        assert len(snap.chokepoints) == 9
        assert snap.country_risk              # gazetteer hits from headlines
        assert len(snap.india_ports) == 12
        assert snap.highlights
        assert isinstance(snap.alerts, list)  # convergence detector ran
        assert snap.cost_inr == 0.0           # all sources free — INR 0
        assert all(h.ok for h in snap.health)
        # v8 CI propagation: every risk row carries an interval + density band
        assert all(r.ci_low <= r.score <= r.ci_high for r in snap.country_risk)
        # INR stress: stooq intraday change folded into the USD/INR quote
        usdinr = next(m for m in snap.markets if m.symbol == "USD/INR")
        assert usdinr.change_pct is not None
        # entity tagging on the wire
        assert any(n.entities for n in snap.news) or snap.news

    async def test_snapshot_cached_between_refreshes(self, aggregator):
        await aggregator.refresh(force=True)
        snap1 = aggregator.snapshot()
        snap2 = await aggregator.refresh()    # TTL-gated — served from cache
        assert snap2.generated_at >= snap1.generated_at
        assert len(snap2.events) == len(snap1.events)

    async def test_intelligence_suite_in_snapshot(self, aggregator):
        snap = await aggregator.refresh(force=True)
        assert len(snap.war_zones) == 11
        assert all(0.0 <= z.intensity <= 1.0 for z in snap.war_zones)
        assert snap.source_bias                 # bias handler profiled the wire
        assert snap.learning.cycles == 1
        assert snap.learning.kg_edges >= 0
        assert snap.learning.refresh_interval_s > 0

    async def test_learning_state_persists_across_instances(self, aggregator, tmp_path):
        await aggregator.refresh(force=True)
        aggregator.save_state()
        restored = OsintAggregator(client=aggregator._client)
        restored.load_state()
        assert restored._cycles == 1
        assert restored.bias.to_state() == aggregator.bias.to_state()

    async def test_surge_mode_on_flash_activity(self, aggregator):
        from geosupply.osint.models import ConvergenceAlert
        alert = ConvergenceAlert(id="x", title="t", lat=0, lon=0,
                                 asset_kind="port", signals=["a", "b"], severity=3)
        aggregator._adapt_interval([alert], [])
        assert aggregator._surge is True
        assert aggregator._interval_s == 60.0
        aggregator._cycles = 10
        aggregator._adapt_interval([], [])
        assert aggregator._surge is False
        assert aggregator._interval_s == 300.0  # quiet world slows down

    async def test_scheduler_start_stop(self, aggregator):
        aggregator.start_scheduler()
        assert aggregator._task is not None and not aggregator._task.done()
        await aggregator.stop_scheduler()
        assert aggregator._task is None


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
async def api_client(aggregator):
    from geosupply.api.main import create_app

    await aggregator.refresh(force=True)
    app = create_app()
    app.dependency_overrides[osint_router_module.aggregator_dep] = lambda: aggregator
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestOsintEndpoints:
    async def test_snapshot(self, api_client):
        resp = await api_client.get("/osint/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cost_inr"] == 0.0
        assert body["events"] and body["news"] and body["chokepoints"]

    async def test_events_filter(self, api_client):
        resp = await api_client.get("/osint/events", params={"category": "earthquake"})
        assert resp.status_code == 200
        events = resp.json()
        assert events
        assert all(e["category"] == "earthquake" for e in events)

    async def test_news_priority_filter(self, api_client):
        resp = await api_client.get("/osint/news", params={"min_priority": 2})
        assert resp.status_code == 200
        assert all(n["priority"] >= 2 for n in resp.json())

    async def test_panel_endpoints(self, api_client):
        for path, min_len in [
            ("/osint/markets", 5),
            ("/osint/chokepoints", 9),
            ("/osint/risk", 1),
            ("/osint/india/ports", 12),
            ("/osint/highlights", 1),
            ("/osint/sources/health", 7),
            ("/osint/alerts", 0),
        ]:
            resp = await api_client.get(path)
            assert resp.status_code == 200, path
            assert len(resp.json()) >= min_len, path

    async def test_sources_health_shape(self, api_client):
        resp = await api_client.get("/osint/sources/health")
        row = resp.json()[0]
        assert {"name", "ok", "breaker_state", "items"} <= set(row.keys())

    async def test_warzones_endpoint(self, api_client):
        resp = await api_client.get("/osint/warzones")
        assert resp.status_code == 200
        zones = resp.json()
        assert len(zones) == 11
        assert {"id", "kind", "intensity", "polygon"} <= set(zones[0].keys())

    async def test_ask_endpoint(self, api_client):
        resp = await api_client.get("/osint/ask", params={"q": "red sea shipping risk"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "red sea shipping risk"
        assert "answer" in body and "citations" in body
        assert body["cost_inr"] == 0.0

    async def test_graph_endpoint(self, api_client):
        resp = await api_client.get("/osint/graph")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_streams_endpoint_and_region_filter(self, api_client):
        resp = await api_client.get("/osint/streams")
        streams = resp.json()
        assert len(streams) == 10
        assert all(s["embed_url"].startswith("https://www.youtube.com/embed/")
                   for s in streams)
        india = (await api_client.get("/osint/streams",
                                      params={"region": "india"})).json()
        assert india and all(s["region"] == "INDIA" for s in india)

    async def test_focus_countries_india_first(self, api_client):
        resp = await api_client.get("/osint/focus/countries")
        countries = resp.json()
        assert countries[0]["iso2"] == "IN"      # India-first focus registry
        assert {"lat", "lon", "zoom"} <= set(countries[0].keys())
        assert len(countries) == 30

    async def test_sources_bias_endpoint(self, api_client):
        resp = await api_client.get("/osint/sources/bias")
        assert resp.status_code == 200
        rows = resp.json()
        assert rows
        assert {"source", "credibility", "sensationalism"} <= set(rows[0].keys())


# ---------------------------------------------------------------------------
# WebSocket live link (real hub, real WS session via Starlette TestClient)
# ---------------------------------------------------------------------------

class TestOsintWebSocket:
    def _ws_app(self, aggregator: OsintAggregator, monkeypatch) -> FastAPI:
        app = FastAPI()
        app.include_router(osint_router_module.router, prefix="/osint")
        monkeypatch.setattr(osint_router_module, "get_aggregator", lambda: aggregator)
        return app

    async def test_ws_sends_snapshot_on_connect_and_broadcast(self, aggregator, monkeypatch):
        await aggregator.refresh(force=True)
        app = self._ws_app(aggregator, monkeypatch)
        client = TestClient(app)
        with client.websocket_connect("/osint/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "snapshot"
            assert first["data"]["cost_inr"] == 0.0
            assert first["data"]["events"]

    async def test_hub_tracks_and_prunes_clients(self, aggregator, monkeypatch):
        await aggregator.refresh(force=True)
        app = self._ws_app(aggregator, monkeypatch)
        client = TestClient(app)
        assert aggregator.hub.client_count == 0
        with client.websocket_connect("/osint/ws") as ws:
            ws.receive_json()
            assert aggregator.hub.client_count == 1
        # context exit closes socket → router cleanup must deregister
        assert aggregator.hub.client_count == 0

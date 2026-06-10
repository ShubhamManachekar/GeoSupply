"""
GeoSupply AI — OSINT aggregation middleware.

OsintAggregator owns:
  - one shared httpx.AsyncClient
  - all source connectors (TTL-cached, breaker-guarded)
  - derived analytics (chokepoint stress, country risk, highlights)
  - a background refresh loop that pushes snapshots to the WebSocket hub

Single-writer principle: only the aggregator mutates the snapshot; the API
layer and WS hub are read-only consumers. All sources are free — INR 0.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from functools import lru_cache

import httpx

from geosupply.osint.hub import OsintHub
from geosupply.osint.intel import (
    apply_trends,
    build_highlights,
    compute_chokepoint_stress,
    compute_country_risk,
    detect_convergence,
    tag_entities,
)
from geosupply.osint.models import NewsItem, OsintEvent, OsintSnapshot
from geosupply.osint.sources import (
    EonetDisasterSource,
    GdeltConflictSource,
    GdeltNewsSource,
    IndiaPortWeatherSource,
    MarketsSource,
    RssNewsSource,
    UsgsQuakeSource,
)

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_S = 120.0  # scheduler tick; per-source TTLs gate real fetches
MAX_NEWS = 100
MAX_EVENTS = 250


class OsintAggregator:
    """Aggregates all OSINT sources into one cached dashboard snapshot."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self.hub = OsintHub()
        self.quakes = UsgsQuakeSource()
        self.disasters = EonetDisasterSource()
        self.conflicts = GdeltConflictSource()
        self.gdelt_news = GdeltNewsSource()
        self.rss = RssNewsSource()
        self.markets = MarketsSource()
        self.port_weather = IndiaPortWeatherSource()
        self._snapshot: OsintSnapshot = OsintSnapshot()
        self._refresh_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        # Trend history ring buffers (drift-vector style): last 12 cycles
        self._risk_history: deque[dict[str, float]] = deque(maxlen=12)
        self._choke_history: deque[dict[str, float]] = deque(maxlen=12)

    # ── lifecycle ─────────────────────────────────────────────────────
    async def setup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(follow_redirects=True)

    async def teardown(self) -> None:
        await self.stop_scheduler()
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def sources(self) -> list:
        return [self.quakes, self.disasters, self.conflicts, self.gdelt_news,
                self.rss, self.markets, self.port_weather]

    # ── core refresh ──────────────────────────────────────────────────
    async def refresh(self, force: bool = False) -> OsintSnapshot:
        """Refresh all sources (TTL-gated) and rebuild the snapshot."""
        if self._client is None:
            await self.setup()
        assert self._client is not None
        async with self._refresh_lock:
            results = await asyncio.gather(
                *(src.refresh(self._client, force=force) for src in self.sources)
            )
            (quakes_r, disasters_r, conflicts_r, gnews_r,
             rss_r, markets_r, ports_r) = results

            events: list[OsintEvent] = [
                *quakes_r.items, *disasters_r.items, *conflicts_r.items,
            ][:MAX_EVENTS]

            news: list[NewsItem] = [*rss_r.items, *gnews_r.items]
            news.sort(key=lambda n: n.published, reverse=True)
            news = news[:MAX_NEWS]
            tag_entities(news)

            chokepoints = compute_chokepoint_stress(events)
            risks = compute_country_risk(news, events)
            apply_trends(risks, chokepoints,
                         list(self._risk_history), list(self._choke_history))
            alerts = detect_convergence(events, chokepoints, ports_r.items)
            highlights = build_highlights(
                risks, chokepoints, events, ports_r.items, markets_r.items,
                alerts=alerts,
            )
            self._risk_history.append({r.iso2: r.score for r in risks})
            self._choke_history.append({c.id: c.stress_index for c in chokepoints})

            self._snapshot = OsintSnapshot(
                alerts=alerts,
                events=events,
                news=news,
                markets=markets_r.items,
                chokepoints=chokepoints,
                country_risk=risks,
                india_ports=ports_r.items,
                highlights=highlights,
                health=[src.health() for src in self.sources],
                cost_inr=0.0,  # every source on this layer is free
            )
            return self._snapshot

    def snapshot(self) -> OsintSnapshot:
        """Last built snapshot (may be empty before first refresh)."""
        return self._snapshot

    # ── background scheduler ──────────────────────────────────────────
    async def _loop(self) -> None:
        while True:
            try:
                await self.refresh()
                payload = {"type": "snapshot", "data": self._snapshot.model_dump(mode="json")}
                delivered = await self.hub.broadcast(payload)
                logger.debug("OSINT snapshot broadcast to %d clients", delivered)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — scheduler must survive any cycle failure
                logger.error("OSINT refresh cycle failed: %s", exc)
            await asyncio.sleep(REFRESH_INTERVAL_S)

    def start_scheduler(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="osint-scheduler")
            logger.info("OSINT scheduler started (tick=%ss)", REFRESH_INTERVAL_S)

    async def stop_scheduler(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("OSINT scheduler stopped")
        self._task = None


@lru_cache(maxsize=1)
def get_aggregator() -> OsintAggregator:
    """Process-wide singleton aggregator."""
    return OsintAggregator()

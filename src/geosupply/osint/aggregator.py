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
import json
import logging
import os
import tempfile
from collections import deque
from functools import lru_cache
from pathlib import Path

import httpx

from geosupply.config import DATA_DIR
from geosupply.osint.bias import SourceBiasTracker
from geosupply.osint.hub import OsintHub
from geosupply.osint.intel import (
    apply_trends,
    build_highlights,
    compute_chokepoint_stress,
    compute_country_risk,
    compute_war_zones,
    detect_convergence,
    tag_entities,
)
from geosupply.osint.knowledge_graph import OsintKnowledgeGraph
from geosupply.osint.models import LearningStats, NewsItem, OsintEvent, OsintSnapshot
from geosupply.osint.projection import RiskProjector
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

REFRESH_INTERVAL_S = 120.0   # default tick; per-source TTLs gate real fetches
SURGE_INTERVAL_S = 60.0      # autonomous surge mode: flash activity detected
QUIET_INTERVAL_S = 300.0     # autonomous quiet mode: calm world, save quota
MAX_NEWS = 100
MAX_EVENTS = 250


def _state_path() -> Path:
    """Learning-state file (env-overridable so tests can isolate it)."""
    return Path(os.getenv("OSINT_STATE_PATH", str(DATA_DIR / "osint_learning.json")))


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
        # Pre-refresh snapshot already carries structural war-zone baselines
        self._snapshot: OsintSnapshot = OsintSnapshot(war_zones=compute_war_zones([]))
        self._refresh_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        # Trend history ring buffers (drift-vector style): last 12 cycles
        self._risk_history: deque[dict[str, float]] = deque(maxlen=12)
        self._choke_history: deque[dict[str, float]] = deque(maxlen=12)
        # Intelligence suite (all CPU, ₹0): KG + bias learning + projections
        self.kg = OsintKnowledgeGraph()
        self.bias = SourceBiasTracker()
        self.projector = RiskProjector()
        self._cycles = 0
        self._interval_s = REFRESH_INTERVAL_S
        self._surge = False

    # ── lifecycle ─────────────────────────────────────────────────────
    async def setup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(follow_redirects=True)
        self.load_state()

    async def teardown(self) -> None:
        await self.stop_scheduler()
        self.save_state()
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── learning-state persistence (survives restarts — autonomous) ───
    def save_state(self) -> None:
        state_path = _state_path()
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "kg": self.kg.to_state(),
                "bias": self.bias.to_state(),
                "projector": self.projector.to_state(),
                "cycles": self._cycles,
            }
            fd, tmp = tempfile.mkstemp(dir=str(state_path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, state_path)
        except OSError as exc:
            logger.warning("OSINT learning-state save failed: %s", exc)

    def load_state(self) -> None:
        state_path = _state_path()
        if not state_path.is_file():
            return
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("OSINT learning-state load failed: %s", exc)
            return
        self.kg.load_state(payload.get("kg") or [])
        self.bias.load_state(payload.get("bias") or {})
        self.projector.load_state(payload.get("projector") or {})
        try:
            self._cycles = int(payload.get("cycles", 0))
        except (TypeError, ValueError):
            self._cycles = 0
        logger.info("OSINT learning state restored (%d prior cycles)", self._cycles)

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

            # ── intelligence suite (CPU, ₹0) ──────────────────────────
            self.kg.decay()
            self.kg.observe(news)                        # live knowledge graph
            bias_profiles = self.bias.analyze(news)      # bias handler learns
            source_weights = {p.source: p.credibility for p in bias_profiles}

            chokepoints = compute_chokepoint_stress(events)
            risks = compute_country_risk(news, events, source_weights)
            apply_trends(risks, chokepoints,
                         list(self._risk_history), list(self._choke_history))
            forecasts = self.projector.observe({r.iso2: r.score for r in risks})
            for r in risks:
                r.projected_score = forecasts.get(r.iso2)
            war_zones = compute_war_zones(events)
            alerts = detect_convergence(events, chokepoints, ports_r.items)
            highlights = build_highlights(
                risks, chokepoints, events, ports_r.items, markets_r.items,
                alerts=alerts,
            )
            self._risk_history.append({r.iso2: r.score for r in risks})
            self._choke_history.append({c.id: c.stress_index for c in chokepoints})
            self._cycles += 1
            self._adapt_interval(alerts, news)

            self._snapshot = OsintSnapshot(
                alerts=alerts,
                events=events,
                news=news,
                markets=markets_r.items,
                chokepoints=chokepoints,
                country_risk=risks,
                india_ports=ports_r.items,
                highlights=highlights,
                war_zones=war_zones,
                graph_edges=self.kg.top_edges(15),
                source_bias=bias_profiles,
                learning=LearningStats(
                    cycles=self._cycles,
                    refresh_interval_s=self._interval_s,
                    surge_mode=self._surge,
                    projection_mae=self.projector.mae,
                    projection_samples=self.projector.samples,
                    kg_nodes=self.kg.node_count,
                    kg_edges=self.kg.edge_count,
                    penalised_sources=self.bias.penalised_count,
                ),
                health=[src.health() for src in self.sources],
                cost_inr=0.0,  # every source on this layer is free
            )
            if self._cycles % 5 == 0:
                self.save_state()
            return self._snapshot

    def _adapt_interval(self, alerts: list, news: list[NewsItem]) -> None:
        """Autonomous tempo: surge on flash activity, slow down when calm."""
        flash = sum(1 for n in news if n.priority == 3)
        if alerts or flash >= 3:
            self._surge, self._interval_s = True, SURGE_INTERVAL_S
        elif flash == 0 and not alerts and self._cycles > 3:
            self._surge, self._interval_s = False, QUIET_INTERVAL_S
        else:
            self._surge, self._interval_s = False, REFRESH_INTERVAL_S

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
            await asyncio.sleep(self._interval_s)

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

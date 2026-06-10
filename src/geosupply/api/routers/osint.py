"""
OSINT dashboard endpoints — REST snapshot + per-panel reads + live WebSocket.

The aggregator is the single writer; these endpoints are read-only views.
GET /osint/snapshot is the frontend's cold-start payload; /osint/ws streams
the same shape on every scheduler cycle.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from geosupply.osint.aggregator import OsintAggregator, get_aggregator
from geosupply.osint.models import (
    ChokepointStatus,
    ConvergenceAlert,
    CountryRisk,
    IntelHighlight,
    MarketQuote,
    NewsItem,
    OsintEvent,
    OsintSnapshot,
    PortStatus,
    SourceHealth,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def aggregator_dep() -> OsintAggregator:
    return get_aggregator()


@router.get("/snapshot", response_model=OsintSnapshot)
async def osint_snapshot(
    refresh: bool = Query(default=False, description="Force a TTL-gated refresh first"),
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Full dashboard payload. With ?refresh=true, refreshes stale sources first."""
    if refresh or not agg.snapshot().events and not agg.snapshot().news:
        await agg.refresh()
    return agg.snapshot()


@router.get("/events", response_model=list[OsintEvent])
async def osint_events(
    category: str | None = Query(default=None),
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Geolocated map events, optionally filtered by category."""
    events = agg.snapshot().events
    if category:
        events = [e for e in events if e.category == category]
    return events


@router.get("/news", response_model=list[NewsItem])
async def osint_news(
    min_priority: int = Query(default=0, ge=0, le=3),
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Live intel feed, optionally filtered by minimum priority band."""
    return [n for n in agg.snapshot().news if n.priority >= min_priority]


@router.get("/markets", response_model=list[MarketQuote])
async def osint_markets(agg: OsintAggregator = Depends(aggregator_dep)):
    return agg.snapshot().markets


@router.get("/chokepoints", response_model=list[ChokepointStatus])
async def osint_chokepoints(agg: OsintAggregator = Depends(aggregator_dep)):
    return agg.snapshot().chokepoints


@router.get("/risk", response_model=list[CountryRisk])
async def osint_risk(agg: OsintAggregator = Depends(aggregator_dep)):
    return agg.snapshot().country_risk


@router.get("/india/ports", response_model=list[PortStatus])
async def osint_india_ports(agg: OsintAggregator = Depends(aggregator_dep)):
    return agg.snapshot().india_ports


@router.get("/highlights", response_model=list[IntelHighlight])
async def osint_highlights(agg: OsintAggregator = Depends(aggregator_dep)):
    return agg.snapshot().highlights


@router.get("/alerts", response_model=list[ConvergenceAlert])
async def osint_alerts(agg: OsintAggregator = Depends(aggregator_dep)):
    """Multi-signal convergence alerts around chokepoints / Indian ports."""
    return agg.snapshot().alerts


@router.get("/sources/health", response_model=list[SourceHealth])
async def osint_sources_health(agg: OsintAggregator = Depends(aggregator_dep)):
    """Per-source breaker state, latency, last refresh (System panel)."""
    return [src.health() for src in agg.sources]


@router.websocket("/ws")
async def osint_ws(ws: WebSocket):
    """Live snapshot stream. Sends current snapshot on connect, then pushes."""
    agg = get_aggregator()
    await agg.hub.connect(ws)
    try:
        await ws.send_json({
            "type": "snapshot",
            "data": agg.snapshot().model_dump(mode="json"),
        })
        while True:
            # Client messages are keepalives/pings — protocol is server-push.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — boundary: log + clean disconnect
        logger.warning("OSINT WS error: %s", exc)
    finally:
        await agg.hub.disconnect(ws)

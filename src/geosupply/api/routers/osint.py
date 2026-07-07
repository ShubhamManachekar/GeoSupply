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
    FocusCountry,
    IntelAnswer,
    IntelHighlight,
    KGEdge,
    LiveStream,
    MarketQuote,
    NewsItem,
    OsintEvent,
    OsintSnapshot,
    PortStatus,
    SourceBias,
    SourceHealth,
    WarZone,
)
from pydantic import BaseModel, Field

from geosupply.osint.okf import answer_from_bundle, parse_frontmatter
from geosupply.osint.plans import PlanInfo, plan_info, require_feature
from geosupply.osint.rag_feedback import FeedbackEvent
from geosupply.osint.registry import COUNTRY_CENTROIDS, COUNTRY_GAZETTEER, LIVE_STREAMS

logger = logging.getLogger(__name__)

router = APIRouter()


async def aggregator_dep() -> OsintAggregator:
    return get_aggregator()


@router.get("/plan", response_model=PlanInfo)
async def osint_plan():
    """Active freemium plan + unlocked/locked features (frontend badge)."""
    return plan_info()


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


@router.get("/warzones", response_model=list[WarZone])
async def osint_warzones(agg: OsintAggregator = Depends(aggregator_dep)):
    """Active war / blockade / exclusion zones with live intensity."""
    return agg.snapshot().war_zones


@router.get("/graph", response_model=list[KGEdge],
            dependencies=[require_feature("advanced_intel")])
async def osint_graph(
    entity: str | None = Query(default=None),
    limit: int = Query(default=15, ge=1, le=100),
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Live knowledge-graph relations, optionally for one entity."""
    if entity:
        return agg.kg.edges_for(entity)[:limit]
    return agg.kg.top_edges(limit)


@router.get("/ask", response_model=IntelAnswer,
            dependencies=[require_feature("advanced_intel")])
async def osint_ask(
    q: str = Query(min_length=2, max_length=300),
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """OKF knowledge answering (replaces chunk-retrieval RAG).

    The query routes to matched OKF concept documents (frontmatter-first),
    which are loaded whole and composed into a cited answer. The feedback
    learner (thumbs ↑/↓) weights which facts enter the bundle, so answers
    still self-improve as users vote.
    """
    return answer_from_bundle(q, agg.ensure_okf_bundle(), agg.kg)


class FeedbackItem(BaseModel):
    """One citation vote — used by POST /osint/ask/feedback."""
    source: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="news", max_length=32)
    vote: int = Field(ge=-1, le=1)


class FeedbackRequest(BaseModel):
    """Batch of thumbs on citations from one /osint/ask response."""
    query: str = Field(default="", max_length=300)
    items: list[FeedbackItem] = Field(default_factory=list, max_length=32)


class FeedbackAck(BaseModel):
    accepted: int
    trained_sources: int


@router.post("/ask/feedback", response_model=FeedbackAck,
             dependencies=[require_feature("advanced_intel")])
async def osint_ask_feedback(
    payload: FeedbackRequest,
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Record user votes on RAG citations; reweights retrieval per source."""
    events = [FeedbackEvent(source=i.source, kind=i.kind, vote=i.vote)
              for i in payload.items]
    accepted = agg.rag_feedback.apply(events)
    if accepted:
        agg.save_state()
    return FeedbackAck(accepted=accepted,
                       trained_sources=agg.rag_feedback.trained_sources)


@router.get("/ask/feedback", response_model=list[dict],
            dependencies=[require_feature("advanced_intel")])
async def osint_ask_feedback_summary(
    agg: OsintAggregator = Depends(aggregator_dep),
):
    """Learned RAG source weights (top-N, only sources above min-votes gate)."""
    return agg.rag_feedback.summary()


@router.get("/okf", response_model=list[dict],
            dependencies=[require_feature("advanced_intel")])
async def osint_okf_index(agg: OsintAggregator = Depends(aggregator_dep)):
    """OKF 0.1 bundle listing — GeoSupply as an agent-consumable knowledge producer."""
    out = []
    agg.ensure_okf_bundle()
    for path, doc in sorted(agg.okf_bundle.items()):
        meta = parse_frontmatter(doc)
        out.append({"path": path, "type": meta.get("type", ""),
                    "title": meta.get("title", path),
                    "description": meta.get("description", ""),
                    "bytes": len(doc)})
    return out


@router.get("/okf/{doc_path:path}",
            dependencies=[require_feature("advanced_intel")])
async def osint_okf_document(doc_path: str,
                             agg: OsintAggregator = Depends(aggregator_dep)):
    """Serve one OKF concept document as raw markdown."""
    from fastapi import HTTPException
    from fastapi.responses import PlainTextResponse
    doc = agg.ensure_okf_bundle().get(doc_path)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no such concept: {doc_path}")
    return PlainTextResponse(doc, media_type="text/markdown")


@router.get("/sources/bias", response_model=list[SourceBias],
            dependencies=[require_feature("advanced_intel")])
async def osint_sources_bias(agg: OsintAggregator = Depends(aggregator_dep)):
    """News-analysis profiles with learned per-outlet credibility."""
    return agg.snapshot().source_bias


@router.get("/streams", response_model=list[LiveStream])
async def osint_streams(region: str | None = Query(default=None)):
    """Curated live news streams / public cams (official YouTube lives)."""
    streams = [
        LiveStream(
            id=s["id"], name=s["name"], kind=s["kind"], region=s["region"],
            embed_url=f"https://www.youtube.com/embed/live_stream?channel={s['channel_id']}",
        )
        for s in LIVE_STREAMS
    ]
    if region:
        streams = [s for s in streams if s.region == region.upper()]
    return streams


@router.get("/focus/countries", response_model=list[FocusCountry])
async def osint_focus_countries():
    """Focus-mode registry: countries with map centroids (India first)."""
    countries = [
        FocusCountry(iso2=iso2, name=COUNTRY_GAZETTEER[iso2][0],
                     lat=lat, lon=lon, zoom=zoom)
        for iso2, (lat, lon, zoom) in COUNTRY_CENTROIDS.items()
        if iso2 in COUNTRY_GAZETTEER
    ]
    countries.sort(key=lambda c: (c.iso2 != "IN", c.name))
    return countries


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

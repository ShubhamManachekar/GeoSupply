"""
GeoSupply AI — Playground API Router

Endpoints that power the live execution playground.

GET  /playground/topology          — Swarm topology as a node/edge graph
GET  /playground/stream            — SSE: global event stream (all traces)
GET  /playground/stream/{trace_id} — SSE: events for one trace only
GET  /playground/events            — Poll: buffered events since seq (non-SSE)
GET  /playground/agents            — All agent states (name, domain, state)
GET  /playground/routing-table     — Task-type → supervisor mapping
POST /playground/run               — Fire a task and get a trace_id back
POST /playground/run/supply-brief  — Run the full 10-step DAG
POST /playground/run/nlp           — Run NLP pipeline and stream results
DELETE /playground/trace/{trace_id} — Clear a trace from the ring buffer
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import StreamingResponse

from geosupply.api.dependencies import swarm_master_dep, budget_dep
from geosupply.core.trace_bus import TraceBus
from geosupply.schemas import TaskPacket

router = APIRouter()


def _bus() -> TraceBus:
    return TraceBus.get()


# ── GET /playground/topology ───────────────────────────────────────────────────

@router.get("/topology")
async def topology(sm=Depends(swarm_master_dep)):
    """
    Return the swarm as a graph (nodes + edges) for D3/vis.js rendering.
    Nodes: SwarmMaster, 14 supervisors, all agents.
    Edges: swarm→supervisor, supervisor→agent.
    """
    import geosupply.agents  # noqa: F401 — force registration
    from geosupply.core.base_agent import BaseAgent

    nodes: list[dict] = []
    edges: list[dict] = []

    # Root node
    nodes.append({"id": "SwarmMaster", "label": "SwarmMaster", "layer": "swarm", "group": "swarm"})

    # Supervisor nodes + edges from SwarmMaster
    sup_agents: dict[str, list[str]] = {}
    for sup_name, supervisor in sm._supervisor_registry.items():
        nodes.append({"id": sup_name, "label": sup_name.replace("Supervisor", "\nSup"),
                      "layer": "supervisor", "group": "supervisor"})
        edges.append({"from": "SwarmMaster", "to": sup_name, "label": ""})
        agent_names: list[str] = []
        if hasattr(supervisor, "_agents"):
            agent_names = list(supervisor._agents.keys())
        sup_agents[sup_name] = agent_names

    # Agent nodes + edges
    all_agents = {getattr(cls, "name", cls.__name__): cls for cls in BaseAgent.__subclasses__()}
    for sup_name, agent_names in sup_agents.items():
        for aname in agent_names:
            cls = all_agents.get(aname)
            domain = getattr(cls, "domain", "unknown") if cls else "unknown"
            nodes.append({"id": aname, "label": aname.replace("Agent", "\nAgt"),
                          "layer": "agent", "group": domain})
            edges.append({"from": sup_name, "to": aname, "label": ""})

    # Worker nodes (not connected to graph — shown as a capability list)
    import geosupply.workers  # noqa: F401
    from geosupply.core.base_worker import BaseWorker
    workers = [
        {
            "name": getattr(cls, "name", cls.__name__),
            "tier": getattr(cls, "tier", 0),
            "capabilities": sorted(getattr(cls, "capabilities", set())),
        }
        for cls in BaseWorker.__subclasses__()
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "workers": sorted(workers, key=lambda w: (w["tier"], w["name"])),
        "stats": {
            "supervisor_count": len(sm._supervisor_registry),
            "agent_count": len(all_agents),
            "worker_count": len(workers),
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    }


# ── GET /playground/agents ─────────────────────────────────────────────────────

@router.get("/agents")
async def agent_states():
    """Return live state for all registered agents."""
    import geosupply.agents  # noqa: F401
    from geosupply.core.base_agent import BaseAgent

    agents = []
    for cls in BaseAgent.__subclasses__():
        name = getattr(cls, "name", cls.__name__)
        domain = getattr(cls, "domain", "unknown")
        caps = sorted(getattr(cls, "capabilities", set()))
        agents.append({
            "name": name,
            "domain": domain,
            "capabilities": caps,
            "layer": "agent",
        })
    agents.sort(key=lambda a: (a["domain"], a["name"]))
    return {"count": len(agents), "agents": agents}


# ── GET /playground/routing-table ──────────────────────────────────────────────

@router.get("/routing-table")
async def routing_table():
    """Full ROUTING_TABLE — task_type → supervisor, tier, static."""
    from geosupply.orchestrator.swarm_master import ROUTING_TABLE
    rows = [
        {"task_type": k, "supervisor": v[0], "llm_tier": v[1], "use_static": v[2]}
        for k, v in sorted(ROUTING_TABLE.items())
    ]
    return {"count": len(rows), "routing_table": rows}


# ── GET /playground/stream ─────────────────────────────────────────────────────

@router.get("/stream")
async def stream_all(request: Request):
    """SSE: global real-time stream of ALL trace events from all active runs."""
    async def _gen():
        async for event in _bus().stream(trace_id="", replay=False):
            if await request.is_disconnected():
                break
            yield event.to_sse()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/stream/{trace_id}")
async def stream_trace(trace_id: str, request: Request, replay: bool = Query(True)):
    """SSE: events for a specific trace_id (with optional replay of buffered history)."""
    async def _gen():
        async for event in _bus().stream(trace_id=trace_id, replay=replay):
            if await request.is_disconnected():
                break
            yield event.to_sse()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── GET /playground/events ─────────────────────────────────────────────────────

@router.get("/events")
async def poll_events(
    trace_id: str = Query("", description="Filter by trace_id (empty = all)"),
    since_seq: int = Query(0, description="Return events with seq > this value"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Non-SSE polling endpoint for clients that can't consume SSE (e.g. Streamlit).
    Returns buffered events since the given sequence number.
    """
    events = _bus().drain(trace_id=trace_id, since_seq=since_seq, limit=limit)
    max_seq = max((e["seq"] for e in events), default=since_seq)
    return {
        "trace_id": trace_id,
        "since_seq": since_seq,
        "next_seq": max_seq,
        "count": len(events),
        "events": events,
    }


# ── POST /playground/run ───────────────────────────────────────────────────────

@router.post("/run")
async def run_task(
    background_tasks: BackgroundTasks,
    task_type: str = Query(..., description="e.g. NLP_SENTIMENT, CLAIM_VERIFY, SANCTIONS_CHECK"),
    payload: dict = None,
    sm=Depends(swarm_master_dep),
    budget=Depends(budget_dep),
):
    """
    Fire any task type at the swarm. Returns immediately with a trace_id.
    Connect to GET /playground/stream/{trace_id} to watch execution live.
    """
    if payload is None:
        payload = {}

    trace_id = str(uuid.uuid4())[:8]
    payload["trace_id"] = trace_id

    bus = _bus()
    bus.emit("swarm", "submitted", "SwarmMaster",
             trace_id=trace_id, status="running",
             input_summary=f"task_type={task_type}")

    async def _run():
        try:
            packet = TaskPacket(
                task_id=trace_id,
                task_type=task_type,
                payload=payload,
                trace_id=trace_id,
            )
            await sm.route(packet)
        except Exception as exc:
            bus.emit("swarm", "error", "SwarmMaster",
                     trace_id=trace_id, status="error", error_msg=str(exc))

    background_tasks.add_task(_run)

    return {
        "trace_id": trace_id,
        "task_type": task_type,
        "stream_url": f"/playground/stream/{trace_id}",
        "poll_url": f"/playground/events?trace_id={trace_id}",
        "message": "Task queued. Connect to stream_url for live events.",
    }


# ── POST /playground/run/supply-brief ─────────────────────────────────────────

@router.post("/run/supply-brief")
async def run_supply_brief(
    background_tasks: BackgroundTasks,
    topic: str = Query(...),
    source_credibility: float = Query(0.8, ge=0.0, le=1.0),
    sm=Depends(swarm_master_dep),
):
    """
    Run the full 10-step supply brief DAG.
    Returns trace_id immediately — stream events at /playground/stream/{trace_id}.
    """
    trace_id = str(uuid.uuid4())[:8]
    payload = {"topic": topic, "source_credibility": source_credibility, "trace_id": trace_id}
    bus = _bus()
    bus.emit("swarm", "brief_queued", "SwarmMaster",
             trace_id=trace_id, status="running",
             input_summary=f"topic={topic[:60]}")

    async def _run():
        try:
            await sm.run_supply_brief(payload, plan_id=trace_id)
        except Exception as exc:
            bus.emit("swarm", "error", "SwarmMaster",
                     trace_id=trace_id, status="error", error_msg=str(exc))

    background_tasks.add_task(_run)
    return {
        "trace_id": trace_id,
        "topic": topic,
        "stream_url": f"/playground/stream/{trace_id}",
        "poll_url": f"/playground/events?trace_id={trace_id}",
    }


# ── POST /playground/run/nlp ───────────────────────────────────────────────────

@router.post("/run/nlp")
async def run_nlp(
    background_tasks: BackgroundTasks,
    text: str = Query(..., description="Text to analyse"),
):
    """
    Run the three-worker NLP pipeline (sentiment + NER + claims) concurrently.
    Returns trace_id — stream at /playground/stream/{trace_id}.
    """
    trace_id = str(uuid.uuid4())[:8]
    bus = _bus()
    bus.emit("swarm", "nlp_queued", "SwarmMaster",
             trace_id=trace_id, status="running",
             input_summary=text[:80])

    async def _run():
        from geosupply.workers.sentiment_worker import SentimentWorker
        from geosupply.workers.ner_worker import NERWorker
        from geosupply.workers.claim_worker import ClaimWorker
        inp = {"text": text, "trace_id": trace_id}
        try:
            await asyncio.gather(
                SentimentWorker().process(inp),
                NERWorker().process(inp),
                ClaimWorker().process(inp),
            )
            bus.emit("swarm", "nlp_complete", "SwarmMaster",
                     trace_id=trace_id, status="ok",
                     output_summary="sentiment + NER + claims done")
        except Exception as exc:
            bus.emit("swarm", "error", "SwarmMaster",
                     trace_id=trace_id, status="error", error_msg=str(exc))

    background_tasks.add_task(_run)
    return {"trace_id": trace_id, "stream_url": f"/playground/stream/{trace_id}",
            "poll_url": f"/playground/events?trace_id={trace_id}"}


# ── DELETE /playground/trace/{trace_id} ───────────────────────────────────────

@router.delete("/trace/{trace_id}")
async def clear_trace(trace_id: str):
    """Remove all buffered events for a trace_id from the ring buffer."""
    removed = _bus().clear_trace(trace_id)
    return {"trace_id": trace_id, "events_removed": removed}

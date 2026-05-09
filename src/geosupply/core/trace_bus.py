"""
GeoSupply AI — TraceBus (Observability Event Bus)

A lightweight in-process async pub/sub for real-time execution tracing.
Every layer of the swarm (SwarmMaster → Supervisor → Agent → Worker) emits
structured TraceEvent objects here. The playground API drains them over SSE.

Completely separate from EventBus (which handles cross-agent domain events).
TraceBus is observability-only — read by dashboards, never acted upon.

Architecture:
    Any layer          →  TraceBus.emit()   → asyncio.Queue (unbounded*)
    SSE endpoint       →  TraceBus.stream() → yields JSON lines
    Playground poller  →  TraceBus.drain()  → returns buffered list

*Soft cap: oldest events dropped when queue exceeds MAX_EVENTS to bound memory.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator

MAX_EVENTS = 5_000      # ring-buffer cap (oldest dropped when full)
SSE_POLL_INTERVAL = 0.1  # seconds between queue polls in stream()


@dataclass
class TraceEvent:
    """A single observable event emitted by any swarm layer."""

    # ── Identity ──────────────────────────────────────────────────────────────
    event_id:   str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id:   str = ""           # propagated through the call chain
    seq:        int = 0            # monotonic sequence per trace_id

    # ── Classification ────────────────────────────────────────────────────────
    layer: str = "unknown"         # swarm | supervisor | agent | worker | subagent
    event_type: str = "info"       # start | complete | error | state_change | cost | route

    # ── Source ────────────────────────────────────────────────────────────────
    name:   str = ""               # e.g. "VerifierWorker", "NLPSupervisor"
    domain: str = ""               # e.g. "nlp", "quality"

    # ── Status & Timing ───────────────────────────────────────────────────────
    status:      str   = "ok"      # running | ok | error | skipped | blocked
    duration_ms: float = 0.0
    cost_inr:    float = 0.0

    # ── Payload summaries (never full data — keeps events small) ─────────────
    input_summary:  str = ""
    output_summary: str = ""
    error_msg:      str = ""

    # ── Timestamp ─────────────────────────────────────────────────────────────
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_sse(self) -> str:
        """Encode as Server-Sent Event wire format."""
        import json
        return f"data: {json.dumps(asdict(self))}\n\n"

    def to_dict(self) -> dict:
        return asdict(self)


class TraceBus:
    """
    Singleton in-process trace event bus.

    Usage:
        bus = TraceBus.get()
        bus.emit("worker", "start", "VerifierWorker", trace_id="t1", ...)
        async for event in bus.stream(trace_id="t1"):
            yield event.to_sse()
    """

    _instance: "TraceBus | None" = None

    def __init__(self) -> None:
        # Ring buffer (deque with maxlen) for historical replay
        self._ring: deque[TraceEvent] = deque(maxlen=MAX_EVENTS)
        # Live listeners: each SSE client gets its own asyncio.Queue
        self._listeners: list[asyncio.Queue[TraceEvent | None]] = []
        # Per-trace sequence counters
        self._seq: dict[str, int] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "TraceBus":
        """Return the process-level singleton, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for tests)."""
        cls._instance = None

    # ── Emit ─────────────────────────────────────────────────────────────────

    def emit(
        self,
        layer: str,
        event_type: str,
        name: str,
        *,
        trace_id: str = "",
        domain: str = "",
        status: str = "ok",
        duration_ms: float = 0.0,
        cost_inr: float = 0.0,
        input_summary: str = "",
        output_summary: str = "",
        error_msg: str = "",
    ) -> TraceEvent:
        """Emit a trace event — non-blocking, safe to call from sync or async code."""
        seq = self._seq.get(trace_id, 0) + 1
        self._seq[trace_id] = seq

        event = TraceEvent(
            trace_id=trace_id,
            seq=seq,
            layer=layer,
            event_type=event_type,
            name=name,
            domain=domain,
            status=status,
            duration_ms=round(duration_ms, 2),
            cost_inr=round(cost_inr, 6),
            input_summary=input_summary[:120],
            output_summary=output_summary[:120],
            error_msg=error_msg[:200],
        )

        # Store in ring buffer
        self._ring.append(event)

        # Fan out to all live listeners
        for q in self._listeners:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow client — drop event rather than block

        return event

    # ── Stream (SSE) ─────────────────────────────────────────────────────────

    async def stream(
        self,
        trace_id: str = "",
        replay: bool = True,
    ) -> AsyncGenerator[TraceEvent, None]:
        """
        Async generator that yields TraceEvents in real time.

        Args:
            trace_id: Only yield events matching this trace_id.
                      Empty string = yield ALL events (global stream).
            replay:   If True, first replay buffered events matching the filter,
                      then switch to live events.
        """
        q: asyncio.Queue[TraceEvent | None] = asyncio.Queue(maxsize=1000)
        self._listeners.append(q)

        try:
            # Replay historical events from ring buffer
            if replay:
                for event in list(self._ring):
                    if not trace_id or event.trace_id == trace_id:
                        yield event

            # Live stream
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Yield a keepalive comment — clients see this as heartbeat
                    yield TraceEvent(
                        layer="bus", event_type="heartbeat",
                        name="TraceBus", trace_id=trace_id,
                        output_summary="keepalive",
                    )
                    continue

                if event is None:
                    break  # sentinel — stream closed
                if not trace_id or event.trace_id == trace_id:
                    yield event

        finally:
            self._listeners.remove(q)

    # ── Drain (polling) ───────────────────────────────────────────────────────

    def drain(
        self,
        trace_id: str = "",
        since_seq: int = 0,
        limit: int = 200,
    ) -> list[dict]:
        """
        Non-blocking poll: return buffered events newer than since_seq.
        Used by the Streamlit playground (which can't consume SSE natively).
        """
        results = []
        for event in self._ring:
            if trace_id and event.trace_id != trace_id:
                continue
            if event.seq <= since_seq:
                continue
            results.append(event.to_dict())
            if len(results) >= limit:
                break
        return results

    def clear_trace(self, trace_id: str) -> int:
        """Remove all events for a trace_id from the ring buffer. Returns count."""
        before = len(self._ring)
        kept = [e for e in self._ring if e.trace_id != trace_id]
        self._ring.clear()
        self._ring.extend(kept)
        return before - len(self._ring)

    def close(self) -> None:
        """Signal all SSE streams to terminate."""
        for q in self._listeners:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass

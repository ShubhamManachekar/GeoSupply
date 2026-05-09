"""
GeoSupply AI — Tracer (Non-invasive swarm instrumentation)

Patches BaseWorker.process(), BaseAgent.execute(), BaseSupervisor.dispatch(),
and SwarmMaster.route() with thin wrappers that emit TraceEvents to TraceBus
WITHOUT changing any existing signatures or return types.

Activation (called once at startup):
    from geosupply.core.tracer import install_tracer
    install_tracer()

After install_tracer(), every call through any layer automatically emits:
    ┌─────────────────────────────────────────────────────────────────────┐
    │ layer=swarm      event=route      SwarmMaster routes a TaskPacket   │
    │ layer=supervisor event=start/end  BaseSupervisor.dispatch()         │
    │ layer=agent      event=start/end  BaseAgent.execute()               │
    │ layer=worker     event=start/end  BaseWorker.process()              │
    │ layer=subagent   event=start/end  BaseSubAgent.run()                │
    └─────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import time
import logging
import functools
from typing import Any

logger = logging.getLogger(__name__)

_INSTALLED = False


def _truncate(val: Any, n: int = 100) -> str:
    """Safe string truncation of any value."""
    try:
        s = str(val)
        return s[:n] + "…" if len(s) > n else s
    except Exception:
        return ""


def _extract_trace_id(args: tuple, kwargs: dict) -> str:
    """Try to find trace_id from call arguments (dict, TaskPacket, or kwarg)."""
    # Direct kwarg
    if "trace_id" in kwargs:
        return str(kwargs["trace_id"])
    # First positional arg — could be dict or TaskPacket
    for arg in args:
        if isinstance(arg, dict):
            tid = arg.get("trace_id") or arg.get("payload", {}).get("trace_id", "")
            if tid:
                return str(tid)
        elif hasattr(arg, "trace_id"):
            return str(arg.trace_id)
    return "global"


def _input_summary(args: tuple, kwargs: dict) -> str:
    """Build a short human-readable input summary."""
    for arg in args:
        if isinstance(arg, dict):
            text = arg.get("text") or arg.get("query") or arg.get("claim_text") or arg.get("topic", "")
            if text:
                return _truncate(text, 80)
            task_type = arg.get("task_type") or arg.get("compound_task_type", "")
            if task_type:
                return f"task_type={task_type}"
        elif hasattr(arg, "task_type"):
            return f"task_type={arg.task_type}"
    return _truncate(str(args)[:80])


def _output_summary(result: Any) -> str:
    """Build a short human-readable output summary."""
    if isinstance(result, dict):
        r = result.get("result", result)
        if isinstance(r, dict):
            # Common output patterns
            for key in ("verdict", "brief_text", "tweet", "prediction", "translated_text",
                        "polarity", "status", "risk_level", "cluster_count"):
                if key in r:
                    return f"{key}={_truncate(str(r[key]), 60)}"
            claims = r.get("claims", [])
            if claims:
                return f"claims={len(claims)}"
            entities = r.get("entities", [])
            if entities:
                return f"entities={len(entities)}"
        return _truncate(str(r)[:80])
    return _truncate(str(result)[:80])


def _wrap_async(fn, layer: str, get_name, domain: str = "") -> Any:
    """
    Return an async wrapper around fn that emits start/complete/error events.
    get_name(self) → str
    """
    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        from geosupply.core.trace_bus import TraceBus
        bus = TraceBus.get()

        name = get_name(self)
        trace_id = _extract_trace_id(args, kwargs)
        inp = _input_summary(args, kwargs)

        bus.emit(
            layer, "start", name,
            trace_id=trace_id,
            domain=getattr(self, "domain", domain),
            status="running",
            input_summary=inp,
        )

        t0 = time.perf_counter()
        try:
            result = await fn(self, *args, **kwargs)
            duration_ms = (time.perf_counter() - t0) * 1000
            cost_inr = 0.0
            if isinstance(result, dict):
                cost_inr = result.get("meta", {}).get("cost_inr", 0.0) or 0.0

            bus.emit(
                layer, "complete", name,
                trace_id=trace_id,
                domain=getattr(self, "domain", domain),
                status="ok",
                duration_ms=duration_ms,
                cost_inr=cost_inr,
                input_summary=inp,
                output_summary=_output_summary(result),
            )
            return result

        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            bus.emit(
                layer, "error", name,
                trace_id=trace_id,
                domain=getattr(self, "domain", domain),
                status="error",
                duration_ms=duration_ms,
                input_summary=inp,
                error_msg=str(exc)[:200],
            )
            raise

    return wrapper


def install_tracer() -> bool:
    """
    Patch all four base classes with trace-emitting wrappers.
    Safe to call multiple times — only installs once per process.
    Returns True if newly installed, False if already active.
    """
    global _INSTALLED
    if _INSTALLED:
        return False

    try:
        from geosupply.core.base_worker import BaseWorker
        from geosupply.core.base_agent import BaseAgent
        from geosupply.core.base_supervisor import BaseSupervisor
        from geosupply.core.base_subagent import BaseSubAgent
        from geosupply.orchestrator.swarm_master import SwarmMaster

        # ── BaseWorker.process ────────────────────────────────────────────────
        BaseWorker.process = _wrap_async(
            BaseWorker.process,
            layer="worker",
            get_name=lambda self: getattr(self, "name", self.__class__.__name__),
        )
        # Also wrap safe_process so individual retries are visible
        _orig_safe = BaseWorker.safe_process

        @functools.wraps(_orig_safe)
        async def _traced_safe(self, input_data: dict) -> dict:
            from geosupply.core.trace_bus import TraceBus
            TraceBus.get().emit(
                "worker", "retry_check",
                getattr(self, "name", self.__class__.__name__),
                trace_id=input_data.get("trace_id", "global"),
                status="running",
                input_summary=_input_summary((input_data,), {}),
            )
            return await _orig_safe(self, input_data)

        BaseWorker.safe_process = _traced_safe

        # ── BaseAgent.execute ─────────────────────────────────────────────────
        BaseAgent.execute = _wrap_async(
            BaseAgent.execute,
            layer="agent",
            get_name=lambda self: getattr(self, "name", self.__class__.__name__),
        )

        # ── BaseSupervisor.dispatch ───────────────────────────────────────────
        BaseSupervisor.dispatch = _wrap_async(
            BaseSupervisor.dispatch,
            layer="supervisor",
            get_name=lambda self: getattr(self, "name", self.__class__.__name__),
        )

        # ── BaseSubAgent.run ──────────────────────────────────────────────────
        BaseSubAgent.run = _wrap_async(
            BaseSubAgent.run,
            layer="subagent",
            get_name=lambda self: getattr(self, "name", self.__class__.__name__),
        )

        # ── SwarmMaster.route ─────────────────────────────────────────────────
        _orig_route = SwarmMaster.route

        @functools.wraps(_orig_route)
        async def _traced_route(self, task, supervisor_registry=None):
            from geosupply.core.trace_bus import TraceBus
            from geosupply.orchestrator.swarm_master import ROUTING_TABLE

            bus = TraceBus.get()
            trace_id = getattr(task, "trace_id", "") or ""
            task_type = getattr(task, "task_type", str(task))
            supervisor_name = ROUTING_TABLE.get(task_type, ("?", 0, False))[0]

            bus.emit(
                "swarm", "route", "SwarmMaster",
                trace_id=trace_id,
                status="running",
                input_summary=f"task_type={task_type} → {supervisor_name}",
            )

            t0 = time.perf_counter()
            try:
                result = await _orig_route(self, task, supervisor_registry)
                duration_ms = (time.perf_counter() - t0) * 1000
                cost_inr = result.get("cost_inr", 0.0) if isinstance(result, dict) else 0.0
                bus.emit(
                    "swarm", "routed", "SwarmMaster",
                    trace_id=trace_id,
                    status="ok",
                    duration_ms=duration_ms,
                    cost_inr=cost_inr,
                    output_summary=_output_summary(result),
                )
                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - t0) * 1000
                bus.emit(
                    "swarm", "error", "SwarmMaster",
                    trace_id=trace_id,
                    status="error",
                    duration_ms=duration_ms,
                    error_msg=str(exc),
                )
                raise

        SwarmMaster.route = _traced_route

        # ── SwarmMaster.run_supply_brief ──────────────────────────────────────
        _orig_brief = SwarmMaster.run_supply_brief

        @functools.wraps(_orig_brief)
        async def _traced_brief(self, payload, plan_id=None):
            from geosupply.core.trace_bus import TraceBus
            bus = TraceBus.get()
            trace_id = payload.get("trace_id", plan_id or "brief")
            bus.emit(
                "swarm", "dag_start", "SwarmMaster",
                trace_id=trace_id,
                status="running",
                input_summary=f"topic={payload.get('topic', '')[:60]}",
            )
            t0 = time.perf_counter()
            result = await _orig_brief(self, payload, plan_id)
            duration_ms = (time.perf_counter() - t0) * 1000
            cost = result.get("total_cost_inr", 0.0)
            bus.emit(
                "swarm", "dag_complete", "SwarmMaster",
                trace_id=trace_id,
                status="ok",
                duration_ms=duration_ms,
                cost_inr=cost,
                output_summary=f"plan_id={result.get('plan_id')} tasks={len(result.get('task_results', {}))}",
            )
            return result

        SwarmMaster.run_supply_brief = _traced_brief

        _INSTALLED = True
        logger.info("Tracer installed — all swarm layers instrumented")
        return True

    except Exception as exc:
        logger.warning("Tracer installation failed (non-fatal): %s", exc)
        return False


def is_installed() -> bool:
    return _INSTALLED

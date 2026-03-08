"""
TimelineGeneratorAgent — Builds chronological event graphs and derives hidden trends
Part of: GeoSupply AI FA v2
Layer: 3 (Agent)
Group: B — Intelligence & Knowledge
Phase: 6
"""

from datetime import datetime, timezone
from typing import Literal
from geosupply.core.base_agent import BaseAgent
from geosupply.core.decorators import tracer, cost_tracker, internal_breaker
from geosupply.schemas import GeoEventRecord, GeoEventTimeline, TimelineNode


class InvalidStateTransition(Exception):
    pass


class TimelineGeneratorAgent(BaseAgent):
    """
    Parses GeoEventRecords from EventExtractorWorker to build chronological
    and spatial event graphs. Identifies hidden trends.

    DOMAIN: Predictive Intelligence / Chronology
    CAPABILITIES: TIMELINE_GRAPH, TREND_DETECTION
    MANAGES: EventExtractorWorker (indirectly via SwarmMaster tasks)
    """

    name = "TimelineGeneratorAgent"
    domain = "Predictive Intelligence"
    capabilities = {"TIMELINE_GRAPH", "TREND_DETECTION"}
    max_concurrent = 3
    _state: Literal["IDLE", "BUSY", "DONE", "ERROR", "RECOVERY"] = "IDLE"

    # FA v1 G2: State transition guards
    _VALID_TRANSITIONS = {
        "IDLE":     {"BUSY"},
        "BUSY":     {"DONE", "ERROR"},
        "DONE":     {"IDLE"},
        "ERROR":    {"RECOVERY"},
        "RECOVERY": {"IDLE"},
    }

    def _transition(self, new_state: str) -> None:
        if new_state not in self._VALID_TRANSITIONS.get(self._state, set()):
            raise InvalidStateTransition(
                f"{self.name}: {self._state} → {new_state} not allowed"
            )
        self._prev_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.now(timezone.utc)

    def advertise_capabilities(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "capabilities": list(self.capabilities),
            "cost_per_call_inr": 0.15,
            "avg_latency_ms": 2500,
        }

    @tracer
    @cost_tracker
    @internal_breaker(timeout_s=30, max_failures=3)
    async def execute(self, task: dict) -> dict:
        """Main execution entry point."""
        self._transition("BUSY")
        try:
            result = await self._do_work(task)
            self._transition("DONE")
            self._transition("IDLE")
            return result
        except Exception as e:
            self._transition("ERROR")
            self._transition("RECOVERY")
            # Recovery logic could go here (e.g. notify supervisor)
            self._transition("IDLE")
            return {"error": str(e), "cost_inr": 0.0}

    async def _do_work(self, task: dict) -> dict:
        """
        Builds the Timeline logic. Assumes task['events'] is a list of dicts matching GeoEventRecord.
        """
        raw_events = task.get("events", [])
        if not raw_events:
            raise ValueError("No events provided for timeline generation")

        events = []
        for e in raw_events:
            if isinstance(e, dict):
                events.append(GeoEventRecord(**e))
            elif isinstance(e, GeoEventRecord):
                events.append(e)

        if not events:
            raise ValueError("Events could not be parsed to GeoEventRecord")

        # Sort chronologically
        events.sort(key=lambda x: x.date_occurred)

        # Build basic trend narrative and nodes
        trend_keyword = "Escalation" if "WAR" in [e.event_type for e in events] else "Instability"
        
        nodes = []
        for i, event in enumerate(events):
            # Define simple relationship links between adjacent chronological events
            related_ids = []
            if i > 0:
                related_ids.append(f"Event-{i-1}")
            if i < len(events) - 1:
                related_ids.append(f"Event-{i+1}")
                
            nodes.append(TimelineNode(
                event=event,
                related_events=related_ids
            ))

        timeline = GeoEventTimeline(
            timeline_name=task.get("timeline_name", f"Timeline_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"),
            nodes=nodes,
            identified_trend=f"Analyzed {len(events)} sequential events indicating overall {trend_keyword}."
        )

        return {
            "result": timeline.model_dump(),
            "meta": {
                "agent": self.name,
                "cost_inr": 0.15,
                "events_processed": len(events),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

"""
WatchdogSubAgent — Layer 4 SubAgent
FA v2 | Part III | Rule 10: every agent has a watchdog.

Polls registered agents' state every cycle, detects stuck/errored agents,
publishes WatchdogAlert events to 'watchdog.alert' topic via EventBus,
and returns a summary of all alerts raised.

Alert conditions:
  STUCK_BUSY:   agent has been BUSY > STUCK_BUSY_THRESHOLD_S seconds
  STUCK_ERROR:  agent has been in ERROR > STUCK_ERROR_THRESHOLD_S seconds
  UNREACHABLE:  agent.state raises an exception
  RECOVERED:    previously alerted agent is now IDLE again
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import WatchdogAlert

logger = logging.getLogger(__name__)

# Thresholds (seconds)
STUCK_BUSY_THRESHOLD_S: int = 300    # 5 minutes
STUCK_ERROR_THRESHOLD_S: int = 60    # 1 minute


class WatchdogSubAgent(BaseSubAgent):
    """
    Monitors all registered BaseAgent instances.

    PIPELINE:
        poll_agents → classify_alerts → publish_alerts

    ESCALATION:
        Publishes WatchdogAlert on 'watchdog.alert' EventBus topic.
        InfraSupervisor subscribes and triggers agent restart.

    USAGE:
        watchdog = WatchdogSubAgent()
        await watchdog.setup()
        watchdog.register_agent(logging_agent)
        result = await watchdog.run({"trace_id": "wdg-001"})
    """

    name = "WatchdogSubAgent"
    pipeline_steps = ["poll_agents", "classify_alerts", "publish_alerts"]

    def __init__(self) -> None:
        self._registered_agents: dict[str, object] = {}
        # agent_name → datetime when it entered current state
        self._state_entered_at: dict[str, datetime] = {}
        # agent_name → last known state (for RECOVERED detection)
        self._last_known_state: dict[str, str] = {}
        # set of agent names currently under alert
        self._alerted_agents: set[str] = set()
        self._event_bus = None
        self._total_alerts_raised: int = 0

    def register_agent(self, agent: object, event_bus: object = None) -> None:
        """Register an agent for watchdog monitoring."""
        name = getattr(agent, "name", str(agent))
        self._registered_agents[name] = agent
        self._state_entered_at[name] = datetime.now(timezone.utc)
        self._last_known_state[name] = "IDLE"
        if event_bus is not None:
            self._event_bus = event_bus
        logger.debug("WatchdogSubAgent: monitoring %s", name)

    def unregister_agent(self, agent_name: str) -> None:
        """Remove an agent from watchdog monitoring."""
        self._registered_agents.pop(agent_name, None)
        self._state_entered_at.pop(agent_name, None)
        self._last_known_state.pop(agent_name, None)
        self._alerted_agents.discard(agent_name)

    # ── Pipeline steps ─────────────────────────────────────────────────────

    def _poll_agents(self) -> dict[str, str]:
        """Step 1: Read state from every registered agent. Returns name → state."""
        states: dict[str, str] = {}
        for name, agent in self._registered_agents.items():
            try:
                states[name] = getattr(agent, "state", "UNKNOWN")
            except Exception:
                states[name] = "UNREACHABLE"
        return states

    def _classify_alerts(
        self, states: dict[str, str]
    ) -> list[WatchdogAlert]:
        """Step 2: Compare states against thresholds → build alert list."""
        now = datetime.now(timezone.utc)
        alerts: list[WatchdogAlert] = []

        for name, state in states.items():
            prev_state = self._last_known_state.get(name, "IDLE")

            # Track state entry time on transition
            if state != prev_state:
                self._state_entered_at[name] = now
                self._last_known_state[name] = state

            # RECOVERED: was alerted, now IDLE again
            if name in self._alerted_agents and state == "IDLE":
                self._alerted_agents.discard(name)
                alerts.append(WatchdogAlert(
                    agent_name=name,
                    alert_type="RECOVERED",
                    state_at_alert="IDLE",
                    stuck_duration_s=0.0,
                ))
                continue

            # Already alerted — skip re-alerting
            if name in self._alerted_agents:
                continue

            entered_at = self._state_entered_at.get(name, now)
            duration_s = (now - entered_at).total_seconds()

            if state == "UNREACHABLE":
                self._alerted_agents.add(name)
                alerts.append(WatchdogAlert(
                    agent_name=name,
                    alert_type="UNREACHABLE",
                    state_at_alert=state,
                    stuck_duration_s=duration_s,
                ))
            elif state == "BUSY" and duration_s > STUCK_BUSY_THRESHOLD_S:
                self._alerted_agents.add(name)
                alerts.append(WatchdogAlert(
                    agent_name=name,
                    alert_type="STUCK_BUSY",
                    state_at_alert=state,
                    stuck_duration_s=duration_s,
                ))
            elif state == "ERROR" and duration_s > STUCK_ERROR_THRESHOLD_S:
                self._alerted_agents.add(name)
                alerts.append(WatchdogAlert(
                    agent_name=name,
                    alert_type="STUCK_ERROR",
                    state_at_alert=state,
                    stuck_duration_s=duration_s,
                ))

        return alerts

    async def _publish_alerts(
        self, alerts: list[WatchdogAlert], trace_id: str
    ) -> int:
        """Step 3: Publish each alert to EventBus 'watchdog.alert' topic."""
        if not alerts or self._event_bus is None:
            return 0

        from geosupply.schemas import Event

        published = 0
        for alert in alerts:
            alert.trace_id = trace_id
            event = Event(
                topic="watchdog.alert",
                source=self.name,
                payload=alert.model_dump(mode="json"),
            )
            try:
                await self._event_bus.publish(event, skip_verification=True)
                published += 1
            except Exception as exc:
                logger.error("WatchdogSubAgent: failed to publish alert: %s", exc)

        self._total_alerts_raised += published
        return published

    # ── BaseSubAgent interface ─────────────────────────────────────────────

    async def run(self, input_data: dict) -> dict:
        """
        Run one watchdog cycle.

        Input:  {"trace_id": str}
        Output: {"result": {"alerts": [...], "agents_monitored": N}, "meta": {...}}
        """
        trace_id = input_data.get("trace_id", "wdg-unknown")

        states = self._poll_agents()
        alerts = self._classify_alerts(states)
        published = await self._publish_alerts(alerts, trace_id)

        alert_dicts = [a.model_dump(mode="json") for a in alerts]

        if alerts:
            logger.warning(
                "WatchdogSubAgent: %d alert(s) raised [trace=%s]: %s",
                len(alerts),
                trace_id,
                [a["alert_type"] + ":" + a["agent_name"] for a in alert_dicts],
            )

        return {
            "result": {
                "alerts": alert_dicts,
                "alert_count": len(alerts),
                "agents_monitored": len(self._registered_agents),
                "agent_states": states,
                "published": published,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
            },
        }

    @property
    def stats(self) -> dict:
        return {
            "agents_monitored": len(self._registered_agents),
            "total_alerts_raised": self._total_alerts_raised,
            "currently_alerted": sorted(self._alerted_agents),
        }

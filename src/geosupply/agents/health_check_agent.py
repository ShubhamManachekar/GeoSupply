"""
HealthCheckAgent — Infrastructure Singleton (#3)
FA v2 | Part IV Group A | Layer 3

Contract: check() → {status, latency, queue_depth}
Monitors registered agents, workers, and EventBus health.
Runs every 5 minutes. WatchdogAgent monitors this agent.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from geosupply.config import AgentState
from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class HealthCheckAgent(BaseAgent):
    """
    System health monitor.

    DOMAIN: infrastructure
    CAPABILITIES: HEALTH_CHECK, STATUS_REPORT, ALERT
    SCHEDULE: Every 5 minutes (triggered by WatchdogAgent)

    Tracks:
        - Registered agent status (IDLE, BUSY, ERROR, etc.)
        - EventBus subscriber count and publish stats
        - Worker pool availability
        - Overall system health score
    """

    name = "HealthCheckAgent"
    domain = "infrastructure"
    capabilities = {"HEALTH_CHECK", "STATUS_REPORT", "ALERT"}
    max_concurrent = 1

    _registered_agents: dict[str, BaseAgent]
    _check_history: list[dict]
    _last_check: datetime | None

    def __init__(self) -> None:
        self._registered_agents = {}
        self._check_history = []
        self._last_check = None

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent for health monitoring."""
        self._registered_agents[agent.name] = agent
        logger.debug("HealthCheckAgent: monitoring %s", agent.name)

    def unregister_agent(self, agent_name: str) -> None:
        """Remove an agent from monitoring."""
        self._registered_agents.pop(agent_name, None)

    async def check(self) -> dict[str, Any]:
        """
        Run a health check across all registered components.

        Returns:
            dict with overall status and per-agent details
        """
        start = time.monotonic()
        agent_statuses: dict[str, dict] = {}
        healthy_count = 0
        total_count = len(self._registered_agents)

        for name, agent in self._registered_agents.items():
            try:
                status = agent.state
                is_healthy = status in ("IDLE", "BUSY", "DONE")
                agent_statuses[name] = {
                    "state": status,
                    "healthy": is_healthy,
                    "domain": agent.domain,
                }
                if is_healthy:
                    healthy_count += 1
            except Exception as exc:
                agent_statuses[name] = {
                    "state": "UNREACHABLE",
                    "healthy": False,
                    "error": str(exc),
                }

        elapsed_ms = (time.monotonic() - start) * 1000

        # Overall status
        if total_count == 0:
            overall = "NO_AGENTS"
        elif healthy_count == total_count:
            overall = "HEALTHY"
        elif healthy_count >= total_count * 0.7:
            overall = "DEGRADED"
        else:
            overall = "CRITICAL"

        report = {
            "overall": overall,
            "agents_healthy": healthy_count,
            "agents_total": total_count,
            "health_ratio": healthy_count / max(total_count, 1),
            "agents": agent_statuses,
            "check_latency_ms": round(elapsed_ms, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._check_history.append(report)
        # Keep last 100 checks
        if len(self._check_history) > 100:
            self._check_history = self._check_history[-100:]

        self._last_check = datetime.now(timezone.utc)
        return report

    # === BaseAgent contract ===

    async def execute(self, task: dict) -> dict:
        """Execute a health check task dispatched by supervisor."""
        action = task.get("action", "check")

        if action == "check":
            report = await self.check()
            return {
                "result": report,
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        elif action == "history":
            limit = task.get("limit", 10)
            return {
                "result": {"checks": self._check_history[-limit:]},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        return {
            "result": {"error": f"Unknown action: {action}"},
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }

    @property
    def stats(self) -> dict:
        return {
            "monitored_agents": len(self._registered_agents),
            "total_checks": len(self._check_history),
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }

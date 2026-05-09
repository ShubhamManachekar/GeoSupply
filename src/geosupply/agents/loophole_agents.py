"""Loophole Hunter domain agents — Layer 3 wrappers for LoopholeHunterSupervisor."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class LoopholeHunterAgent(BaseAgent):
    name = "LoopholeHunterAgent"
    domain = "loophole"
    capabilities = {"LOOPHOLE_HUNT"}

    async def execute(self, task: dict) -> dict:
        from geosupply.subagents.penetration_test_subagent import PenetrationTestSubAgent
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await PenetrationTestSubAgent().run({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class PenTestAgent(BaseAgent):
    name = "PenTestAgent"
    domain = "loophole"
    capabilities = {"LOOPHOLE_PENTEST"}

    async def execute(self, task: dict) -> dict:
        from geosupply.subagents.penetration_test_subagent import PenetrationTestSubAgent
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await PenetrationTestSubAgent().run(
            {**payload, "probe_set": "full", "trace_id": trace_id}
        )
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class OverrideMonitorAgent(BaseAgent):
    name = "OverrideMonitorAgent"
    domain = "loophole"
    capabilities = {"LOOPHOLE_OVERRIDE_MONITOR"}

    async def execute(self, task: dict) -> dict:
        from geosupply.subagents.override_pattern_subagent import OverridePatternSubAgent
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        result = await OverridePatternSubAgent().run({**payload, "trace_id": trace_id})
        return {
            "result": result.get("result", {}),
            "meta": {
                "agent": self.name,
                "cost_inr": result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""
OverridePatternSubAgent — Phase 6 SubAgent Layer
FA v3 | Security | Layer 4

Analyses override history for abuse patterns using thresholds from config.py.

PIPELINE:
    Step 1 (load_overrides):     Validate and parse list of OverrideRecord dicts
    Step 2 (classify_patterns):  Apply 4 pattern detectors against config thresholds
    Step 3 (emit_findings):      Convert each violation into LoopholeFinding objects

Config thresholds used:
    OVERRIDE_ALERT_WEEKLY_LIMIT        = 5   (max overrides in last 7 days)
    OVERRIDE_SOURCE_FAVOURITISM_LIMIT  = 3   (max overrides targeting same entity)
    OVERRIDE_TIME_CLUSTER_LIMIT        = 3   (max overrides within any 1-hour window)
    OVERRIDE_FACTCHECK_BYPASS_LIMIT    = 0.20 (max fraction with action=="approve")

Cost: Rs 0.0 (Tier-0 — no LLM).
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from geosupply.config import (
    OVERRIDE_ALERT_WEEKLY_LIMIT,
    OVERRIDE_SOURCE_FAVOURITISM_LIMIT,
    OVERRIDE_TIME_CLUSTER_LIMIT,
    OVERRIDE_FACTCHECK_BYPASS_LIMIT,
)
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.schemas import LoopholeFinding

logger = logging.getLogger(__name__)


class _ParsedOverride(NamedTuple):
    timestamp: datetime
    action: str
    target: str


class OverridePatternSubAgent(BaseSubAgent):
    """Detects abuse patterns in admin override history."""

    name = "OverridePatternSubAgent"
    pipeline_steps = ["load_overrides", "classify_patterns", "emit_findings"]
    parallel_steps: set[str] = set()

    async def setup(self) -> None:
        await super().setup()

    async def teardown(self) -> None:
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        """
        Analyse override records and emit LoopholeFinding objects for each violation.
        """
        # ----------------------------------------------------------------
        # Step 1 — load_overrides
        # ----------------------------------------------------------------
        overrides = input_data.get("overrides", [])
        trace_id = input_data.get("trace_id", str(uuid.uuid4()))
        now = datetime.now(timezone.utc)

        parsed: list[_ParsedOverride] = []
        for raw in overrides:
            try:
                ts_raw = raw.get("timestamp")
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                elif isinstance(ts_raw, datetime):
                    ts = ts_raw
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                else:
                    ts = now
                parsed.append(_ParsedOverride(
                    timestamp=ts,
                    action=str(raw.get("action", "")),
                    target=str(raw.get("target", "")),
                ))
            except Exception as exc:
                logger.warning("OverridePatternSubAgent: skipping invalid override record: %s", exc)

        # ----------------------------------------------------------------
        # Step 2 — classify_patterns
        # ----------------------------------------------------------------
        findings: list[LoopholeFinding] = []

        # PATTERN 1 — weekly volume
        week_ago = now - timedelta(days=7)
        recent = [o for o in parsed if o.timestamp >= week_ago]
        if len(recent) > OVERRIDE_ALERT_WEEKLY_LIMIT:
            findings.append(LoopholeFinding(
                check_id="OVR-001",
                name="ExcessiveWeeklyOverrides",
                severity="HIGH",
                layer="Layer 0 Admin",
                details=(
                    f"{len(recent)} overrides in last 7 days "
                    f"(limit={OVERRIDE_ALERT_WEEKLY_LIMIT})"
                ),
                recommendation="Review override frequency; may indicate unauthorized access",
            ))

        # PATTERN 2 — source favouritism
        target_counts: dict[str, int] = defaultdict(int)
        for o in parsed:
            target_counts[o.target] += 1
        for target, count in target_counts.items():
            if count > OVERRIDE_SOURCE_FAVOURITISM_LIMIT:
                findings.append(LoopholeFinding(
                    check_id="OVR-002",
                    name="SourceFavouritism",
                    severity="MEDIUM",
                    layer="Layer 0 Admin",
                    details=(
                        f"Target '{target}' overridden {count} times "
                        f"(limit={OVERRIDE_SOURCE_FAVOURITISM_LIMIT})"
                    ),
                    recommendation="Audit overrides targeting this entity for bias or manipulation",
                ))

        # PATTERN 3 — time clustering (sliding 1-hour window)
        sorted_parsed = sorted(parsed, key=lambda o: o.timestamp)
        for i, anchor in enumerate(sorted_parsed):
            window_end = anchor.timestamp + timedelta(hours=1)
            cluster_count = sum(
                1 for o in sorted_parsed[i:]
                if anchor.timestamp <= o.timestamp < window_end
            )
            if cluster_count >= OVERRIDE_TIME_CLUSTER_LIMIT:
                findings.append(LoopholeFinding(
                    check_id="OVR-003",
                    name="TimeClusteredOverrides",
                    severity="HIGH",
                    layer="Layer 0 Admin",
                    details=(
                        f"{cluster_count} overrides within 1-hour window "
                        f"(limit={OVERRIDE_TIME_CLUSTER_LIMIT})"
                    ),
                    recommendation="Investigate rapid override bursts — may be automated or unauthorized",
                ))
                break  # Only report once per run

        # PATTERN 4 — factcheck bypass fraction
        if len(parsed) > 0:
            bypass_count = sum(1 for o in parsed if o.action == "approve")
            bypass_fraction = bypass_count / len(parsed)
            if bypass_fraction > OVERRIDE_FACTCHECK_BYPASS_LIMIT:
                findings.append(LoopholeFinding(
                    check_id="OVR-004",
                    name="FactCheckBypassExcessive",
                    severity="CRITICAL",
                    layer="Layer 4 SubAgents",
                    details=(
                        f"{bypass_fraction:.1%} of overrides are approve actions "
                        f"(limit={OVERRIDE_FACTCHECK_BYPASS_LIMIT:.0%})"
                    ),
                    recommendation="Mandatory review: fact-check bypass may allow hallucinated content",
                ))

        # ----------------------------------------------------------------
        # Step 3 — emit_findings
        # ----------------------------------------------------------------
        return {
            "result": {
                "patterns_detected": len(findings),
                "findings": [f.model_dump() for f in findings],
                "override_count": len(parsed),
                "trace_id": trace_id,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "steps_completed": 3,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

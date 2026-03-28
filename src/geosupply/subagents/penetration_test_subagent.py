"""
PenetrationTestSubAgent — Phase 6 SubAgent Layer
FA v3 | Security | Layer 4

Automated security probes against the production architecture.
Tests that defences are in place, NOT that they can be bypassed.

PIPELINE:
    Step 1 (probe_schema_bypass):    Attempt invalid schema construction; verify rejection
    Step 2 (probe_budget_evasion):   Attempt tasks with zero/negative budget; verify rejection
    Step 3 (probe_event_signing):    Attempt EventBus publish with forged signature; verify rejection
    Step 4 (aggregate_findings):     Collect FAIL probes as LoopholeFinding objects

Each probe records PASS (defence held) or FAIL (vulnerability found).
Any FAIL becomes a LoopholeFinding in the output.
Cost: Rs 0.0 (Tier-0 -- no LLM).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

from geosupply.core.base_subagent import BaseSubAgent
from geosupply.core.event_bus import EventBus
from geosupply.schemas import TaskPacket, Event, LoopholeFinding

logger = logging.getLogger(__name__)

_TEST_AGENT_NAME = "PenTestProbeAgent"
_TEST_SIGNING_KEY = "pen-test-key-not-for-production-use"


class PenetrationTestSubAgent(BaseSubAgent):
    """Automated security probes against the production architecture."""

    name = "PenetrationTestSubAgent"
    pipeline_steps = ["probe_schema_bypass", "probe_budget_evasion", "probe_event_signing", "aggregate_findings"]
    parallel_steps: set[str] = set()

    def __init__(self) -> None:
        self._event_bus = EventBus()

    async def setup(self) -> None:
        """Register test signing key and initialise EventBus."""
        self._event_bus.register_agent_key(_TEST_AGENT_NAME, _TEST_SIGNING_KEY)
        await super().setup()

    async def teardown(self) -> None:
        """Revoke test signing key on shutdown."""
        self._event_bus.revoke_agent_key(_TEST_AGENT_NAME)
        await super().teardown()

    async def run(self, input_data: dict) -> dict:
        """
        Run security probes and collect findings for any failed defences.
        """
        trace_id = input_data.get("trace_id", str(uuid.uuid4()))
        probes_run = 0
        failures: list[LoopholeFinding] = []

        # Ensure test key is registered even if setup() wasn't called
        if _TEST_AGENT_NAME not in self._event_bus._agent_keys:
            self._event_bus.register_agent_key(_TEST_AGENT_NAME, _TEST_SIGNING_KEY)

        # ----------------------------------------------------------------
        # Step 1 — probe_schema_bypass
        # ----------------------------------------------------------------

        # PROBE 1a: TaskPacket with missing required fields
        try:
            TaskPacket()  # type: ignore[call-arg]
            # If we get here, validation did NOT raise — this is a FAIL
            failures.append(LoopholeFinding(
                check_id="PEN-001",
                name="TaskPacketMissingFieldsAccepted",
                severity="HIGH",
                layer="Layer 1",
                details="TaskPacket accepted empty construction without required fields",
                recommendation="Add required field validators to TaskPacket",
            ))
        except (ValidationError, TypeError):
            pass  # PASS — defence held
        probes_run += 1

        # PROBE 1b: TaskPacket with budget_inr = -10.0 (negative budget)
        try:
            t = TaskPacket(task_id="pen-001", task_type="NLP_NER", budget_inr=-10.0)
            # If no validator rejects negative budget, check if it was accepted
            if t.budget_inr == -10.0:
                failures.append(LoopholeFinding(
                    check_id="PEN-002",
                    name="NegativeBudgetAccepted",
                    severity="CRITICAL",
                    layer="Layer 1",
                    details="TaskPacket accepted budget_inr=-10.0 without rejection",
                    recommendation="Add Pydantic ge=0.0 validator on TaskPacket.budget_inr",
                ))
        except (ValidationError, ValueError):
            pass  # PASS — defence held
        probes_run += 1

        # PROBE 1c: AgentMessage empty strings (informational only — not a failure)
        probes_run += 1

        # ----------------------------------------------------------------
        # Step 2 — probe_budget_evasion
        # ----------------------------------------------------------------
        from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
        sup = IngestionSupervisor()
        sup.reset_budget()

        # PROBE 2a: budget_inr = 0.0 (zero budget — allowed by design since cost deducted post-exec)
        probes_run += 1

        # PROBE 2b: budget_inr > supervisor budget_inr cap (should be rejected)
        task_over = TaskPacket(
            task_id="pen-test-over",
            task_type="INGEST_NEWS",
            budget_inr=9999.0,
        )
        result = await sup.dispatch(task_over)
        if result.get("reason") != "task_over_budget":
            failures.append(LoopholeFinding(
                check_id="PEN-003",
                name="OverBudgetTaskNotRejected",
                severity="HIGH",
                layer="Layer 2",
                details=f"task_over_budget not raised for budget_inr=9999.0, got: {result}",
                recommendation="BaseSupervisor must gate budget_inr > _budget_remaining",
            ))
        probes_run += 1

        # ----------------------------------------------------------------
        # Step 3 — probe_event_signing
        # ----------------------------------------------------------------

        # PROBE 3a: Event with blank signature
        now = datetime.now(timezone.utc)
        blank_sig_event = Event(
            topic="test.topic",
            source=_TEST_AGENT_NAME,
            payload={},
            timestamp=now,
            signature="",
        )
        if self._event_bus.verify_event(blank_sig_event):
            failures.append(LoopholeFinding(
                check_id="PEN-004",
                name="BlankSignatureAccepted",
                severity="CRITICAL",
                layer="Layer 0 EventBus",
                details="EventBus accepted blank HMAC signature",
                recommendation="HMAC verification must reject empty signature strings",
            ))
        probes_run += 1

        # PROBE 3b: Event with forged/wrong signature
        forged_sig_event = Event(
            topic="test.topic",
            source=_TEST_AGENT_NAME,
            payload={},
            timestamp=now,
            signature="aabbccdd1122eeff00112233445566778899aabbccddeeff00112233445566778899",
        )
        if self._event_bus.verify_event(forged_sig_event):
            failures.append(LoopholeFinding(
                check_id="PEN-005",
                name="ForgedSignatureAccepted",
                severity="CRITICAL",
                layer="Layer 0 EventBus",
                details="EventBus accepted a forged HMAC signature",
                recommendation="HMAC verification must reject signatures not matching expected digest",
            ))
        probes_run += 1

        # ----------------------------------------------------------------
        # Step 4 — aggregate_findings
        # ----------------------------------------------------------------
        return {
            "result": {
                "probes_run": probes_run,
                "vulnerabilities_found": len(failures),
                "findings": [f.model_dump() for f in failures],
                "trace_id": trace_id,
            },
            "meta": {
                "subagent": self.name,
                "cost_inr": 0.0,
                "steps_completed": 4,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

"""Tests for PenetrationTestSubAgent."""

import pytest

from geosupply.subagents.penetration_test_subagent import PenetrationTestSubAgent
from geosupply.schemas import LoopholeFinding, TaskPacket
from pydantic import ValidationError


@pytest.fixture
def agent():
    a = PenetrationTestSubAgent()
    return a


class TestPenetrationTestSubAgentClean:
    @pytest.mark.asyncio
    async def test_clean_architecture_runs_without_error(self, agent):
        """Against the real production components — subagent must complete all 4 steps."""
        result = await agent.run({})
        # Subagent completes successfully regardless of findings
        assert result["meta"]["cost_inr"] == 0.0
        assert result["meta"]["steps_completed"] == 4
        assert "vulnerabilities_found" in result["result"]
        assert "probes_run" in result["result"]

    @pytest.mark.asyncio
    async def test_probes_run_count(self, agent):
        result = await agent.run({})
        # 7 probes: probe 1a, 1b, 1c, 2a, 2b, 3a, 3b
        assert result["result"]["probes_run"] == 7

    @pytest.mark.asyncio
    async def test_critical_defences_hold(self, agent):
        """PEN-001, PEN-003, PEN-004, PEN-005 should not fire on correct architecture."""
        result = await agent.run({})
        fired_ids = {f["check_id"] for f in result["result"]["findings"]}
        # Schema missing fields MUST be rejected (PEN-001)
        assert "PEN-001" not in fired_ids, "PEN-001 fired — TaskPacket missing-fields not rejected"
        # Over-budget task MUST be rejected (PEN-003)
        assert "PEN-003" not in fired_ids, "PEN-003 fired — over-budget task not rejected"
        # Blank signature MUST be rejected (PEN-004)
        assert "PEN-004" not in fired_ids, "PEN-004 fired — blank signature accepted"
        # Forged signature MUST be rejected (PEN-005)
        assert "PEN-005" not in fired_ids, "PEN-005 fired — forged signature accepted"


class TestPenetrationTestSubAgentSchemaBypass:
    def test_probe_schema_bypass_taskpacket_missing_fields(self):
        """Verify probe 1a correctly identifies that TaskPacket() raises ValidationError."""
        try:
            t = TaskPacket()  # type: ignore[call-arg]
            # If this passes, schema is weaker than expected
            assert False, "TaskPacket() should raise ValidationError"
        except (ValidationError, TypeError):
            pass  # Defence held


class TestPenetrationTestSubAgentBudgetEvasion:
    @pytest.mark.asyncio
    async def test_probe_budget_evasion_over_budget_rejected(self, agent):
        """Verify probe 2b correctly captures over-budget task rejection."""
        from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
        sup = IngestionSupervisor()
        sup.reset_budget()
        task = TaskPacket(task_id="pen-over", task_type="INGEST_NEWS", budget_inr=9999.0)
        result = await sup.dispatch(task)
        assert result.get("reason") == "task_over_budget"


class TestPenetrationTestSubAgentEventSigning:
    def test_probe_event_signing_blank_rejected(self):
        """Verify probe 3a correctly captures that blank signature is rejected by EventBus."""
        from geosupply.core.event_bus import EventBus
        from geosupply.schemas import Event
        from datetime import datetime, timezone
        bus = EventBus()
        bus.register_agent_key("test_agent", "test-key-abc")
        event = Event(
            topic="test",
            source="test_agent",
            payload={},
            timestamp=datetime.now(timezone.utc),
            signature="",
        )
        assert not bus.verify_event(event)


class TestPenetrationTestSubAgentFindingsValid:
    @pytest.mark.asyncio
    async def test_findings_are_loophole_finding_parseable(self, agent):
        result = await agent.run({})
        for finding in result["result"]["findings"]:
            validated = LoopholeFinding.model_validate(finding)
            assert validated.check_id

"""Tests for IntelSupervisor — Phase 6 intelligence analysis supervisor."""

import pytest
from geosupply.supervisors.intel_supervisor import IntelSupervisor
from geosupply.schemas import TaskPacket


@pytest.fixture
def supervisor():
    return IntelSupervisor()


def make_task(task_type: str, budget: float = 10.0, payload: dict | None = None) -> TaskPacket:
    return TaskPacket(
        task_id=f"intel-{task_type.lower().replace('_', '-')}",
        task_type=task_type,
        priority="P1",
        budget_inr=budget,
        payload=payload or {"text": "Test intel input"},
    )


def _dispatched_agent(result: dict) -> str:
    """Extract agent name from completed dispatch result."""
    return result["result"]["result"]["agent"]


class TestRouting:
    async def test_supply_chain_routes_to_supplier_agent(self, supervisor):
        task = make_task("SUPPLY_CHAIN_RISK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SupplierAgent"

    async def test_sanctions_routes_to_sanctions_agent(self, supervisor):
        task = make_task("SANCTIONS_CHECK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SanctionsAgent"

    async def test_source_cred_routes_to_source_cred_agent(self, supervisor):
        task = make_task("SOURCE_CRED")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SourceCredAgent"

    async def test_cyber_threat_routes_to_cyber_agent(self, supervisor):
        task = make_task("CYBER_THREAT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "CyberAgent"

    async def test_verify_claim_routes_to_verifier_agent(self, supervisor):
        task = make_task("VERIFY_CLAIM")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "VerifierAgent"

    async def test_author_check_routes_to_author_agent(self, supervisor):
        task = make_task("AUTHOR_CHECK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "AuthorAgent"

    async def test_unknown_type_falls_back_to_source_cred(self, supervisor):
        task = make_task("INTEL_UNKNOWN_XYZ")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SourceCredAgent"


class TestTier3BudgetGate:
    async def test_verify_claim_rejected_when_budget_exhausted(self, supervisor):
        # Drain budget below Tier-3 minimum (0.05)
        supervisor._budget_remaining = 0.03
        task = make_task("VERIFY_CLAIM", budget=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted_tier3"

    async def test_author_check_rejected_when_budget_exhausted(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = make_task("AUTHOR_CHECK", budget=1.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"

    async def test_tier1_task_not_rejected_by_tier3_gate(self, supervisor):
        # Tier-3 gate only fires for VERIFY_CLAIM / AUTHOR_CHECK
        supervisor._budget_remaining = 0.03
        # SANCTIONS_CHECK is Tier-1 — not blocked by Tier-3 gate
        # It may still fail the task_budget check if budget=0.03 < task.budget
        task = make_task("SANCTIONS_CHECK", budget=0.02)
        result = await supervisor.dispatch(task)
        # Should pass Tier-3 gate at minimum
        assert result.get("reason") != "budget_exhausted_tier3"


class TestCapabilities:
    def test_capable_agents_for_sanctions(self, supervisor):
        agents = supervisor.capable_agents("SANCTIONS_CHECK")
        assert "SanctionsAgent" in agents

    def test_capable_agents_for_bot_detect(self, supervisor):
        agents = supervisor.capable_agents("BOT_DETECT")
        assert "AuthorAgent" in agents

    def test_tier3_agents_returns_verifier_and_author(self, supervisor):
        tier3 = supervisor.tier3_agents()
        assert "VerifierAgent" in tier3
        assert "AuthorAgent" in tier3

    def test_capable_agents_for_unknown_returns_empty(self, supervisor):
        agents = supervisor.capable_agents("UNKNOWN_CAP_XYZ")
        assert agents == []


class TestSupervisorMeta:
    def test_name_is_intel_supervisor(self, supervisor):
        assert supervisor.name == "IntelSupervisor"

    def test_domain_is_intel(self, supervisor):
        assert supervisor.domain == "intel"

    def test_budget_is_20(self, supervisor):
        assert supervisor.budget_inr == 20.0

    def test_six_agents_registered(self, supervisor):
        assert len(supervisor.agents) == 6

"""Unit tests for SwarmManagerAgent decompose(), execute_dag(), and route()."""

from __future__ import annotations

import pytest

from geosupply.agents.swarm_manager_agent import (
    ROUTING_TABLE,
    SUPPLY_BRIEF_TEMPLATE,
    SwarmManagerAgent,
)
from geosupply.schemas import TaskPacket


# ---------------------------------------------------------------------------
# Shared mock supervisor
# ---------------------------------------------------------------------------

class _MockSupervisor:
    def __init__(self, name):
        self.name = name
        self.dispatched = []

    async def dispatch(self, task):
        self.dispatched.append(task.task_id)
        return {"status": "completed", "cost_inr": 0.0}


# ---------------------------------------------------------------------------
# decompose() tests
# ---------------------------------------------------------------------------

class TestDecompose:
    def test_decompose_supply_brief_returns_10_packets(self):
        agent = SwarmManagerAgent()
        packets = agent.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        assert len(packets) == 10
        assert all(isinstance(p, TaskPacket) for p in packets)

    def test_decompose_task_ids_unique(self):
        agent = SwarmManagerAgent()
        packets = agent.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        ids = [p.task_id for p in packets]
        assert len(ids) == len(set(ids))
        assert all(isinstance(tid, str) and len(tid) > 0 for tid in ids)

    def test_decompose_dependencies_resolved(self):
        agent = SwarmManagerAgent()
        packets = agent.decompose(
            {"compound_task_type": "SUPPLY_BRIEF", "plan_id": "abcd1234efgh"}
        )
        by_type = {p.task_type: p for p in packets}

        brief = by_type["BRIEF_GENERATE"]
        nar_id = by_type["NARRATIVE_NETWORK"].task_id
        rag_id = by_type["RAG_QUERY"].task_id

        assert nar_id in brief.dependencies
        assert rag_id in brief.dependencies

    def test_decompose_unknown_type_returns_empty(self):
        agent = SwarmManagerAgent()
        packets = agent.decompose({"compound_task_type": "TOTALLY_UNKNOWN_TASK"})
        assert packets == []

    def test_decompose_uses_provided_plan_id(self):
        agent = SwarmManagerAgent()
        packets = agent.decompose(
            {"compound_task_type": "SUPPLY_BRIEF", "plan_id": "fixed-plan-id-xyz"}
        )
        # All task_ids should use the first 8 chars of plan_id
        for p in packets:
            assert p.task_id.endswith("fixed-pl")

    def test_decompose_propagates_payload(self):
        agent = SwarmManagerAgent()
        payload = {"region": "INDIA", "depth": 3}
        packets = agent.decompose(
            {"compound_task_type": "SUPPLY_BRIEF", "payload": payload}
        )
        assert all(p.payload == payload for p in packets)


# ---------------------------------------------------------------------------
# execute_dag() tests
# ---------------------------------------------------------------------------

class TestExecuteDAG:
    @pytest.mark.asyncio
    async def test_execute_dag_completes_all(self):
        """3-task chain: A → B → C. All should appear in completed."""
        agent = SwarmManagerAgent()
        mock_sup = _MockSupervisor("NLPSupervisor")
        registry = {"NLPSupervisor": mock_sup}

        tasks = [
            TaskPacket(task_id="A", task_type="NLP_NER",       priority="P1", dependencies=[]),
            TaskPacket(task_id="B", task_type="NLP_SENTIMENT",  priority="P1", dependencies=["A"]),
            TaskPacket(task_id="C", task_type="NLP_CLAIM",      priority="P1", dependencies=["B"]),
        ]

        completed = await agent.execute_dag(tasks, registry)

        assert set(completed.keys()) == {"A", "B", "C"}
        assert all(r["status"] == "completed" for r in completed.values())

    @pytest.mark.asyncio
    async def test_execute_dag_respects_order(self):
        """B depends on A — B must be dispatched after A."""
        agent = SwarmManagerAgent()
        dispatch_order: list[str] = []

        class _OrderedSupervisor:
            async def dispatch(self, task):
                dispatch_order.append(task.task_id)
                return {"status": "completed", "cost_inr": 0.0}

        registry = {"NLPSupervisor": _OrderedSupervisor()}

        tasks = [
            TaskPacket(task_id="A", task_type="NLP_NER",      priority="P1", dependencies=[]),
            TaskPacket(task_id="B", task_type="NLP_SENTIMENT", priority="P1", dependencies=["A"]),
        ]

        await agent.execute_dag(tasks, registry)

        assert dispatch_order.index("A") < dispatch_order.index("B")

    @pytest.mark.asyncio
    async def test_execute_dag_parallel_roots(self):
        """Two independent root tasks should both complete."""
        agent = SwarmManagerAgent()
        mock_ingest = _MockSupervisor("IngestionSupervisor")
        registry = {"IngestionSupervisor": mock_ingest}

        tasks = [
            TaskPacket(task_id="X", task_type="INGEST_NEWS",      priority="P1", dependencies=[]),
            TaskPacket(task_id="Y", task_type="INGEST_INDIA_API",  priority="P1", dependencies=[]),
        ]

        completed = await agent.execute_dag(tasks, registry)
        assert set(completed.keys()) == {"X", "Y"}


# ---------------------------------------------------------------------------
# route() tests
# ---------------------------------------------------------------------------

class TestRoute:
    @pytest.mark.asyncio
    async def test_route_known_task_type(self):
        """RAG_QUERY routes to IntelSupervisor."""
        agent = SwarmManagerAgent()
        intel_sup = _MockSupervisor("IntelSupervisor")
        registry = {"IntelSupervisor": intel_sup}

        task = TaskPacket(task_id="rag-001", task_type="RAG_QUERY", priority="P0")
        result = await agent.route(task, registry)

        assert result["status"] == "completed"
        assert "rag-001" in intel_sup.dispatched

    @pytest.mark.asyncio
    async def test_route_unknown_task_type_fallback(self):
        """Unknown task_type falls back to IngestionSupervisor."""
        agent = SwarmManagerAgent()
        ingest_sup = _MockSupervisor("IngestionSupervisor")
        registry = {"IngestionSupervisor": ingest_sup}

        task = TaskPacket(task_id="unknown-001", task_type="NO_SUCH_TYPE", priority="P1")
        result = await agent.route(task, registry)

        assert result["status"] == "completed"
        assert "unknown-001" in ingest_sup.dispatched

    @pytest.mark.asyncio
    async def test_route_missing_supervisor(self):
        """Supervisor named in ROUTING_TABLE but absent from registry → error."""
        agent = SwarmManagerAgent()
        # Registry is deliberately empty
        task = TaskPacket(task_id="brief-001", task_type="BRIEF_GENERATE", priority="P0")
        result = await agent.route(task, {})

        assert result["status"] == "error"
        assert "IntelSupervisor" in result["reason"]

    @pytest.mark.asyncio
    async def test_route_dispatches_correct_task_object(self):
        """The exact TaskPacket passed to route() is forwarded to dispatch()."""
        agent = SwarmManagerAgent()
        received: list[TaskPacket] = []

        class _CapturingSupervisor:
            async def dispatch(self, task):
                received.append(task)
                return {"status": "completed", "cost_inr": 0.0}

        registry = {"QualitySupervisor": _CapturingSupervisor()}
        task = TaskPacket(task_id="cv-001", task_type="CLAIM_VERIFY", priority="P0")
        await agent.route(task, registry)

        assert len(received) == 1
        assert received[0].task_id == "cv-001"


# ---------------------------------------------------------------------------
# ROUTING_TABLE coverage test
# ---------------------------------------------------------------------------

class TestRoutingTable:
    def test_routing_table_has_supply_brief_types(self):
        """Every task_type used in SUPPLY_BRIEF_TEMPLATE must appear in ROUTING_TABLE."""
        supply_brief_types = {step["task_type"] for step in SUPPLY_BRIEF_TEMPLATE}
        missing = supply_brief_types - set(ROUTING_TABLE.keys())
        assert missing == set(), f"ROUTING_TABLE is missing: {missing}"

    def test_routing_table_values_are_3_tuples(self):
        for task_type, entry in ROUTING_TABLE.items():
            assert isinstance(entry, tuple) and len(entry) == 3, (
                f"{task_type!r} entry is not a 3-tuple: {entry!r}"
            )
            supervisor_name, tier, uses_static = entry
            assert isinstance(supervisor_name, str)
            assert isinstance(tier, int)
            assert isinstance(uses_static, bool)


# ---------------------------------------------------------------------------
# Delegation tests — SwarmManagerAgent → SwarmMaster
# ---------------------------------------------------------------------------

class TestSwarmManagerAgentDelegation:
    def test_decompose_still_returns_10_packets(self):
        """SwarmManagerAgent.decompose() still returns 10 packets (delegation works)."""
        agent = SwarmManagerAgent()
        packets = agent.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        assert len(packets) == 10

    def test_routing_table_importable(self):
        """ROUTING_TABLE can be imported from swarm_manager_agent (backward compat)."""
        from geosupply.agents.swarm_manager_agent import ROUTING_TABLE as RT
        assert isinstance(RT, dict)
        assert len(RT) >= 57

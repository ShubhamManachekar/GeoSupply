"""Tests for SwarmMaster orchestrator."""

import pytest

from geosupply.orchestrator.swarm_master import SwarmMaster, ROUTING_TABLE, SUPPLY_BRIEF_TEMPLATE
from geosupply.schemas import TaskPacket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockSupervisor:
    """Minimal supervisor that records calls and returns a completed result."""

    def __init__(self, name: str, cost_inr: float = 0.1) -> None:
        self.name = name
        self.cost_inr = cost_inr
        self.calls: list[TaskPacket] = []

    async def dispatch(self, task: TaskPacket) -> dict:
        self.calls.append(task)
        return {
            "status": "completed",
            "cost_inr": self.cost_inr,
            "result": {"agent": self.name},
        }


class _FailingSupervisor:
    """Supervisor that always raises an exception."""

    name = "FailingSupervisor"

    async def dispatch(self, task: TaskPacket) -> dict:
        raise RuntimeError("simulated supervisor failure")


def _make_all_supervisors() -> dict:
    """Create a registry with stubs for all supervisors in ROUTING_TABLE."""
    names = {v[0] for v in ROUTING_TABLE.values()}
    return {name: _MockSupervisor(name) for name in names}


def _make_brief_supervisors() -> dict:
    """Create supervisor registry for the SUPPLY_BRIEF pipeline."""
    needed = {ROUTING_TABLE[step["task_type"]][0] for step in SUPPLY_BRIEF_TEMPLATE}
    return {name: _MockSupervisor(name) for name in needed}


# ---------------------------------------------------------------------------
# TestSwarmMasterInit
# ---------------------------------------------------------------------------

class TestSwarmMasterInit:
    def test_default_registry_empty(self):
        sm = SwarmMaster()
        assert sm.registered_supervisors == []

    def test_plan_count_starts_zero(self):
        sm = SwarmMaster()
        assert sm.plan_count == 0

    def test_register_supervisor_adds_to_registry(self):
        sm = SwarmMaster()
        obj = _MockSupervisor("X")
        sm.register_supervisor("X", obj)
        assert "X" in sm.registered_supervisors

    def test_registry_is_single_writer(self):
        sm = SwarmMaster()
        obj = _MockSupervisor("Y")
        sm.register_supervisor("Y", obj)
        # Direct assignment not used — only register_supervisor() mutates
        assert "Y" in sm._supervisor_registry


# ---------------------------------------------------------------------------
# TestSwarmMasterDecompose
# ---------------------------------------------------------------------------

class TestSwarmMasterDecompose:
    def test_supply_brief_returns_10_packets(self):
        sm = SwarmMaster()
        packets = sm.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        assert len(packets) == 10

    def test_all_task_ids_unique(self):
        sm = SwarmMaster()
        packets = sm.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        ids = [p.task_id for p in packets]
        assert len(ids) == len(set(ids))

    def test_plan_id_prefix_in_task_ids(self):
        sm = SwarmMaster()
        plan_id = "abcdef1234567890"
        packets = sm.decompose({"compound_task_type": "SUPPLY_BRIEF", "plan_id": plan_id})
        for p in packets:
            assert plan_id[:8] in p.task_id

    def test_dependency_ids_reference_real_task_ids(self):
        sm = SwarmMaster()
        packets = sm.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        all_ids = {p.task_id for p in packets}
        for p in packets:
            for dep in p.dependencies:
                assert dep in all_ids, f"Dep {dep!r} not in task_ids"

    def test_unknown_compound_type_returns_empty(self):
        sm = SwarmMaster()
        packets = sm.decompose({"compound_task_type": "UNKNOWN_COMPOUND"})
        assert packets == []

    def test_plan_count_increments(self):
        sm = SwarmMaster()
        sm.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        sm.decompose({"compound_task_type": "SUPPLY_BRIEF"})
        assert sm.plan_count == 2

    def test_payload_propagated_to_all_packets(self):
        sm = SwarmMaster()
        packets = sm.decompose({
            "compound_task_type": "SUPPLY_BRIEF",
            "payload": {"region": "INDIA"},
        })
        for p in packets:
            assert p.payload.get("region") == "INDIA"


# ---------------------------------------------------------------------------
# TestSwarmMasterExecuteDAG
# ---------------------------------------------------------------------------

class TestSwarmMasterExecuteDAG:
    @pytest.mark.asyncio
    async def test_single_task_no_deps_completes(self):
        sup = _MockSupervisor("IngestionSupervisor")
        sm = SwarmMaster({"IngestionSupervisor": sup})
        task = TaskPacket(task_id="t1", task_type="INGEST_NEWS", priority="P1")
        results = await sm.execute_dag([task])
        assert len(results) == 1
        assert results["t1"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_chain_respects_dependency_order(self):
        call_order: list[str] = []

        class OrderedSup:
            def __init__(self, name: str) -> None:
                self.name = name

            async def dispatch(self, task: TaskPacket) -> dict:
                call_order.append(task.task_id)
                return {"status": "completed", "cost_inr": 0.0}

        sup = OrderedSup("IngestionSupervisor")
        nlp_sup = OrderedSup("NLPSupervisor")
        registry = {"IngestionSupervisor": sup, "NLPSupervisor": nlp_sup}
        sm = SwarmMaster(registry)

        t_a = TaskPacket(task_id="A", task_type="INGEST_NEWS", priority="P1", dependencies=[])
        t_b = TaskPacket(task_id="B", task_type="NLP_NER", priority="P1", dependencies=["A"])
        t_c = TaskPacket(task_id="C", task_type="NLP_SENTIMENT", priority="P1", dependencies=["B"])

        await sm.execute_dag([t_a, t_b, t_c])
        assert call_order.index("A") < call_order.index("B")
        assert call_order.index("B") < call_order.index("C")

    @pytest.mark.asyncio
    async def test_parallel_roots_both_complete(self):
        sup = _MockSupervisor("IngestionSupervisor")
        sm = SwarmMaster({"IngestionSupervisor": sup})
        t1 = TaskPacket(task_id="t1", task_type="INGEST_NEWS", priority="P1", dependencies=[])
        t2 = TaskPacket(task_id="t2", task_type="INGEST_AIS", priority="P1", dependencies=[])
        results = await sm.execute_dag([t1, t2])
        assert results["t1"]["status"] == "completed"
        assert results["t2"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_exception_captured_per_task(self):
        good_sup = _MockSupervisor("IngestionSupervisor")
        bad_sup = _FailingSupervisor()
        # Map QualitySupervisor to failing supervisor
        registry = {
            "IngestionSupervisor": good_sup,
            "QualitySupervisor": bad_sup,
        }
        sm = SwarmMaster(registry)
        t_good = TaskPacket(task_id="good", task_type="INGEST_NEWS", priority="P1", dependencies=[])
        t_bad = TaskPacket(task_id="bad", task_type="CLAIM_VERIFY", priority="P1", dependencies=[])
        results = await sm.execute_dag([t_good, t_bad])
        assert results["good"]["status"] == "completed"
        assert results["bad"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_circular_dependency_is_detected(self):
        sup = _MockSupervisor("IngestionSupervisor")
        sm = SwarmMaster({"IngestionSupervisor": sup})
        t_a = TaskPacket(task_id="A", task_type="INGEST_NEWS", priority="P1", dependencies=["B"])
        t_b = TaskPacket(task_id="B", task_type="INGEST_AIS", priority="P1", dependencies=["A"])
        results = await sm.execute_dag([t_a, t_b])
        assert results["A"]["status"] == "skipped"
        assert results["A"]["reason"] == "dependency_unresolvable"
        assert results["B"]["status"] == "skipped"


# ---------------------------------------------------------------------------
# TestSwarmMasterRoute
# ---------------------------------------------------------------------------

class TestSwarmMasterRoute:
    @pytest.mark.asyncio
    async def test_known_task_type_dispatches_to_correct_supervisor(self):
        sup = _MockSupervisor("IngestionSupervisor")
        sm = SwarmMaster({"IngestionSupervisor": sup})
        task = TaskPacket(task_id="t1", task_type="INGEST_NEWS", priority="P1")
        result = await sm.route(task)
        assert result["status"] == "completed"
        assert len(sup.calls) == 1

    @pytest.mark.asyncio
    async def test_unknown_task_type_falls_back_to_ingestion(self):
        sup = _MockSupervisor("IngestionSupervisor")
        sm = SwarmMaster({"IngestionSupervisor": sup})
        task = TaskPacket(task_id="t1", task_type="TOTALLY_UNKNOWN_XYZ", priority="P1")
        result = await sm.route(task)
        assert result["status"] == "completed"
        assert len(sup.calls) == 1

    @pytest.mark.asyncio
    async def test_missing_supervisor_returns_error(self):
        sm = SwarmMaster({})  # empty registry
        task = TaskPacket(task_id="t1", task_type="INGEST_NEWS", priority="P1")
        result = await sm.route(task)
        assert result["status"] == "error"
        assert "not in registry" in result["reason"]


# ---------------------------------------------------------------------------
# TestSwarmMasterRunSupplyBrief
# ---------------------------------------------------------------------------

class TestSwarmMasterRunSupplyBrief:
    @pytest.mark.asyncio
    async def test_run_supply_brief_returns_all_10_task_ids(self):
        registry = _make_brief_supervisors()
        sm = SwarmMaster(registry)
        result = await sm.run_supply_brief({"region": "INDIA"})
        assert len(result["task_results"]) == 10

    @pytest.mark.asyncio
    async def test_run_supply_brief_generates_plan_id(self):
        registry = _make_brief_supervisors()
        sm = SwarmMaster(registry)
        result = await sm.run_supply_brief({"region": "INDIA"})
        assert result["plan_id"]
        assert isinstance(result["plan_id"], str)

    @pytest.mark.asyncio
    async def test_run_supply_brief_accepts_caller_plan_id(self):
        registry = _make_brief_supervisors()
        sm = SwarmMaster(registry)
        result = await sm.run_supply_brief({"region": "INDIA"}, plan_id="test-plan-001")
        assert result["plan_id"] == "test-plan-001"

    @pytest.mark.asyncio
    async def test_run_supply_brief_total_cost_is_sum(self):
        # Each mock supervisor returns cost_inr=0.1, 10 tasks → 1.0 total
        registry = _make_brief_supervisors()
        sm = SwarmMaster(registry)
        result = await sm.run_supply_brief({"region": "INDIA"})
        assert result["total_cost_inr"] == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# TestSwarmMasterRoutingTableIntegrity (regression guard)
# ---------------------------------------------------------------------------

class TestSwarmMasterRoutingTableIntegrity:
    def test_all_routing_table_entries_have_3_tuple(self):
        for key, val in ROUTING_TABLE.items():
            assert isinstance(val, tuple), f"Key {key!r} value is not a tuple"
            assert len(val) == 3, f"Key {key!r} tuple has {len(val)} elements, expected 3"
            name, tier, uses_static = val
            assert isinstance(name, str)
            assert isinstance(tier, int)
            assert isinstance(uses_static, bool)

    def test_supply_brief_template_task_types_in_routing_table(self):
        for step in SUPPLY_BRIEF_TEMPLATE:
            tt = step["task_type"]
            assert tt in ROUTING_TABLE, f"SUPPLY_BRIEF_TEMPLATE task_type {tt!r} not in ROUTING_TABLE"

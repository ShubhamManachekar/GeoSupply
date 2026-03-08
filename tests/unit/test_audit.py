"""
Test suite for geosupply.cli.audit — Phase-End Dynamic Test Suite.

Philosophy: ZERO MOCKS. Every test exercises real component discovery,
real schema registries, and real class hierarchies.
"""

import pytest
from geosupply.cli.audit import (
    discover_components,
    run_logic_breakage_tests,
    run_logic_gap_tests,
    run_oversight_tests,
    run_broken_chain_tests,
)
from geosupply.config import SCHEMA_VERSIONS
from geosupply.schemas import ALL_SCHEMAS
from geosupply.core.base_worker import BaseWorker
from geosupply.core.base_agent import BaseAgent
from geosupply.core.base_subagent import BaseSubAgent


# ── Discovery Tests ──────────────────────────────────────────────────


class TestDiscoverComponents:
    """Tests that dynamic component discovery finds real, registered components."""

    def test_discovery_finds_workers(self):
        """Real workers exist after discovery — InputSanitiserWorker, EventExtractorWorker."""
        workers, _, _ = discover_components()
        worker_names = [w.__name__ for w in workers]
        assert len(workers) >= 2, f"Expected at least 2 workers, got {len(workers)}: {worker_names}"
        assert "InputSanitiserWorker" in worker_names, "InputSanitiserWorker missing from discovery"
        assert "EventExtractorWorker" in worker_names, "EventExtractorWorker missing from discovery"

    def test_discovery_finds_agents(self):
        """Real agents exist after discovery — LoggingAgent, SecurityAgent, etc."""
        _, agents, _ = discover_components()
        agent_names = [a.__name__ for a in agents]
        assert len(agents) >= 3, f"Expected at least 3 agents, got {len(agents)}: {agent_names}"
        assert "LoggingAgent" in agent_names, "LoggingAgent missing from discovery"
        assert "SecurityAgent" in agent_names, "SecurityAgent missing from discovery"
        assert "HealthCheckAgent" in agent_names, "HealthCheckAgent missing from discovery"

    def test_discovery_returns_tuples(self):
        """Discovery returns three lists (workers, agents, subagents)."""
        result = discover_components()
        assert len(result) == 3
        workers, agents, subagents = result
        assert isinstance(workers, list)
        assert isinstance(agents, list)
        assert isinstance(subagents, list)

    def test_all_discovered_workers_inherit_base_worker(self):
        """Every discovered worker genuinely inherits from BaseWorker — no fakes."""
        workers, _, _ = discover_components()
        for w in workers:
            assert issubclass(w, BaseWorker), f"{w.__name__} does not inherit BaseWorker"

    def test_all_discovered_agents_inherit_base_agent(self):
        """Every discovered agent genuinely inherits from BaseAgent — no fakes."""
        _, agents, _ = discover_components()
        for a in agents:
            assert issubclass(a, BaseAgent), f"{a.__name__} does not inherit BaseAgent"


# ── Logic Breakage Tests ─────────────────────────────────────────────


class TestLogicBreakage:
    """Tests the schema registration consistency check against REAL registries."""

    def test_schema_count_matches_versions(self):
        """ALL_SCHEMAS and SCHEMA_VERSIONS must be kept perfectly in sync."""
        assert len(ALL_SCHEMAS) == len(SCHEMA_VERSIONS), (
            f"Schema mismatch: ALL_SCHEMAS has {len(ALL_SCHEMAS)} entries, "
            f"SCHEMA_VERSIONS has {len(SCHEMA_VERSIONS)} entries"
        )

    def test_every_schema_has_a_version_entry(self):
        """Each schema name in ALL_SCHEMAS must have a corresponding SCHEMA_VERSIONS entry."""
        for schema_name in ALL_SCHEMAS:
            assert schema_name in SCHEMA_VERSIONS, (
                f"Schema '{schema_name}' exists in ALL_SCHEMAS but missing from SCHEMA_VERSIONS"
            )

    def test_every_version_entry_has_a_schema(self):
        """Each SCHEMA_VERSIONS entry must correspond to a real schema in ALL_SCHEMAS."""
        for version_name in SCHEMA_VERSIONS:
            assert version_name in ALL_SCHEMAS, (
                f"SCHEMA_VERSIONS has '{version_name}' but it's missing from ALL_SCHEMAS"
            )

    def test_breakage_function_returns_pass(self):
        """The run_logic_breakage_tests function itself returns (passed, 0) on a valid codebase."""
        passed, failed = run_logic_breakage_tests(strict=True)
        assert passed >= 1
        assert failed == 0


# ── Logic Gap Tests ──────────────────────────────────────────────────


class TestLogicGap:
    """Tests that every worker overrides process() — exercised on REAL subclasses."""

    def test_all_workers_override_process(self):
        """Every real BaseWorker subclass must define its own process() method."""
        workers, _, _ = discover_components()
        for worker_cls in workers:
            assert worker_cls.process is not BaseWorker.process, (
                f"{worker_cls.__name__} does not override process() — logic gap"
            )

    def test_gap_function_returns_pass(self):
        """The run_logic_gap_tests function returns (passed, 0) on a valid codebase."""
        workers, agents, subagents = discover_components()
        passed, failed = run_logic_gap_tests(workers, agents, subagents, strict=True)
        assert passed >= 1
        assert failed == 0


# ── Oversight Tests ──────────────────────────────────────────────────


class TestOversight:
    """Tests that every agent has valid MRO — exercised on REAL subclasses."""

    def test_all_agents_have_base_agent_in_mro(self):
        """Every real BaseAgent subclass must have BaseAgent in its MRO chain."""
        _, agents, _ = discover_components()
        for agent_cls in agents:
            mro_names = [c.__name__ for c in agent_cls.__mro__]
            assert "BaseAgent" in mro_names, (
                f"{agent_cls.__name__} has broken MRO: {mro_names}"
            )

    def test_all_agents_resolve_init_signature(self):
        """Every agent's __init__ should be inspectable without errors."""
        import inspect
        _, agents, _ = discover_components()
        for agent_cls in agents:
            sig = inspect.signature(agent_cls.__init__)
            assert sig is not None, f"{agent_cls.__name__}.__init__ signature failed"

    def test_oversight_function_returns_pass(self):
        """The run_oversight_tests function returns (passed, 0) on a valid codebase."""
        workers, agents, subagents = discover_components()
        passed, failed = run_oversight_tests(workers, agents, subagents, strict=True)
        assert passed >= 1
        assert failed == 0


# ── Connectivity / Broken Chain Tests ────────────────────────────────


class TestConnectivity:
    """Tests that core imports and module chain are unbroken — real imports only."""

    def test_decorators_import(self):
        """Core decorators must be importable — proves the chain is unbroken."""
        from geosupply.core.decorators import retry, timeout, cost_tracker, tracer, breaker
        assert callable(retry)
        assert callable(timeout)
        assert callable(cost_tracker)
        assert callable(tracer)
        assert callable(breaker)

    def test_event_bus_import(self):
        """EventBus must be importable and instantiable — proves messaging chain works."""
        from geosupply.core.event_bus import EventBus
        bus = EventBus()
        assert hasattr(bus, "publish")
        assert hasattr(bus, "subscribe")

    def test_config_locked_values_integrity(self):
        """Locked config values must match FA v1 spec — real config, no mocking."""
        from geosupply.config import HALLUCINATION_FLOOR, BUDGET_CAP_INR
        assert HALLUCINATION_FLOOR == 0.70, f"HALLUCINATION_FLOOR drifted to {HALLUCINATION_FLOOR}"
        assert BUDGET_CAP_INR == 500.0, f"BUDGET_CAP_INR drifted to {BUDGET_CAP_INR}"

    def test_broken_chain_function_returns_pass(self):
        """The run_broken_chain_tests function returns (passed, 0) on a valid codebase."""
        passed, failed = run_broken_chain_tests()
        assert passed >= 1
        assert failed == 0


# ── Cross-Validation Tests ───────────────────────────────────────────


class TestCrossValidation:
    """Cross-cutting tests that verify consistency across layers."""

    def test_schema_versions_have_valid_structure(self):
        """Every SCHEMA_VERSIONS entry must have 'current' and 'min_supported' keys."""
        for name, version_info in SCHEMA_VERSIONS.items():
            assert "current" in version_info, f"Schema '{name}' missing 'current' version key"
            assert "min_supported" in version_info, f"Schema '{name}' missing 'min_supported' key"
            assert version_info["current"] >= version_info["min_supported"], (
                f"Schema '{name}': current ({version_info['current']}) < min_supported ({version_info['min_supported']})"
            )

    def test_all_schemas_are_pydantic_models(self):
        """Every schema in ALL_SCHEMAS must be a genuine Pydantic BaseModel subclass."""
        from pydantic import BaseModel
        for name, schema_cls in ALL_SCHEMAS.items():
            assert issubclass(schema_cls, BaseModel), (
                f"Schema '{name}' ({schema_cls}) is not a Pydantic BaseModel"
            )

    def test_worker_error_schema_exists_and_is_functional(self):
        """WorkerError (schema #23) must exist and be instantiable with real data."""
        assert "WorkerError" in ALL_SCHEMAS, "WorkerError schema missing from ALL_SCHEMAS"
        WorkerError = ALL_SCHEMAS["WorkerError"]
        # Real instantiation — no mocking, uses valid Literal value
        err = WorkerError(
            error_type="INTERNAL",
            message="test failure",
            worker_name="TestWorker",
            retry_count=1,
            cost_inr=0.0,
        )
        assert err.error_type == "INTERNAL"
        assert err.worker_name == "TestWorker"
        assert err.retry_count == 1

"""
Unit tests for bootstrap.wire_all_supervisors().
Session 29: verifies 14 supervisors, 48+ agents, no proxies.
"""
from __future__ import annotations

import pytest


class TestBootstrap:
    """Tests for wire_all_supervisors()."""

    def test_wire_all_supervisors_returns_14_entries(self):
        """Bootstrap must wire exactly 14 supervisors."""
        from geosupply.bootstrap import wire_all_supervisors
        summary = wire_all_supervisors()
        assert len(summary) == 14, (
            f"Expected 14 supervisors, got {len(summary)}: {list(summary.keys())}"
        )

    def test_total_agent_count_is_at_least_48(self):
        """Bootstrap must wire at least 48 agents in total."""
        from geosupply.bootstrap import wire_all_supervisors
        summary = wire_all_supervisors()
        total = sum(summary.values())
        assert total >= 48, (
            f"Expected >= 48 agents total, got {total}. Summary: {summary}"
        )

    def test_wired_agent_is_not_proxy(self):
        """After wiring, IngestionSupervisor's NewsAgent must NOT be a _SupervisorAgentProxy."""
        from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
        from geosupply.agents.ingestion_agents import NewsAgent

        sup = IngestionSupervisor()
        sup.register_agent("NewsAgent", NewsAgent())

        agent = sup._agent_registry["NewsAgent"]
        agent_type_name = type(agent).__name__
        assert agent_type_name != "_SupervisorAgentProxy", (
            f"NewsAgent is still a proxy: {agent_type_name}"
        )
        assert isinstance(agent, NewsAgent), (
            f"NewsAgent is not a real NewsAgent instance: {agent_type_name}"
        )

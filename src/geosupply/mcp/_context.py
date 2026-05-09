"""
GeoSupply MCP — Standalone swarm bootstrap (no FastAPI dependency).

Builds a fully wired SwarmMaster + BudgetManagerAgent without importing
the FastAPI application — safe to call from any MCP transport (stdio, SSE).

Usage:
    from geosupply.mcp._context import get_swarm, get_budget

The two getters are lru_cache'd so the swarm is initialised exactly once
per process, regardless of how many MCP tool calls arrive concurrently.
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_swarm():
    """Return a fully registered SwarmMaster singleton."""
    # Force all subclass registrations before building the swarm
    import geosupply.workers    # noqa: F401
    import geosupply.agents     # noqa: F401
    import geosupply.supervisors  # noqa: F401
    import geosupply.subagents  # noqa: F401

    from geosupply.orchestrator.swarm_master import SwarmMaster
    from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
    from geosupply.supervisors.nlp_supervisor import NLPSupervisor
    from geosupply.supervisors.quality_supervisor import QualitySupervisor
    from geosupply.supervisors.intel_supervisor import IntelSupervisor
    from geosupply.supervisors.infra_supervisor import InfraSupervisor
    from geosupply.supervisors.disaster_recovery_supervisor import DisasterRecoverySupervisor
    from geosupply.supervisors.ml_supervisor import MLSupervisor
    from geosupply.supervisors.india_supervisor import IndiaSupervisor
    from geosupply.supervisors.dashboard_supervisor import DashboardSupervisor
    from geosupply.supervisors.dev_supervisor import DevSupervisor
    from geosupply.supervisors.test_supervisor import TestSupervisor
    from geosupply.supervisors.tech_supervisor import TechSupervisor
    from geosupply.supervisors.marketing_supervisor import MarketingSupervisor
    from geosupply.supervisors.loophole_hunter_supervisor import LoopholeHunterSupervisor
    from geosupply.bootstrap import wire_all_supervisors

    sm = SwarmMaster()
    sm.register_supervisor("IngestionSupervisor",        IngestionSupervisor())
    sm.register_supervisor("NLPSupervisor",              NLPSupervisor())
    sm.register_supervisor("QualitySupervisor",          QualitySupervisor())
    sm.register_supervisor("IntelSupervisor",            IntelSupervisor())
    sm.register_supervisor("InfraSupervisor",            InfraSupervisor())
    sm.register_supervisor("DisasterRecoverySupervisor", DisasterRecoverySupervisor())
    sm.register_supervisor("MLSupervisor",               MLSupervisor())
    sm.register_supervisor("IndiaSupervisor",            IndiaSupervisor())
    sm.register_supervisor("DashboardSupervisor",        DashboardSupervisor())
    sm.register_supervisor("DevSupervisor",              DevSupervisor())
    sm.register_supervisor("TestSupervisor",             TestSupervisor())
    sm.register_supervisor("TechSupervisor",             TechSupervisor())
    sm.register_supervisor("MarketingSupervisor",        MarketingSupervisor())
    sm.register_supervisor("LoopholeHunterSupervisor",   LoopholeHunterSupervisor())

    summary = wire_all_supervisors()
    logger.info("MCP context: bootstrap complete — %d supervisors wired", len(summary))
    return sm


@lru_cache(maxsize=1)
def get_budget():
    """Return a singleton BudgetManagerAgent."""
    from geosupply.agents.budget_manager_agent import BudgetManagerAgent
    return BudgetManagerAgent()

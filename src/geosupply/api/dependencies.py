"""
GeoSupply AI — FastAPI dependency injection (Phase 9).

Provides singleton SwarmMaster + BudgetManagerAgent via lru_cache.
All 14 supervisors registered at startup.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache

from geosupply.orchestrator.swarm_master import SwarmMaster
from geosupply.agents.budget_manager_agent import BudgetManagerAgent
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


@lru_cache(maxsize=1)
def get_swarm_master() -> SwarmMaster:
    """Return a singleton SwarmMaster with all 14 supervisors registered."""
    sm = SwarmMaster()
    sm.register_supervisor("IngestionSupervisor",         IngestionSupervisor())
    sm.register_supervisor("NLPSupervisor",               NLPSupervisor())
    sm.register_supervisor("QualitySupervisor",           QualitySupervisor())
    sm.register_supervisor("IntelSupervisor",             IntelSupervisor())
    sm.register_supervisor("InfraSupervisor",             InfraSupervisor())
    sm.register_supervisor("DisasterRecoverySupervisor",  DisasterRecoverySupervisor())
    sm.register_supervisor("MLSupervisor",                MLSupervisor())
    sm.register_supervisor("IndiaSupervisor",             IndiaSupervisor())
    sm.register_supervisor("DashboardSupervisor",         DashboardSupervisor())
    sm.register_supervisor("DevSupervisor",               DevSupervisor())
    sm.register_supervisor("TestSupervisor",              TestSupervisor())
    sm.register_supervisor("TechSupervisor",              TechSupervisor())
    sm.register_supervisor("MarketingSupervisor",         MarketingSupervisor())
    sm.register_supervisor("LoopholeHunterSupervisor",    LoopholeHunterSupervisor())
    return sm


@lru_cache(maxsize=1)
def get_budget_agent() -> BudgetManagerAgent:
    """Return a singleton BudgetManagerAgent."""
    return BudgetManagerAgent()


# In-process task store (replaced in tests via app.dependency_overrides).
# Lock guards concurrent reads/writes across async request handlers.
_TASK_STORE: dict[str, dict] = {}
_TASK_STORE_LOCK: asyncio.Lock = asyncio.Lock()


def get_task_store() -> dict[str, dict]:
    return _TASK_STORE


def get_task_store_lock() -> asyncio.Lock:
    return _TASK_STORE_LOCK


# FastAPI async dependency wrappers
async def swarm_master_dep() -> SwarmMaster:
    return get_swarm_master()


async def budget_dep() -> BudgetManagerAgent:
    return get_budget_agent()


async def task_store_dep() -> dict[str, dict]:
    return get_task_store()


async def task_store_lock_dep() -> asyncio.Lock:
    return get_task_store_lock()

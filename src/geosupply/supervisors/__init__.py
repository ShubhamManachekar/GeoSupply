"""GeoSupply AI — Supervisors package.

Exports all concrete supervisors implemented in this repository.
"""

# Phase 6: Supervisor Layer — Session 22 (5 initial)
from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
from geosupply.supervisors.quality_supervisor import QualitySupervisor
from geosupply.supervisors.nlp_supervisor import NLPSupervisor
from geosupply.supervisors.intel_supervisor import IntelSupervisor
from geosupply.supervisors.infra_supervisor import InfraSupervisor

# Phase 6: Supervisor Layer — Session 28 (9 new)
from geosupply.supervisors.disaster_recovery_supervisor import DisasterRecoverySupervisor
from geosupply.supervisors.ml_supervisor import MLSupervisor
from geosupply.supervisors.india_supervisor import IndiaSupervisor
from geosupply.supervisors.dashboard_supervisor import DashboardSupervisor
from geosupply.supervisors.dev_supervisor import DevSupervisor
from geosupply.supervisors.test_supervisor import TestSupervisor
from geosupply.supervisors.tech_supervisor import TechSupervisor
from geosupply.supervisors.marketing_supervisor import MarketingSupervisor
from geosupply.supervisors.loophole_hunter_supervisor import LoopholeHunterSupervisor

__all__ = [
    "IngestionSupervisor",
    "QualitySupervisor",
    "NLPSupervisor",
    "IntelSupervisor",
    "InfraSupervisor",
    "DisasterRecoverySupervisor",
    "MLSupervisor",
    "IndiaSupervisor",
    "DashboardSupervisor",
    "DevSupervisor",
    "TestSupervisor",
    "TechSupervisor",
    "MarketingSupervisor",
    "LoopholeHunterSupervisor",
]

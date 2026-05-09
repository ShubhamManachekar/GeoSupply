"""
GeoSupply AI — Bootstrap
Wires all real agent instances into all 14 supervisors, replacing proxy stubs.

All imports are local (inside the function) to avoid circular imports at module load time.
Returns dict[str, int] = {supervisor_name: agents_wired_count}.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def wire_all_supervisors() -> dict[str, int]:
    """
    Instantiate all 14 supervisors and register real agents into each one.
    Returns a summary dict of {supervisor_name: agents_wired_count}.
    """
    # ── Supervisors ──────────────────────────────────────────────────────────
    from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
    from geosupply.supervisors.nlp_supervisor import NLPSupervisor
    from geosupply.supervisors.quality_supervisor import QualitySupervisor
    from geosupply.supervisors.intel_supervisor import IntelSupervisor
    from geosupply.supervisors.ml_supervisor import MLSupervisor
    from geosupply.supervisors.india_supervisor import IndiaSupervisor
    from geosupply.supervisors.dashboard_supervisor import DashboardSupervisor
    from geosupply.supervisors.dev_supervisor import DevSupervisor
    from geosupply.supervisors.test_supervisor import TestSupervisor
    from geosupply.supervisors.tech_supervisor import TechSupervisor
    from geosupply.supervisors.marketing_supervisor import MarketingSupervisor
    from geosupply.supervisors.loophole_hunter_supervisor import LoopholeHunterSupervisor
    from geosupply.supervisors.disaster_recovery_supervisor import DisasterRecoverySupervisor
    from geosupply.supervisors.infra_supervisor import InfraSupervisor

    # ── Domain agents ─────────────────────────────────────────────────────────
    from geosupply.agents.ingestion_agents import (
        NewsAgent, IndiaAPIAgent, TelegramAgent, AISAgent
    )
    from geosupply.agents.nlp_agents import (
        SentimentAgent, NERAgent, ClaimAgent, TranslationAgent, PropagandaAgent
    )
    from geosupply.agents.quality_agents import NLPAgent, HallucinationAgent, SourceCredAgent
    from geosupply.agents.intel_agents import (
        SupplierAgent, SanctionsAgent, CyberAgent, VerifierAgent, AuthorAgent
    )
    from geosupply.agents.ml_agents import (
        StressScoreAgent, ConflictPredictAgent, SupplierRankAgent, SanctionClassifyAgent
    )
    from geosupply.agents.india_agents import (
        IndiaPortAgent, IndiaMonsoonAgent, IndiaULIPAgent, IndiaPoliticalAgent
    )
    from geosupply.agents.dashboard_agents import (
        MetricPullAgent, AlertRenderAgent, KPIUpdateAgent
    )
    from geosupply.agents.dev_agents import SchemaMigrateAgent, LintCheckAgent, TestRunAgent
    from geosupply.agents.test_agents import UnitTestAgent, IntegrationTestAgent, CoverageAgent
    from geosupply.agents.tech_agents import APIHealthAgent, DBCheckAgent, CacheFlushAgent
    from geosupply.agents.marketing_agents import (
        TweetGenAgent, PredictionPostAgent, AnalyticsAgent, ContentGenAgent
    )
    from geosupply.agents.loophole_agents import (
        LoopholeHunterAgent, PenTestAgent, OverrideMonitorAgent
    )
    from geosupply.agents.dr_agents import (
        BackupAgent, CostProjectionAgent, RestoreAgent, FailoverAgent
    )
    # Infra agents (already exist)
    from geosupply.agents.health_check_agent import HealthCheckAgent
    from geosupply.agents.logging_agent import LoggingAgent
    from geosupply.agents.moe_router_agent import MoERouterAgent
    from geosupply.agents.budget_manager_agent import BudgetManagerAgent
    from geosupply.agents.route_manager_agent import RouteManagerAgent
    from geosupply.agents.security_agent import SecurityAgent
    from geosupply.agents.swarm_manager_agent import SwarmManagerAgent
    from geosupply.agents.knowledge_graph_agent import KnowledgeGraphAgent
    from geosupply.agents.fact_check_agent import FactCheckAgent
    from geosupply.agents.summarization_audit_agent import SummarizationAuditAgent
    from geosupply.agents.timeline_generator_agent import TimelineGeneratorAgent

    summary: dict[str, int] = {}

    # ── 1. IngestionSupervisor ────────────────────────────────────────────────
    ingestion_sup = IngestionSupervisor()
    ingestion_agents = {
        "NewsAgent": NewsAgent(),
        "IndiaAPIAgent": IndiaAPIAgent(),
        "TelegramAgent": TelegramAgent(),
        "AISAgent": AISAgent(),
    }
    for name, agent in ingestion_agents.items():
        ingestion_sup.register_agent(name, agent)
    summary["IngestionSupervisor"] = len(ingestion_agents)

    # ── 2. NLPSupervisor ──────────────────────────────────────────────────────
    nlp_sup = NLPSupervisor()
    nlp_agents = {
        "SentimentAgent": SentimentAgent(),
        "NERAgent": NERAgent(),
        "ClaimAgent": ClaimAgent(),
        "TranslationAgent": TranslationAgent(),
        "PropagandaAgent": PropagandaAgent(),
    }
    for name, agent in nlp_agents.items():
        nlp_sup.register_agent(name, agent)
    summary["NLPSupervisor"] = len(nlp_agents)

    # ── 3. QualitySupervisor ──────────────────────────────────────────────────
    quality_sup = QualitySupervisor()
    quality_agents = {
        "NLPAgent": NLPAgent(),
        "HallucinationAgent": HallucinationAgent(),
        "SourceCredAgent": SourceCredAgent(),
    }
    for name, agent in quality_agents.items():
        quality_sup.register_agent(name, agent)
    summary["QualitySupervisor"] = len(quality_agents)

    # ── 4. IntelSupervisor ────────────────────────────────────────────────────
    intel_sup = IntelSupervisor()
    intel_agents = {
        "SupplierAgent": SupplierAgent(),
        "SanctionsAgent": SanctionsAgent(),
        "CyberAgent": CyberAgent(),
        "VerifierAgent": VerifierAgent(),
        "AuthorAgent": AuthorAgent(),
    }
    for name, agent in intel_agents.items():
        intel_sup.register_agent(name, agent)
    summary["IntelSupervisor"] = len(intel_agents)

    # ── 5. MLSupervisor ───────────────────────────────────────────────────────
    ml_sup = MLSupervisor()
    ml_agents = {
        "StressScoreAgent": StressScoreAgent(),
        "ConflictPredictAgent": ConflictPredictAgent(),
        "SupplierRankAgent": SupplierRankAgent(),
        "SanctionClassifyAgent": SanctionClassifyAgent(),
    }
    for name, agent in ml_agents.items():
        ml_sup.register_agent(name, agent)
    summary["MLSupervisor"] = len(ml_agents)

    # ── 6. IndiaSupervisor ────────────────────────────────────────────────────
    india_sup = IndiaSupervisor()
    india_agents = {
        "IndiaPortAgent": IndiaPortAgent(),
        "IndiaMonsoonAgent": IndiaMonsoonAgent(),
        "IndiaULIPAgent": IndiaULIPAgent(),
        "IndiaPoliticalAgent": IndiaPoliticalAgent(),
    }
    for name, agent in india_agents.items():
        india_sup.register_agent(name, agent)
    summary["IndiaSupervisor"] = len(india_agents)

    # ── 7. DashboardSupervisor ────────────────────────────────────────────────
    dashboard_sup = DashboardSupervisor()
    dashboard_agents = {
        "MetricPullAgent": MetricPullAgent(),
        "AlertRenderAgent": AlertRenderAgent(),
        "KPIUpdateAgent": KPIUpdateAgent(),
    }
    for name, agent in dashboard_agents.items():
        dashboard_sup.register_agent(name, agent)
    summary["DashboardSupervisor"] = len(dashboard_agents)

    # ── 8. DevSupervisor ──────────────────────────────────────────────────────
    dev_sup = DevSupervisor()
    dev_agents = {
        "SchemaMigrateAgent": SchemaMigrateAgent(),
        "LintCheckAgent": LintCheckAgent(),
        "TestRunAgent": TestRunAgent(),
    }
    for name, agent in dev_agents.items():
        dev_sup.register_agent(name, agent)
    summary["DevSupervisor"] = len(dev_agents)

    # ── 9. TestSupervisor ─────────────────────────────────────────────────────
    test_sup = TestSupervisor()
    test_agents = {
        "UnitTestAgent": UnitTestAgent(),
        "IntegrationTestAgent": IntegrationTestAgent(),
        "CoverageAgent": CoverageAgent(),
    }
    for name, agent in test_agents.items():
        test_sup.register_agent(name, agent)
    summary["TestSupervisor"] = len(test_agents)

    # ── 10. TechSupervisor ────────────────────────────────────────────────────
    tech_sup = TechSupervisor()
    tech_agents = {
        "APIHealthAgent": APIHealthAgent(),
        "DBCheckAgent": DBCheckAgent(),
        "CacheFlushAgent": CacheFlushAgent(),
    }
    for name, agent in tech_agents.items():
        tech_sup.register_agent(name, agent)
    summary["TechSupervisor"] = len(tech_agents)

    # ── 11. MarketingSupervisor ───────────────────────────────────────────────
    marketing_sup = MarketingSupervisor()
    marketing_agents = {
        "TweetGenAgent": TweetGenAgent(),
        "PredictionPostAgent": PredictionPostAgent(),
        "AnalyticsAgent": AnalyticsAgent(),
        "ContentGenAgent": ContentGenAgent(),
    }
    for name, agent in marketing_agents.items():
        marketing_sup.register_agent(name, agent)
    summary["MarketingSupervisor"] = len(marketing_agents)

    # ── 12. LoopholeHunterSupervisor ──────────────────────────────────────────
    loophole_sup = LoopholeHunterSupervisor()
    loophole_agents = {
        "LoopholeHunterAgent": LoopholeHunterAgent(),
        "PenTestAgent": PenTestAgent(),
        "OverrideMonitorAgent": OverrideMonitorAgent(),
    }
    for name, agent in loophole_agents.items():
        loophole_sup.register_agent(name, agent)
    summary["LoopholeHunterSupervisor"] = len(loophole_agents)

    # ── 13. DisasterRecoverySupervisor ────────────────────────────────────────
    dr_sup = DisasterRecoverySupervisor()
    dr_agents = {
        "BackupAgent": BackupAgent(),
        "CostProjectionAgent": CostProjectionAgent(),
        "RestoreAgent": RestoreAgent(),
        "FailoverAgent": FailoverAgent(),
    }
    for name, agent in dr_agents.items():
        dr_sup.register_agent(name, agent)
    summary["DisasterRecoverySupervisor"] = len(dr_agents)

    # ── 14. InfraSupervisor ───────────────────────────────────────────────────
    infra_sup = InfraSupervisor()
    infra_agents = {
        "LoggingAgent": LoggingAgent(),
        "HealthCheckAgent": HealthCheckAgent(),
        "SecurityAgent": SecurityAgent(),
        "FactCheckAgent": FactCheckAgent(),
        "BudgetManagerAgent": BudgetManagerAgent(),
        "RouteManagerAgent": RouteManagerAgent(),
        "MoERouterAgent": MoERouterAgent(),
        "SwarmManagerAgent": SwarmManagerAgent(),
        "KnowledgeGraphAgent": KnowledgeGraphAgent(),
    }
    for name, agent in infra_agents.items():
        infra_sup.register_agent(name, agent)
    summary["InfraSupervisor"] = len(infra_agents)

    total = sum(summary.values())
    logger.info(
        "wire_all_supervisors: %d supervisors, %d agents total wired",
        len(summary), total,
    )
    return summary

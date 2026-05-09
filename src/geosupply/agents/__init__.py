"""GeoSupply AI — Agents package.

Exports concrete agents implemented in this repository state.
"""

# Phase 0-1: Core agents
from geosupply.agents.health_check_agent import HealthCheckAgent
from geosupply.agents.logging_agent import LoggingAgent
from geosupply.agents.moe_router_agent import MoERouterAgent
from geosupply.agents.budget_manager_agent import BudgetManagerAgent
from geosupply.agents.route_manager_agent import RouteManagerAgent
from geosupply.agents.security_agent import SecurityAgent
from geosupply.agents.swarm_manager_agent import SwarmManagerAgent
from geosupply.agents.timeline_generator_agent import TimelineGeneratorAgent
# Phase 7: Knowledge Graph
from geosupply.agents.knowledge_graph_agent import KnowledgeGraphAgent
# Phase 6+: Quality agents
from geosupply.agents.fact_check_agent import FactCheckAgent
from geosupply.agents.summarization_audit_agent import SummarizationAuditAgent

# Session 29: Domain agent modules
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
from geosupply.agents.dashboard_agents import MetricPullAgent, AlertRenderAgent, KPIUpdateAgent
from geosupply.agents.dev_agents import SchemaMigrateAgent, LintCheckAgent, TestRunAgent
from geosupply.agents.test_agents import UnitTestAgent, IntegrationTestAgent, CoverageAgent
from geosupply.agents.tech_agents import APIHealthAgent, DBCheckAgent, CacheFlushAgent
from geosupply.agents.marketing_agents import (
    TweetGenAgent, PredictionPostAgent, AnalyticsAgent, ContentGenAgent
)
from geosupply.agents.loophole_agents import LoopholeHunterAgent, PenTestAgent, OverrideMonitorAgent
from geosupply.agents.dr_agents import BackupAgent, CostProjectionAgent, RestoreAgent, FailoverAgent

__all__ = [
    # Core infra agents
    "HealthCheckAgent",
    "LoggingAgent",
    "MoERouterAgent",
    "BudgetManagerAgent",
    "RouteManagerAgent",
    "SecurityAgent",
    "SwarmManagerAgent",
    "TimelineGeneratorAgent",
    "KnowledgeGraphAgent",
    "FactCheckAgent",
    "SummarizationAuditAgent",
    # Ingestion
    "NewsAgent",
    "IndiaAPIAgent",
    "TelegramAgent",
    "AISAgent",
    # NLP
    "SentimentAgent",
    "NERAgent",
    "ClaimAgent",
    "TranslationAgent",
    "PropagandaAgent",
    # Quality
    "NLPAgent",
    "HallucinationAgent",
    "SourceCredAgent",
    # Intel
    "SupplierAgent",
    "SanctionsAgent",
    "CyberAgent",
    "VerifierAgent",
    "AuthorAgent",
    # ML
    "StressScoreAgent",
    "ConflictPredictAgent",
    "SupplierRankAgent",
    "SanctionClassifyAgent",
    # India
    "IndiaPortAgent",
    "IndiaMonsoonAgent",
    "IndiaULIPAgent",
    "IndiaPoliticalAgent",
    # Dashboard
    "MetricPullAgent",
    "AlertRenderAgent",
    "KPIUpdateAgent",
    # Dev
    "SchemaMigrateAgent",
    "LintCheckAgent",
    "TestRunAgent",
    # Test
    "UnitTestAgent",
    "IntegrationTestAgent",
    "CoverageAgent",
    # Tech
    "APIHealthAgent",
    "DBCheckAgent",
    "CacheFlushAgent",
    # Marketing
    "TweetGenAgent",
    "PredictionPostAgent",
    "AnalyticsAgent",
    "ContentGenAgent",
    # Loophole
    "LoopholeHunterAgent",
    "PenTestAgent",
    "OverrideMonitorAgent",
    # DR
    "BackupAgent",
    "CostProjectionAgent",
    "RestoreAgent",
    "FailoverAgent",
]

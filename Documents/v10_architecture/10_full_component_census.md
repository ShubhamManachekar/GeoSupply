# Chapter 10: Complete v10 Component Census — Every Agent, Worker, SubAgent

## TOTAL: 136 Components Across 7 Layers + LoopholeHunter

---

## Layer 0 — Human + Admin Interface

| Component | Type | New? |
|-----------|------|------|
| Admin CLI (`geosupply`) | CLI tool | v9 |
| Admin Portal (Streamlit Page 10) | Web UI | v9 |
| Override Panel | Web UI | v9 |
| Telegram Bot (notifications) | Bot | v9 |
| LoopholeHunter Dashboard (Page 12) | Web UI | **v10** |
| Cyber Threat Dashboard (Page 11) | Web UI | v9 |

---

## Layer 1 — Orchestrator (1)

| Component | New? | Key Change in v10 |
|-----------|------|-------------------|
| SwarmMaster | v8 | + Internal circuit breakers, cost projection, watchdog, MoA fallback, schema versioning |

---

## Layer 2 — Supervisors (14)

| # | Supervisor | Domain | New? | Agents Managed |
|---|-----------|--------|------|----------------|
| 1 | IngestSupervisor | Ingestion | v8 | 4 workers |
| 2 | NLPSupervisor | NLP | v8 | 5 workers |
| 3 | IntelSupervisor | Intelligence | v8 | 7 workers + SourceClusterAgent |
| 4 | MLSupervisor | ML | v8 | 3 workers |
| 5 | IndiaSupervisor | India APIs | v8 | 7 workers |
| 6 | DashboardSupervisor | Dashboard | v8 | 2 workers |
| 7 | InfraSupervisor | Infrastructure | v8 | 9 singletons |
| 8 | QualitySupervisor | Quality | v8 | FactCheck + Hallucination + SummarizationAudit |
| 9 | DevSupervisor | Development | v8 | 4 dev agents |
| 10 | TestSupervisor | Testing | v8 | 5 test agents |
| 11 | TechSupervisor | Tech team | v9 | TechScout + APIScan + DepUpdate + Deploy |
| 12 | MarketingSupervisor | Marketing | v9 | Content + Twitter + Prediction + Analytics + Newsletter |
| 13 | **LoopholeHunterSupervisor** | Audit | **v10** | LoopholeHunter + OverrideAudit + PenTest + SummarizationAudit |
| 14 | **DisasterRecoverySupervisor** | DR | **v10** | Backup + Watchdog + CostProjection |

---

## Layer 3 — Agents (38)

### Infrastructure Singletons (9)

| # | Agent | v8/v9/v10 | Always On |
|---|-------|-----------|-----------|
| 1 | LoggingAgent | v8 | Yes |
| 2 | FactCheckAgent | v8 | Yes |
| 3 | HealthCheckAgent | v8 | Yes |
| 4 | SecurityAgent | v8 | Yes |
| 5 | AuditorAgent | v8 | Yes |
| 6 | SourceFeedbackAgent | v8 | Yes |
| 7 | CyberDefenseAgent | v9 | Yes |
| 8 | **WatchdogAgent** | **v10** | Yes (separate process) |
| 9 | **InputGuardAgent** | **v10** | Yes |

### Intelligence & Knowledge Agents (4)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 10 | KnowledgeGraphAgent | v9 |
| 11 | PerformanceLearnerAgent | v9 |
| 12 | **SourceClusterAgent** | **v10** |
| 13 | **ChannelVerificationAgent** | **v10** |

### Dev Agents (4)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 14 | ScaffoldAgent | v8 |
| 15 | CodeReviewAgent | v8 |
| 16 | DocGenAgent | v8 |
| 17 | RefactorAgent | v8 |

### Test Agents (5)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 18 | UnitTestAgent | v8 |
| 19 | IntegrationTestAgent | v8 |
| 20 | LoadTestAgent | v8 |
| 21 | RegressionTestAgent | v8 |
| 22 | ContractTestAgent | v8 |

### Tech Team Agents (4)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 23 | TechScoutAgent | v9 |
| 24 | APIScanAgent | v9 |
| 25 | DepUpdateAgent | v9 |
| 26 | DeployAgent | v9 |

### Marketing Agents (5)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 27 | ContentGeneratorAgent | v9 |
| 28 | TwitterPublisherAgent | v9 |
| 29 | PredictionAgent | v9 |
| 30 | RevenueTrackerAgent | v9 |
| 31 | **AnalyticsAgent** | **v10** |
| 32 | **NewsletterAgent** | **v10** |

### Audit & Security Agents (6)

| # | Agent | v8/v9/v10 |
|---|-------|-----------|
| 33 | **LoopholeHunterAgent** | **v10** |
| 34 | **OverrideAuditAgent** | **v10** |
| 35 | **PenTestAgent** | **v10** |
| 36 | **SummarizationAuditAgent** | **v10** |
| 37 | **BackupAgent** | **v10** |
| 38 | **CostProjectionAgent** | **v10** |

---

## Layer 4 — SubAgents (13)

| # | SubAgent | v8/v9/v10 | Pipeline |
|---|---------|-----------|----------|
| 1 | RAGPipelineSubAgent | v9 | Plan→Retrieve→Rerank→Fuse→Synth |
| 2 | SourceFeedbackSubAgent | v9 | Penalty calculation + update |
| 3 | SemanticDriftMonitor | v9 | Weekly embedding drift analysis |
| 4 | HallucinationCheckSubAgent | v9 | FactCheck orchestration |
| 5 | ReasonPlanSubAgent | v9 | RAG planning step |
| 6 | BriefSynthSubAgent | v9 | MoA 3-proposer synthesis |
| 7 | RetrieveSubAgent | v9 | Parallel vector retrieval |
| 8 | RerankSubAgent | v9 | Cross-encoder reranking |
| 9 | **SummarizationVerifierSubAgent** | **v10** | Semantic distortion check |
| 10 | **SourceClusterSubAgent** | **v10** | IP/domain/author clustering |
| 11 | **OverridePatternSubAgent** | **v10** | Admin override pattern detection |
| 12 | **MoAFallbackSubAgent** | **v10** | 4-level aggregation fallback |
| 13 | **PenetrationTestSubAgent** | **v10** | 8-test penetration suite |

---

## Layer 5 — Workers (40)

| # | Worker | Domain | Tier | STATIC | v8/v9/v10 |
|---|--------|--------|------|--------|-----------|
| 1 | NewsWorker | Ingestion | 0 | No | v8 |
| 2 | IndiaAPIWorker | Ingestion | 0 | No | v8 |
| 3 | TelegramWorker | Ingestion | 0 | No | v8 |
| 4 | AISWorker | Ingestion | 0 | No | v8 |
| 5 | LangWorker | NLP | 0 | No | v8 |
| 6 | TranslationWorker | NLP | 1-2 | No | v8 |
| 7 | SentimentWorker | NLP | 1 | **Yes** | v8 |
| 8 | NERWorker | NLP | 1 | **Yes** | v8 |
| 9 | EmbedWorker | NLP | 0 | No | v8 |
| 10 | ClaimWorker | Intel | 1 | **Yes** | v8 |
| 11 | VerifierWorker | Intel | 3 | No | v8 |
| 12 | SourceCredWorker | Intel | 1 | **Yes** | v8 |
| 13 | AuthorWorker | Intel | 3 | No | v8 |
| 14 | NetworkWorker | Intel | 2 | No | v8 |
| 15 | CIBWorker | Intel | 2 | No | v8 |
| 16 | PropagandaWorker | Intel | 2 | No | v8 |
| 17 | CyberThreatWorker | Intel | 1 | **Yes** | v9 |
| 18 | ConflictWorker | ML | 0 | No | v8 |
| 19 | RetrainWorker | ML | 0 | No | v8 |
| 20 | DriftWorker | ML | 0 | No | v8 |
| 21 | IndiaIntelWorker | India | 1 | No | v8 |
| 22 | MonsoonWorker | India | 0 | No | v8 |
| 23 | StressWorker | Supply | 3 | No | v8 |
| 24 | SupplierWorker | Supply | 1 | **Yes** | v8 |
| 25 | SanctionsWorker | Supply | 1 | **Yes** | v8 |
| 26 | RAGWorker | RAG | 0-3 | No | v8 |
| 27 | GraphRAGWorker | RAG | 3 | No | v8 |
| 28 | BriefWorker | RAG | 3 | No | v8 |
| 29 | StreamlitWorker | Dashboard | 0 | No | v8 |
| 30 | CIVisualisationWorker | Dashboard | 0 | No | v8 |
| 31 | ContextBuildWorker | RAG | 0 | No | v8 |
| 32 | ReasonPlanWorker | RAG | 3 | No | v8 |
| 33 | **ChannelFingerprintWorker** | Ingestion | 0 | No | **v10** |
| 34 | **InputSanitiserWorker** | Security | 0 | No | **v10** |
| 35 | **CostProjectionWorker** | Infra | 0 | No | **v10** |
| 36 | **TwitterAPIWorker** | Marketing | 0 | No | **v10** |
| 37 | **NewsletterWorker** | Marketing | 0 | No | **v10** |
| 38 | **SBOMWorker** | Tech | 0 | No | **v10** |
| 39 | **BackupWorker** | DR | 0 | No | **v10** |
| 40 | **LoopholeDetectionWorker** | Audit | 0 | No | **v10** |

---

## Layer 6 — Model & Skill Pool

| Model | Tier | Location | Cost (INR) |
|-------|------|----------|-----------|
| llama3.2:3b | 1 | PC + Groq | ₹0 |
| qwen2.5:14b | 2 | PC + GCP T4 | ₹0 (PC) / ₹100 (GCP) |
| GPT-OSS:20b | 3 | PC | ₹0 |
| llama-3.3-70b | 3 fallback | Groq | ₹0 |
| qwen-qwq-32b | 2 fallback | Groq | ₹0 |
| claude-sonnet-4-6 | Emergency | API | ₹0.25/call |
| XGBoost (ConflictPredictor) | ML | PC | ₹0 |
| sentence-transformers | Embedding | PC | ₹0 |

---

## Growth Summary

```
v8:   ~71 components (5 layers)
v9:  ~107 components (7 layers)
v10: ~136 components (7 layers + LoopholeHunter cross-layer)

DELTA v9→v10:
    +8  workers
    +5  subagents
    +12 agents
    +2  supervisors
    +6  skills
    +14 APIs
    +8  new schemas
    +9  new test scenarios
    +24 continuous audit checks
    +8  penetration tests
```

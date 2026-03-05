# Part I: Foundation — Principles, Topology & Evolution

## 1.1 What Is GeoSupply AI?

GeoSupply AI is an **India-centric geopolitical supply chain intelligence platform** powered by a multi-agent swarm. It ingests news, OSINT, government data, and satellite feeds, then produces actionable intelligence briefs about geopolitical risks, supply chain disruptions, and trade flow impacts — all denominated in INR.

---

## 1.2 Architecture Evolution

| Version | Layers | Workers | Agents | Key Feature |
|---------|--------|---------|--------|-------------|
| **v8.0** | 5 | 32 | 15 | MoE routing, STATIC decoder, RAG pipeline |
| **v9.0** | 7 | 32 | 26 | SubAgent/Supervisor layers, EventBus, Self-Learning, Admin CLI, Marketing, CyberDefense |
| **v10.0** | 7+LH | **40** | **38** | LoopholeHunter, 14 logic gap fixes, 11 security loopholes fixed, DR, PenTest |

**Final (v10.0)**: 136 components, 42+ APIs, 30 skills, 24 continuous audit checks.

---

## 1.3 Complete Swarm Topology — Final

```
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║                    GEOSUPPLY AI — FINAL SWARM TOPOLOGY v10.0                         ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 0 — HUMAN + ADMIN                                                            ║
║  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐       ║
║  │  Claude Chat          │  │  Google Antigravity   │  │  Admin CLI/Portal    │       ║
║  │  Architecture Review  │  │  Code + Orchestration │  │  Override + Monitor  │       ║
║  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘       ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 1 — ORCHESTRATOR (SwarmMaster v10)                                           ║
║  ┌────────────────────────────────────────────────────────────────────────────────┐ ║
║  │ MoE Gating │ Task Decomposer │ Dependency Resolver │ Budget Mgr (INR)        │ ║
║  │ Session Coordinator │ ColdStart Guard │ Pipeline Rectifier │ Routing Advisor  │ ║
║  │ Backpressure Controller │ InternalCircuitBreakerRegistry (v10)                │ ║
║  │ CostProjectionIntegration │ LoopholeEventConsumer │ WatchdogRegistration(v10) │ ║
║  │ MoAFallbackIntegration │ SchemaVersionManager │ EnhancedDegradedMode (v10)   │ ║
║  └────────────────────────────────────────────────────────────────────────────────┘ ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 2 — SUPERVISORS (14)                                                         ║
║  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          ║
║  │ Ingest   ││ NLP      ││ Intel    ││ ML       ││ India    ││Dashboard │          ║
║  │Super     ││Super     ││Super     ││Super     ││Super     ││Super     │          ║
║  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          ║
║  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          ║
║  │ Infra    ││ Quality  ││ Dev      ││ Test     ││ Tech     ││Marketing │          ║
║  │Super     ││Super     ││Super     ││Super     ││Super     ││Super     │          ║
║  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          ║
║  ┌──────────────────────┐ ┌──────────────────────┐  ◄── NEW v10                    ║
║  │ LoopholeHunterSuper  │ │ DisasterRecoverySuper │                                  ║
║  └──────────────────────┘ └──────────────────────┘                                  ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 3 — AGENTS (38)                                                               ║
║  INFRA(9):    Logging FactCheck HealthCheck Security Auditor SrcFeedback             ║
║               CyberDefense Watchdog(v10) InputGuard(v10)                             ║
║  INTEL(4):    KnowledgeGraph PerformanceLearner SourceCluster(v10) ChannelVerif(v10) ║
║  DEV(4):      Scaffold CodeReview DocGen Refactor                                    ║
║  TEST(5):     UnitTest IntegTest LoadTest Regression ContractTest                    ║
║  TECH(4):     TechScout APIScan DepUpdate Deploy                                     ║
║  MARKETING(5): ContentGenerator TwitterPublisher Prediction Analytics(v10) NL(v10)   ║
║  REVENUE(1):  RevenueTracker                                                         ║
║  AUDIT(6):    LoopholeHunter(v10) OverrideAudit(v10) PenTest(v10)                   ║
║               SummarizationAudit(v10) Backup(v10) CostProjection(v10)                ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 4 — SUBAGENTS (13)                                                            ║
║  RAG: ReasonPlan Retrieve Rerank ContextBuild BriefSynth                             ║
║  QA:  SourceFeedback SemanticDrift HallucinationCheck                                ║
║  v10: SummarizationVerifier SourceCluster OverridePattern MoAFallback PenTest        ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 5 — WORKERS (40)                                                              ║
║  INGEST(4):    News IndiaAPI Telegram AIS                                            ║
║  NLP(5):       Lang Translation Sentiment⚡ NER⚡ Embed                              ║
║  INTEL(7):     Claim⚡ Verifier SrcCred⚡ Author Network CIB Propaganda CyberThreat  ║
║  ML(3):        Conflict Retrain Drift                                                ║
║  RAG(5):       RAG GraphRAG Brief ContextBuild ReasonPlan                            ║
║  SUPPLY(3):    Stress Supplier⚡ Sanctions⚡                                          ║
║  INDIA(2):     IndiaIntel Monsoon                                                    ║
║  DASHBOARD(2): Streamlit CIVisualisation                                             ║
║  v10(8):       ChannelFingerprint⚡ InputSanitiser CostProjection TwitterAPI          ║
║                Newsletter SBOM Backup LoopholeDetection                              ║
║                                                                                      ║
║  ⚡ = STATIC decoder mandatory (Tier-1 schema-strict)                                ║
║                                       │                                               ║
║  ═════════════════════════════════════════════════════════════════════════════════    ║
║                                                                                      ║
║  LAYER 6 — MODEL & SKILL POOL                                                       ║
║  LLMs:    GPT-OSS:20b  qwen2.5:14b  llama3.2:3b  llama-3.3-70b  qwen-qwq-32b      ║
║  ML:      XGBoost(ConflictPredictor) sentence-transformers fasttext                  ║
║  STATIC:  CSR-matrix constrained decoder (all Tier-1 schemas)                        ║
║  SKILLS:  30 skill files in .agent/skills/ (see Part X)                              ║
║                                                                                      ║
║  ┌────────────────────────────────────────────────────────────────────────────────┐ ║
║  │ LOOPHOLE HUNTER (cross-layer, always active, READ-ONLY)                       │ ║
║  │ 24 checks: LOGIC(8) SEC(6) CONSISTENCY(4) PERF(2) OVERSIGHT(4)               │ ║
║  └────────────────────────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 1.4 Hierarchy of Autonomy

```
Orchestrator  →  "WHAT needs to happen"     (decomposes, routes, budgets)
  Supervisor  →  "WHO should do it"          (schedules, prioritizes, gates)
    Agent     →  "HOW to coordinate it"      (manages workers, tracks state)
      SubAgent→  "HOW to pipeline steps"     (composes worker sequences)
        Worker→  "HOW to do one thing"       (executes, reports, retries)
```

## 1.5 Communication Patterns

### Vertical (Hierarchical — Primary)
```
Orchestrator ──dispatch──► Supervisor ──assign──► Agent ──run──► SubAgent ──exec──► Worker
Worker ───────result──────► SubAgent ──result──► Agent ──report─► Supervisor ──report─► Orchestrator
```

### Horizontal (Event Bus — Secondary)
```
FactCheckAgent ──quarantine_event──► EventBus ──notify──► SourceFeedbackSubAgent
HealthCheckAgent ──alert_event──────► EventBus ──notify──► SwarmMaster (DEGRADED_MODE)
AuditorAgent ──drift_event──────────► EventBus ──notify──► RoutingAdvisor
Worker.any ──cost_event─────────────► EventBus ──aggregate──► BudgetManager
LoopholeHunterAgent ──finding_event─► EventBus ──notify──► Admin (Telegram/Portal)
```

### No Lateral (LOCKED)
```
Supervisor-to-Supervisor: FORBIDDEN
Worker-to-Worker (different domain): FORBIDDEN
Only through EventBus or upward through hierarchy
```

## 1.6 Cost Is a First-Class Citizen

```
Worker.process()    → returns cost_inr in meta
SubAgent.run()      → aggregates worker costs
Agent.execute()     → aggregates subagent costs
Supervisor.dispatch()→ enforces budget cap (BudgetGate)
Orchestrator.route() → global INR budget waterfall
CostProjectionAgent → forward-looking monthly estimate
```

## 1.7 Failure Recovery Chain

```
Worker fails     → retry with backoff (max 3) → skip + log
SubAgent fails   → skip step + log + continue pipeline
Agent fails      → internal circuit breaker opens → fallback agent
Supervisor fails → DEGRADED_MODE → core-only agents remain
Orchestrator fails → cold-start guard → minimal pipeline
MoA fails        → 4-level fallback chain (GPT → Groq → Scoring → Manual)
Total failure    → DisasterRecoverySupervisor → restore from Google Drive backup
```

## 1.8 Hardware & Cost (Final)

```
PC RTX 5060 16GB     Mon-Thu 10am-6pm    Primary inference       ₹0
Groq API             24/7 free           Primary fallback        ₹0
GCP T4               INR 0 via credits   Burst GPU               ₹0
Claude API           Emergency only      Architecture review     ₹0.25/call
GitHub Actions       Free 2,000 min/mo   CI/CD pipeline          ₹0
Google Drive         15GB free           Backup target           ₹0

TOTAL MONTHLY PROJECTED:    ₹125 — ₹350
BUDGET CAP (LOCKED):        ₹500/month
```

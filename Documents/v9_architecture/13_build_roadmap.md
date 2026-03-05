# Chapter 13: Phase Build Order, Roadmap & Future-Proofing

## Phase Build Order v9.0 (Strict — Never Violate)

```
Phase 0 — SWARM FOUNDATION
  geosupply/orchestrator/moe_gate.py         MoE routing + STATIC integration
  geosupply/orchestrator/message_bus.py       Message contract + pub/sub
  geosupply/orchestrator/moa_orchestrator.py  3-proposer MoA pattern
  geosupply/infra/event_bus.py               NEW v9: async event bus

Phase 1 — CORE UTILS + BASE CLASSES
  geosupply/config.py                        HALLUCINATION_FLOOR=0.70, constants
  geosupply/schemas.py                       All Pydantic v2 models
  geosupply/infra/circuit_breaker.py         @breaker decorator
  geosupply/workers/base_worker.py           NEW v9: BaseWorker lifecycle
  geosupply/subagents/base_subagent.py       NEW v9: BaseSubAgent pipeline
  geosupply/agents/base_agent.py             NEW v9: BaseAgent capabilities
  geosupply/supervisors/base_supervisor.py   NEW v9: BaseSupervisor budget+queue

Phase 2 — INFRASTRUCTURE AGENTS
  geosupply/agents/infra/logging_agent.py
  geosupply/agents/infra/health_check_agent.py
  geosupply/agents/infra/fact_check_agent.py    0.70 floor, 7-step
  geosupply/agents/infra/security_agent.py
  geosupply/agents/infra/auditor_agent.py       Stratified sampling
  geosupply/agents/infra/source_feedback_agent.py
  geosupply/agents/infra/cyber_defense_agent.py  NEW v9

Phase 3 — INGESTION WORKERS
  geosupply/workers/ingestion/news_worker.py
  geosupply/workers/ingestion/india_api_worker.py
  geosupply/workers/ingestion/telegram_worker.py
  geosupply/workers/ingestion/ais_worker.py

Phase 4 — NLP WORKERS
  geosupply/workers/nlp/lang_worker.py
  geosupply/workers/nlp/translation_worker.py
  geosupply/workers/nlp/sentiment_worker.py       STATIC decoder
  geosupply/workers/nlp/ner_worker.py              STATIC decoder
  geosupply/workers/nlp/embed_worker.py

Phase 5 — INTELLIGENCE WORKERS
  geosupply/workers/intel/claim_worker.py          STATIC decoder
  geosupply/workers/intel/verifier_worker.py
  geosupply/workers/intel/source_cred_worker.py    STATIC decoder
  geosupply/workers/intel/author_worker.py
  geosupply/workers/intel/network_worker.py
  geosupply/workers/intel/cib_worker.py
  geosupply/workers/intel/propaganda_worker.py
  geosupply/workers/intel/cyber_threat_worker.py   NEW v9

Phase 6 — INDIA APIS
  geosupply/workers/india/ulip_connector.py
  geosupply/workers/india/imd_weather.py
  geosupply/workers/india/rbi_forex.py
  geosupply/workers/india/dgft_tracker.py
  geosupply/workers/india/ldb_connector.py
  geosupply/workers/india/india_intel_worker.py
  geosupply/workers/india/monsoon_worker.py

Phase 7 — ML WORKERS
  geosupply/workers/ml/conflict_worker.py
  geosupply/workers/ml/retrain_worker.py
  geosupply/workers/ml/drift_worker.py

Phase 8 — RAG (Fixed sequence) + SUBAGENTS
  geosupply/subagents/reason_plan_subagent.py
  geosupply/subagents/retrieve_subagent.py
  geosupply/subagents/rerank_subagent.py
  geosupply/subagents/context_build_subagent.py
  geosupply/subagents/brief_synth_subagent.py      MoA
  geosupply/subagents/source_feedback_subagent.py
  geosupply/subagents/semantic_drift_monitor.py
  geosupply/subagents/hallucination_check_subagent.py
  geosupply/workers/rag/rag_worker.py
  geosupply/workers/rag/graph_rag_worker.py
  geosupply/workers/rag/brief_worker.py

Phase 9 — SUPPLY CHAIN + KNOWLEDGE
  geosupply/workers/supply/stress_worker.py
  geosupply/workers/supply/supplier_worker.py
  geosupply/workers/supply/sanctions_worker.py
  geosupply/agents/knowledge_graph_agent.py         NEW v9
  geosupply/agents/performance_learner_agent.py     NEW v9

Phase 10 — SUPERVISORS + ORCHESTRATOR
  geosupply/supervisors/ingest_supervisor.py
  geosupply/supervisors/nlp_supervisor.py
  geosupply/supervisors/intel_supervisor.py
  geosupply/supervisors/ml_supervisor.py
  geosupply/supervisors/india_supervisor.py
  geosupply/supervisors/dashboard_supervisor.py
  geosupply/supervisors/infra_supervisor.py
  geosupply/supervisors/quality_supervisor.py
  geosupply/supervisors/dev_supervisor.py
  geosupply/supervisors/test_supervisor.py
  geosupply/orchestrator/swarm_master.py

Phase 11 — ADMIN + DASHBOARD
  geosupply/admin/cli.py                            NEW v9
  geosupply/admin/portal.py                         NEW v9
  geosupply/admin/autonomous_scheduler.py           NEW v9
  geosupply/admin/autonomous_decision_engine.py     NEW v9
  geosupply/infra/observability.py                  NEW v9
  geosupply/infra/self_healing.py                   NEW v9
  dashboard/pages/1_world_map.py
  dashboard/pages/2_supply_chain.py
  ... (9 dashboard pages + CI visualisation)
  dashboard/pages/10_admin.py                       NEW v9
  dashboard/pages/11_cyber_threats.py               NEW v9
```

---

## 12-Week Build Schedule (v9 — extended from v8's 10 weeks)

```
Week 1:  Phase 0-1 (Foundation + Base Classes + Event Bus)
Week 2:  Phase 2 (Infrastructure Agents + CyberDefenseAgent)
Week 3:  Phase 3 (Ingestion Workers)
Week 4:  Phase 4 (NLP Workers + STATIC decoder integration)
Week 5:  Phase 5 (Intelligence Workers + CyberThreatWorker)
Week 6:  Phase 6 (India APIs)
Week 7:  Phase 7 (ML Workers + retrain pipeline)
Week 8:  Phase 8 (RAG fixed + SubAgents)
Week 9:  Phase 9 (Supply Chain + KnowledgeGraph + PerformanceLearner)
Week 10: Phase 10 (Supervisors + SwarmMaster)
Week 11: Phase 11 (Admin CLI + Portal + Autonomous Engine)
Week 12: Integration testing + load testing + security audit + portfolio
```

---

## Future-Proofing: v10+ Roadmap

### Near-Term (v9.1 — Month 4-6)
```
- Autonomy Level 3 (self-adjusting routing + budgets)
- Multi-language dashboard (Hindi, Tamil, Bengali)
- Webhook integration for external alerting
- Mobile-optimized admin portal
- Voice-based CLI assistant
```

### Medium-Term (v10 — Month 6-12)
```
- Multi-agent negotiation (agents debate before final brief)
- Federated learning across pipeline runs
- Custom fine-tuned models for India-specific NER
- Real-time streaming pipeline (replace 6-hour batch)
- GraphRAG knowledge graph querying via natural language
```

### Long-Term (v11 — Year 2)
```
- Multi-tenant SaaS deployment (serve multiple customers)
- Agent marketplace (plug-in new workers dynamically)
- Autonomous model training + deployment (MLOps pipeline)
- Cross-organization intelligence sharing (federated)
- Quantum-resistant security upgrade
- Satellite imagery integration for port monitoring
```

---

## What Is LOCKED (Never Change — Inherited from v8)

```
DAG + strict Pydantic typing across all tiers
Three-tier LLM routing (3b / 14b / 20b)
No lateral Manager-to-Manager communication
Single-writer authority for Tier 0 over state persistence
Infrastructure agents off the critical DAG path
XGBoost + Platt scaling isolated from LLMs
HALLUCINATION_FLOOR = 0.70
All costs in INR — never USD
```

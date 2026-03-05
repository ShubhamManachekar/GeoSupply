# Chapter 11: Infrastructure Agents (7 Singletons — v9 updated)

## Singleton Inventory (v8: 6, v9: 7 — added CyberDefenseAgent)

| # | Agent | Always On | v8/v9 | Key Responsibility |
|---|-------|-----------|-------|-------------------|
| 1 | LoggingAgent | Yes | v8 | Every event, INR cost, Supabase |
| 2 | FactCheckAgent | Yes | v8 | 7-step verification, 0.70 floor |
| 3 | HealthCheckAgent | Yes | v8 | 28 APIs, INR thresholds, self-heal |
| 4 | SecurityAgent | Yes | v8 | Key management, OFAC, audit trail |
| 5 | AuditorAgent | Yes | v8+ | Stratified sampling, drift vector |
| 6 | SourceFeedbackAgent | Yes | v8 | Source penalties, credibility loop |
| 7 | **CyberDefenseAgent** | Yes | **v9 NEW** | Prompt injection, anomaly detect |

## Key Infrastructure Contracts

```
LoggingAgent — imported by EVERY module, no exceptions
    LoggingAgent.log(event_type, **kwargs) — universal logging
    Events: moe_gate, llm_call, module_process, api_call,
            agent_spawn, moa_trace, fact_check, source_penalty,
            cost_alert, cyber_threat (NEW), override_action (NEW)
    Storage: Supabase swarm_logs table
    Alerts: >INR 50/hr WARN, >INR 300/day ALERT, >INR 500/month CRITICAL

FactCheckAgent — 7-step pipeline (see Chapter 5 for detail)
    HALLUCINATION_FLOOR = 0.70 (LOCKED, from config.py)
    Rejection: >20% UNVERIFIED claims → reject → return to worker
    After rejection: auto-triggers SourceFeedbackSubAgent
    MoA mode: verify_batch() checks all 3 proposers independently

HealthCheckAgent — polling intervals
    PC Ollama:      every 2 minutes
    Groq API:       every 15 minutes
    Supabase:       every 15 minutes
    28 external APIs: every 15 minutes
    ChromaDB queue: every 5 minutes
    GCP credit:     every 24 hours
    Self-healing:   restart processes, clear circuits, flush queues

SecurityAgent — key management
    SecurityAgent.get_key('keyname') — ONLY way to access keys
    Monthly rotation: Groq, Supabase, Qdrant
    OFAC sanctions list: updated weekly
    All key access logged to audit trail

AuditorAgent — stratified adaptive sampling (v8 upgrade)
    100%: Workers with confidence <0.60 last run
    100%: FactCheckWorker, BriefGeneratorWorker (always)
    30%:  All other Workers
    10%:  Workers with 10+ consecutive PASS audits
    Weekly: SemanticDriftMonitor + RoutingAdvisorRecord

CyberDefenseAgent (NEW v9)
    Prompt injection detection on all ingested text
    API usage anomaly monitoring
    Message contract violation alerts
    Dependency vulnerability scanning coordination
```

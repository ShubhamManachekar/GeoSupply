# Part X: Registry & Roadmap — APIs, Skills, Schemas, Census, Build Plan
## FA v1 | Gap Mitigations: G9 schema added

## 10.1 Complete API Registry (42+)

### Existing APIs (28)

| # | API | Category | Cost (INR) |
|---|-----|----------|-----------|
| 1 | Groq API | LLM | ₹0 (14,400 req/day) |
| 2 | Ollama (local) | LLM | ₹0 |
| 3 | Claude API | LLM (emergency) | ₹0.25/call |
| 4 | ChromaDB | Vector DB | ₹0 (local) |
| 5 | Supabase | Database | ₹0 (free tier) |
| 6 | NewsAPI | Ingestion | ₹0 |
| 7 | GDELT | Ingestion | ₹0 |
| 8 | ACLED | Ingestion | ₹0 |
| 9 | Telegram API | Ingestion | ₹0 |
| 10 | Google Maps Platform | Geospatial | ₹0 (credits) |
| 11-15 | ULIP (5 core endpoints) | India logistics | ₹0 |
| 16 | DGFT | India trade | ₹0 |
| 17 | IMD | India weather | ₹0 |
| 18 | RBI | India forex | ₹0 |
| 19 | LDB | India container | ₹0 |
| 20-28 | Other India APIs | India specific | ₹0 |

### v10 New APIs (+14)

| # | API | Category | Cost | Priority | Worker |
|---|-----|----------|------|----------|--------|
| 29 | Twitter/X API v2 | Marketing | ₹0 | P0 | TwitterAPIWorker |
| 30 | SendGrid/Resend | Newsletter | ₹0 | P0 | NewsletterWorker |
| 31 | Google Drive API | Backup | ₹0 | P0 | BackupWorker |
| 32 | CISA Alerts | Cyber intel | ₹0 | P1 | CyberThreatWorker |
| 33 | CERT-In RSS | Cyber (India) | ₹0 | P1 | CyberThreatWorker |
| 34 | NVD CVE API | Vulnerability | ₹0 | P1 | DepUpdateAgent |
| 35 | ONDC API | Supply chain | ₹0 | P1 | IndiaAPIWorker |
| 36 | Shodan | Cyber intel | ₹0 | P2 | CyberThreatWorker |
| 37 | GreyNoise | Threat enrich | ₹0 | P2 | CyberThreatWorker |
| 38 | AlienVault OTX | Threat exchange | ₹0 | P2 | CyberThreatWorker |
| 39 | GSTN API | India trade | ₹0 | P2 | IndiaAPIWorker |
| 40 | UMANG API | India govt | ₹0 | P3 | IndiaAPIWorker |
| 41 | Reddit API | OSINT | ₹0 | P3 | TelegramWorker |
| 42 | Wayback Machine | Historical | ₹0 | P3 | NewsWorker |

**Total monthly API cost: ₹125-350 (budget cap: ₹500)**

---

## 10.2 Complete Skills Registry (30)

| # | Skill | Used By | Origin |
|---|-------|---------|--------|
| 1 | python-conventions | All modules | v8 |
| 2 | india-apis | India workers | v8 |
| 3 | llm-routing | MoE gate | v8 |
| 4 | circuit-breaker | API workers | v8 |
| 5 | rag-patterns | RAG pipeline | v8 |
| 6 | testing-standards | Test agents | v8 |
| 7 | multilingual-nlp | NLP workers | v8 |
| 8 | fact-checking | FactCheckAgent | v8 |
| 9 | supply-chain | Supply workers | v8 |
| 10 | security | SecurityAgent | v8 |
| 11 | moe-gateway | SwarmMaster | v8 |
| 12 | logging-integration | LoggingAgent | v8 |
| 13 | infra-agents | Infrastructure | v8 |
| 14 | dashboard-patterns | Streamlit | v8 |
| 15 | knowledge-graph | KnowledgeGraphAgent | v9 |
| 16 | admin-cli | CLI agents | v9 |
| 17 | autonomous-ops | Scheduler | v9 |
| 18 | marketing-content | ContentGenerator | v9 |
| 19 | cyber-intelligence | CyberThreatWorker | v9 |
| 20 | deployment | DeployAgent | v9 |
| 21 | api-discovery | APIScanAgent | v9 |
| 22 | revenue-tracking | RevenueTracker | v9 |
| 23 | prediction-accuracy | PredictionAgent | v9 |
| 24 | event-bus | Event publishers | v9 |
| 25 | **loophole-hunting** | LoopholeHunterAgent | **v10** |
| 26 | **penetration-testing** | PenTestAgent | **v10** |
| 27 | **backup-recovery** | BackupAgent | **v10** |
| 28 | **input-sanitisation** | InputGuardAgent | **v10** |
| 29 | **channel-verification** | ChannelVerificationAgent | **v10** |
| 30 | **cost-projection** | CostProjectionAgent | **v10** |

---

## 10.3 Core Pydantic Schemas (23 — FA v1)

| # | Schema | Fields | Used By |
|---|--------|--------|---------|
| 1 | AgentMessage | trace_id, source, target, payload, cost_inr, timestamp | ALL |
| 2 | TaskPacket | task_id, task_type, priority, budget_inr, timeout_s | SwarmMaster |
| 3 | GeoRiskScore | country, score, ci_low, ci_high, data_density, timestamp | IntelWorkers |
| 4 | CyberThreatScore | threat_type, severity, geographic_scope, mitre_id, india_impact | CyberThreatWorker |
| 5 | SentimentOutput | polarity, subjectivity, confidence | SentimentWorker |
| 6 | NEROutput | entities[], entity_type, span_start, span_end | NERWorker |
| 7 | ClaimOutput | claim_text, claim_type, evidence_needed | ClaimWorker |
| 8 | SourceCredOutput | source_id, credibility_score, history | SourceCredWorker |
| 9 | SupplierScore | supplier_id, risk_score, dependencies[] | SupplierWorker |
| 10 | SanctionsOutput | entity_name, sanctioned_by[], sanction_type | SanctionsWorker |
| 11 | SourceFeedbackScore | source_id, old_score, new_score, penalty, reason | SourceFeedback |
| 12 | AuditSample | sample_id, pipeline_output, audit_result, sampling_rate | AuditorAgent |
| 13 | OverrideRecord | admin_id, action, target, reason, timestamp, totp_verified | Admin CLI |
| 14 | LoopholeFinding | check_id, name, severity, layer, details, recommendation | LoopholeHunter |
| 15 | LoopholeReport | timestamp, total_checks, passed, failed, findings[] | LoopholeHunter |
| 16 | TweetOutput | text, content_type, confidence, hashtags[] | ContentGenerator |
| 17 | PredictionRecord | prediction, confidence, target_date, actual_outcome | PredictionAgent |
| 18 | BackupRecord | target, timestamp, size_mb, encrypted, gcs_path | BackupWorker |
| 19 | ChannelFingerprint | channel_id, dimensions{}, baseline_hash, drift_score | ChannelFingerprint |
| 20 | KnowledgeUpdateRequest | entity_source, entity_target, relation_type, confidence | KnowledgeGraph |
| 21 | CostProjection | daily_inr, weekly_inr, monthly_inr, alert_level | CostProjection |
| 22 | Event | topic, source, payload, timestamp, signature | EventBus |
| **23** | **WorkerError** | **error_type, message, worker_name, retry_count, cost_inr, trace_id, timestamp** | **ALL workers (FA v1 G9)** |

---

## 10.4 Full Component Census — Summary

| Category | v8 | v9 | v10 Final | New |
|----------|----|----|-----------|-----|
| Layers | 5 | 7 | 7 + LH | +cross-layer |
| Workers | 32 | 32 | **40** | +8 |
| SubAgents | 0 | 8 | **13** | +5 |
| Agents | 15 | 26 | **38** | +12 |
| Supervisors | 10 | 12 | **14** | +2 |
| Infra Singletons | 6 | 7 | **9** | +2 |
| APIs | 28 | 28 | **42+** | +14 |
| Skills | 14 | 24 | **30** | +6 |
| Pydantic Schemas | 8 | 14 | **23** | +9 |
| Test Scenarios | 8 | 9 | **18** | +9 |
| LoopholeHunter Checks | 0 | 0 | **24** | +24 |
| Penetration Tests | 0 | 0 | **8** | +8 |
| **Total** | **~71** | **~107** | **~137** | **+30** |

---

## 10.5 Build Roadmap — 13 Phases, 14 Weeks

| Phase | Week | What to Build | Gate |
|-------|------|--------------|------|
| 0 | W1 | `config.py`, `schemas.py`, project skeleton | Tests pass |
| 1 | W1-2 | `base_worker.py`, `event_bus.py`, `logging_agent.py` | Base classes work |
| 2 | W2-3 | 4 Ingestion workers + InputSanitiserWorker | Ingest pipeline runs |
| 3 | W3-4 | 5 NLP workers + STATIC decoder | STATIC outputs valid |
| 4 | W4-5 | 8 Intel workers + CyberThreatWorker | Claims extracted |
| 5 | W5-6 | 3 ML workers + ConflictPredictor | XGBoost predicts |
| 6 | W6-7 | RAG pipeline (5 subagents) + MoAFallback | Briefs generated |
| 7 | W7-8 | KnowledgeGraphAgent + write-buffer queue | KG builds |
| 8 | W8-9 | 14 Supervisors + SwarmMaster v10 | Full pipeline runs |
| 9 | W9-10 | Admin CLI + Portal (12 pages) | Override works |
| 10 | W10-11 | Marketing agents + Twitter + Newsletter | Tweets publish |
| 11 | W11-12 | LoopholeHunter + PenTest + Security hardening | 24 checks pass |
| 12 | W12-13 | Tech team CI/CD + 6-stage deploy pipeline | Canary deploys |
| 13 | W13-14 | DR setup + Backup + WatchdogAgent + Cost projection | Full DR tested |

---

```
FA v1 (CURRENT):  137 components, loophole-hardened, 10 implementation gaps mitigated
v10 (BASE):       136 components, loophole-hardened
v11 (Q4 2026):    Multi-language briefs, mobile app, satellite imagery
v12 (Q1 2027):    Real-time streaming pipeline, federated learning
v13 (Q2 2027):    Multi-modal intelligence (image + text + video)
```

## FINAL CROSS-CHECK ✅ (FA v1)
```
✓ 42+ APIs listed with costs in INR
✓ 30 skills listed with agents that use them
✓ 23 Pydantic schemas listed with consumers (22 v10 + 1 FA v1)
✓ Full census matches all parts (40W + 13SA + 38A + 14S)
✓ Build roadmap covers all 137 components
✓ Every feature from v9 (21 chapters) preserved
✓ Every fix from v10 (11 chapters) integrated
✓ All 10 implementation gaps (G1-G10) mitigated in FA v1
✓ No feature lost in consolidation
✓ Cross-references verified across all 10 parts
```

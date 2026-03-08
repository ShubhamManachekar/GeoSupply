# Part X: Registry & Roadmap — APIs, Skills, Schemas, Census, Build Plan
## FA v2 | Gap Mitigations: G9 schema added | World Monitor Integration

## 10.1 Complete API Registry (59+)

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

### FA v2 New APIs (+17) — World Monitor Integration

| # | API | Category | Cost | Priority | Worker |
|---|-----|----------|------|----------|--------|
| 43 | USGS Earthquake | Disaster | ₹0 | P1 | DisasterWorker |
| 44 | NASA EONET | Disaster | ₹0 | P1 | DisasterWorker |
| 45 | GDACS | Disaster | ₹0 | P1 | DisasterWorker |
| 46 | OpenSky Network | Aviation/Military | ₹0 (free reg) | P1 | AviationWorker |
| 47 | Wingbits | Aircraft enrichment | ₹0 (free reg) | P2 | AviationWorker |
| 48 | AISStream | Maritime (WS) | ₹0 (relay) | P1 | AISWorker |
| 49 | Finnhub | Stock quotes | ₹0 (free reg) | P2 | MarketWorker |
| 50 | Yahoo Finance | Indices/commodities | ₹0 | P2 | MarketWorker |
| 51 | CoinGecko | Crypto prices | ₹0 | P3 | MarketWorker |
| 52 | FRED | Economic indicators | ₹0 | P2 | EconomicWorker |
| 53 | EIA | Oil analytics | ₹0 (free reg) | P2 | EnergyWorker |
| 54 | Cloudflare Radar | Internet outages | ₹0 (free acct) | P2 | CyberThreatWorker |
| 55 | Polymarket | Prediction markets | ₹0 | P3 | PredictionMarketWorker |
| 56 | RSS2JSON | RSS feed parsing | ₹0 | P1 | NewsWorker |
| 57 | NWS | Weather alerts (US) | ₹0 | P3 | DisasterWorker |
| 58 | FAA NASSTATUS | Airport delays | ₹0 | P3 | Optional |
| 59 | USASpending.gov | Govt contracts | ₹0 | P3 | Optional |

**Total monthly API cost: ₹140-375 (budget cap: ₹500) — ALL NEW APIs ARE FREE TIER**

---

## 10.2 Complete Skills Registry (33)

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
| 31 | **dynamic-phase-audit** | Admin CLI (audit.py) | **v10** |
| 32 | **disaster-tracking** | DisasterWorker | **FA v2** |
| 33 | **aviation-military-intel** | AviationWorker | **FA v2** |

---

## 10.3 Core Pydantic Schemas (28 — FA v2)

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
| 24 | GeoEventRecord | event_type, description, source_clipping, severity, locations, date_occurred | EventExtractorWorker |
| 25 | GeoEventTimeline | timeline_name, nodes[], identified_trend | TimelineGeneratorAgent |
| **26** | **DisasterEvent** | **event_type, magnitude, location, source_api, alert_level, affected_region** | **DisasterWorker (FA v2)** |
| **27** | **AviationTrack** | **aircraft_id, callsign, lat, lon, altitude, speed, is_military, operator, classification_confidence** | **AviationWorker (FA v2)** |
| **28** | **MarketSignal** | **symbol, price, change_pct, volume, source_api, signal_type, timestamp** | **MarketWorker (FA v2)** |

---

## 10.4 Full Component Census — Summary

| Category | v8 | v9 | v10 | FA v1 | FA v2 |
|----------|----|----|-----|-------|-------|
| Layers | 5 | 7 | 7 + LH | 7 + LH | 7 + LH |
| Workers | 32 | 32 | 41 | 41 | **45** (+4) |
| SubAgents | 0 | 8 | 13 | 13 | **15** (+2) |
| Agents | 15 | 26 | 39 | 39 | 39 |
| Supervisors | 10 | 12 | 14 | 14 | 14 |
| Infra Singletons | 6 | 7 | 9 | 9 | 9 |
| APIs | 28 | 28 | 42+ | 42+ | **59+** (+17) |
| Skills | 14 | 24 | 30 | 31 | **33** (+2) |
| Pydantic Schemas | 8 | 14 | 22 | 25 | **28** (+3) |
| Test Scenarios | 8 | 9 | 18 | 18 | 18 |
| LH Checks | 0 | 0 | 24 | 24 | 24 |
| Pen Tests | 0 | 0 | 8 | 8 | 8 |
| **Total** | **~71** | **~107** | **~136** | **~141** | **~147** |

---

## 10.5 Build Roadmap — 16 Phases

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
| 14 | W14 | Dynamic Phase-End Test Suite (CLI) | Audit passes |
| **15** | **W15-16** | **FA v2: DisasterWorker + AviationWorker + EnergyWorker + MarketWorker + ConvergenceSubAgent + CascadeSubAgent** | **All 17 new APIs integrated** |

---

```
FA v2 (CURRENT):  ~147 components, loophole-hardened, World Monitor integrated
FA v1 (PREV):     ~141 components, loophole-hardened, 10 implementation gaps mitigated
v11 (Q4 2026):    Multi-language briefs, mobile app, satellite imagery
v12 (Q1 2027):    Real-time streaming pipeline, federated learning
v13 (Q2 2027):    Multi-modal intelligence (image + text + video)
```

## FINAL CROSS-CHECK ✅ (FA v2)
```
✓ 59+ APIs listed with costs in INR (all new APIs are ₹0 free tier)
✓ 33 skills listed with agents that use them
✓ 28 Pydantic schemas listed with consumers (25 FA v1 + 3 FA v2)
✓ Full census matches all parts (45W + 15SA + 39A + 14S)
✓ Build roadmap covers all ~147 components across 16 phases
✓ Every feature from v9 (21 chapters) preserved
✓ Every fix from v10 (11 chapters) integrated
✓ All 10 implementation gaps (G1-G10) mitigated
✓ World Monitor reference features integrated (FA v2)
✓ No feature lost in consolidation
✓ Cross-references verified across all 10 parts
```

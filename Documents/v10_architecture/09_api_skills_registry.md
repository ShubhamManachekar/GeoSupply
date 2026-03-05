# Chapter 9: API Registry (42+) & Skills Registry (30)

## Complete API Registry — v10

### Existing APIs (28 from v8/v9)

| # | API | Category | Cost (INR) | Rate Limit |
|---|-----|----------|-----------|------------|
| 1 | Groq API | LLM | ₹0 | 14,400 req/day |
| 2 | Ollama (Local) | LLM | ₹0 (electricity) | Unlimited |
| 3 | Claude API | LLM (emergency) | ₹0.25/call | Pay-per-use |
| 4 | ChromaDB | Vector DB | ₹0 (local) | Unlimited |
| 5 | Supabase | Database | ₹0 (free tier) | 500MB |
| 6 | NewsAPI | Ingestion | ₹0 (free) | 100 req/day |
| 7 | GDELT | Ingestion | ₹0 | Unlimited |
| 8 | ACLED | Ingestion | ₹0 (research) | rate limited |
| 9 | Telegram API | Ingestion | ₹0 | 30 req/sec |
| 10 | Google Maps | Geospatial | ₹0 (credits) | 28,000/month |
| 11-15 | ULIP (5 core) | India logistics | ₹0 | per-ministry |
| 16 | DGFT | India trade | ₹0 | rate limited |
| 17 | IMD | India weather | ₹0 | rate limited |
| 18 | RBI | India forex | ₹0 | daily |
| 19 | LDB | India container | ₹0 | rate limited |
| 20-28 | Other India APIs | India specific | ₹0 | varies |

### New APIs in v10 (+14)

| # | API | Category | Cost (INR) | Priority | Status |
|---|-----|----------|-----------|----------|--------|
| 29 | **Twitter/X API v2** | Marketing | ₹0 (free) | P0 | 🔧 Adding |
| 30 | **SendGrid** | Newsletter | ₹0 (100/day) | P0 | 🔧 Adding |
| 31 | **CISA Alerts API** | Cyber threat | ₹0 | P1 | 🔧 Adding |
| 32 | **CERT-In RSS** | Cyber (India) | ₹0 | P1 | 🔧 Adding |
| 33 | **NVD CVE API** | Vulnerability | ₹0 | P1 | 🔧 Adding |
| 34 | **ONDC API** | Supply chain (India) | ₹0 | P1 | 📋 Planned |
| 35 | **GSTN API** | Trade (India) | ₹0 | P2 | 📋 Needs auth |
| 36 | **Shodan API** | Cyber intel | ₹0 (free tier) | P2 | 🔧 Adding |
| 37 | **GreyNoise API** | Threat enrich | ₹0 (free tier) | P2 | 🔧 Adding |
| 38 | **AlienVault OTX** | Threat exchange | ₹0 | P2 | 🔧 Adding |
| 39 | **Google Drive API** | Backup | ₹0 (15GB free) | P0 | 🔧 Adding |
| 40 | **UMANG API** | India govt | ₹0 | P3 | 📋 Planned |
| 41 | **Reddit API** | OSINT | ₹0 | P3 | 📋 Planned |
| 42 | **Wayback Machine** | Historical | ₹0 | P3 | 📋 Planned |

### Monthly API Cost Summary (v10)

```
LOCAL (₹0):          Ollama, ChromaDB, SQLite
FREE TIER (₹0):      Groq, Supabase, NewsAPI, GDELT, Twitter/X, SendGrid,
                     CISA, CERT-In, NVD, Shodan, GreyNoise, AlienVault,
                     Google Drive, all India APIs
EMERGENCY (~₹25/mo): Claude API (estimated 100 emergency calls × ₹0.25)
GCP (~₹100/mo):      T4 GPU fallback (if used)

TOTAL PROJECTED:     ₹125 - ₹350/month
BUDGET CAP:          ₹500/month (LOCKED)
```

---

## Complete Skills Registry — v10 (30 Skills)

### Existing Skills (14 from v8)

| # | Skill | Used By |
|---|-------|---------|
| 1 | python-conventions | All modules |
| 2 | india-apis | India workers, ULIP connectors |
| 3 | llm-routing | MoE gate, moe_gate.py |
| 4 | circuit-breaker | All API workers |
| 5 | rag-patterns | RAG pipeline, SubAgents |
| 6 | testing-standards | Test agents, DevSupervisor |
| 7 | multilingual-nlp | NLP workers |
| 8 | fact-checking | FactCheckAgent, VerifierWorker |
| 9 | supply-chain | Stress/Supplier/Sanctions workers |
| 10 | security | SecurityAgent, CyberDefenseAgent |
| 11 | moe-gateway | SwarmMaster, MoE routing |
| 12 | logging-integration | LoggingAgent, all modules |
| 13 | infra-agents | All infrastructure singletons |
| 14 | dashboard-patterns | Streamlit workers |

### v9 Skills (10 added)

| # | Skill | Used By |
|---|-------|---------|
| 15 | knowledge-graph | KnowledgeGraphAgent |
| 16 | admin-cli | CLI agents, OverrideEngine |
| 17 | autonomous-ops | AutonomousScheduler |
| 18 | marketing-content | ContentGenerator, Twitter |
| 19 | cyber-intelligence | CyberThreatWorker, Defense |
| 20 | deployment | DeployAgent, StageAgent |
| 21 | api-discovery | APIScanAgent |
| 22 | revenue-tracking | RevenueTracker |
| 23 | prediction-accuracy | PredictionAgent |
| 24 | event-bus | All event publishers/subscribers |

### v10 Skills (6 NEW)

| # | Skill | Used By | Provides |
|---|-------|---------|----------|
| 25 | **loophole-hunting** | LoopholeHunterAgent | 24-check patterns, audit methodology |
| 26 | **penetration-testing** | PenTestAgent | 8-test suite, safe attack patterns |
| 27 | **backup-recovery** | BackupAgent, BackupWorker | Encryption, DR procedures, verification |
| 28 | **input-sanitisation** | InputGuardAgent, Sanitiser | Injection patterns, truncation, normalisation |
| 29 | **channel-verification** | ChannelVerificationAgent | Fingerprinting, KL divergence, drift detection |
| 30 | **cost-projection** | CostProjectionAgent | Trend analysis, budget forecasting, optimisation |

# Chapter 21: v10 Architecture Audit — Loopholes, Logic Gaps, APIs & Skills

## Design Philosophy

> **Before building v10, tear v9 apart. Find every loophole, question every assumption, and plug every gap.**

This chapter is a **systematic audit** of the entire v9 architecture, identifying logic gaps, security loopholes, missing APIs, oversight blind spots, and skill registry gaps.

---

## PART A: Logic Gaps Found in v9

### GAP 1: Knowledge Graph Consistency Under Concurrent Writes

```
PROBLEM:
    KnowledgeGraphAgent builds graph from pipeline outputs.
    Multiple workers could finish simultaneously and try to
    update the graph concurrently.
    NetworkX is NOT thread-safe.

    Scenario: NewsWorker extracts "India-Australia trade deal"
              TelegramWorker extracts "Australia sanctions India"
              Both try to update India↔Australia edge simultaneously.
              Race condition → inconsistent graph state.

FIX FOR v10:
    Implement write-buffer queue pattern (like ChromaDB).
    KnowledgeGraphAgent owns queue — single-writer authority.
    Workers enqueue KnowledgeUpdateRequest objects.
    Graph updated in ordered batches by KnowledgeGraphAgent.
```

### GAP 2: Marketing Content Hallucination Risk

```
PROBLEM:
    ContentGeneratorAgent generates tweets from predictions.
    FactCheckAgent verifies claims — but tweets are SUMMARIZATIONS,
    not direct claims. Summarization can introduce distortion.

    Scenario: GeoRiskScore says "India-Pakistan tension: 0.67"
              ContentGenerator tweets "Rising India-Pakistan tensions"
              0.67 is BELOW 0.70 threshold — actually LOW tension.
              Tweet implies HIGH tension. Factually misleading.

FIX FOR v10:
    Add SummarizationVerifierSubAgent between ContentGenerator and FactCheck.
    Verifies that summary/tweet PRESERVES the semantic meaning
    of the underlying data. Not just fact-checking the claim,
    but verifying the summarization didn't flip the meaning.
```

### GAP 3: Source Feedback Loop Can Be Gamed

```
PROBLEM:
    SourceFeedbackSubAgent penalises sources by -0.05 per quarantine.
    Recovery is +0.02/week. Floor is 0.10.
    
    Attack: Adversary creates 20 sources that mix 90% real + 10% fake.
    FactCheck catches the 10% fake → source penalised.
    But source recovers in 2.5 weeks.
    Adversary cycles through 20 sources → persistent disinformation.

FIX FOR v10:
    Add penalty escalation: 
        1st quarantine: -0.05
        2nd quarantine (within 30 days): -0.10
        3rd quarantine (within 30 days): -0.20
        4th: source permanently flagged, requires admin override to re-enable.
    Add source clustering: if multiple sources share IP/domain/author,
    penalty applies to entire cluster.
```

### GAP 4: No Circuit Breaker on Internal Agents

```
PROBLEM:
    @breaker decorator on external APIs only.
    Internal agents (FactCheckAgent, AuditorAgent) have no circuit breaker.
    
    Scenario: FactCheckAgent's LLM backend (GPT-OSS:20b) crashes.
    Every worker calling FactCheckAgent blocks waiting.
    No timeout → cascading pipeline freeze.

FIX FOR v10:
    Add internal circuit breaker for all Tier 3+ agent calls.
    FACT_CHECK timeout: 30 seconds per claim batch.
    If FactCheck circuit opens → quarantine ALL claims (safe default).
    Log IncidentRecord with "fact_check_circuit_open" event.
```

### GAP 5: MoA Aggregator Is a Single Point of Failure

```
PROBLEM:
    BriefSynthSubAgent uses 3 proposers + 1 aggregator.
    If aggregator fails, all 3 proposals are wasted.
    The aggregator uses same model (GPT-OSS:20b) as proposers.
    GPU OOM during aggregation = lost work.

FIX FOR v10:
    Add fallback aggregation strategy:
        Primary: GPT-OSS:20b full MoA aggregation
        Fallback 1: Groq llama-3.3-70b aggregation
        Fallback 2: Simple scoring — pick highest-confidence proposal
        Fallback 3: Return all 3 proposals to admin for manual selection
    NEVER discard proposer outputs on aggregation failure.
```

### GAP 6: Admin Override Audit Is Write-Only

```
PROBLEM:
    OverrideRecord logs every admin action. But there's no
    mechanism to REVIEW past overrides for patterns.

    Scenario: Admin manually approves 15 briefs in one week.
    Each individual approval is logged.
    But nobody checks if admin is systematically bypassing FactCheck.

FIX FOR v10:
    Add OverrideAuditAgent that runs weekly:
        - Count overrides per admin per week
        - Flag: >5 overrides/week → send ALERT
        - Flag: override patterns (same source always approved)
        - Generate: monthly override report for review
```

---

## PART B: Security Loopholes

### LOOPHOLE 1: Telegram Channel Poisoning

```
PROBLEM:
    TelegramWorker ingests from 27+ OSINT Telegram channels.
    Telegram channels can be compromised/taken over.
    No verification that channel ownership hasn't changed.

RISK: Attacker takes over OSINT channel → feeds disinformation
      GeoSupply treats it as trusted source → polluted intelligence.

FIX FOR v10:
    Channel fingerprinting:
        - Track posting frequency, language patterns, admin changes
        - SemanticDriftMonitor extended to monitor channel drift
        - Alert if channel suddenly changes posting pattern
        - Admin must re-verify channel after ownership change alert
```

### LOOPHOLE 2: STATIC Decoder Bypass via Prompt Length

```
PROBLEM:
    STATIC decoder constrains output to valid schema tokens.
    But if input prompt is exceptionally long, model may
    truncate context → schema constraints may not apply
    to continuation tokens beyond context window.

RISK: Adversarial long-content articles could push schema
      constraints out of context window → unconstrained output.

FIX FOR v10:
    Hard token limit on all Tier-1 inputs: max 2048 tokens.
    Truncate + summarise before passing to STATIC decoder.
    Add post-generation validation (already exists) as safety net.
    Monitor: flag any Tier-1 input exceeding 1500 tokens.
```

### LOOPHOLE 3: No Rate Limiting on Admin CLI

```
PROBLEM:
    Admin CLI has no rate limiting. Password/token only.
    Brute force possible on local network.

FIX FOR v10:
    - 5 failed attempts → 30 min lockout
    - IP-based rate limiting (even localhost)
    - TOTP (time-based one-time password) for sensitive commands
    - All CLI sessions logged with source IP
```

---

## PART C: Missing APIs & Data Sources

### APIs to Add in v10

| Priority | API | Purpose | Cost (INR) | Integration Effort |
|----------|-----|---------|-----------|-------------------|
| P0 | Twitter/X API v2 | Marketing agent publishing | Free tier | LOW |
| P0 | SendGrid/Resend | Newsletter delivery | Free tier | LOW |
| P1 | CISA Alerts API | Cyber threat intelligence | Free | LOW |
| P1 | CERT-In RSS | India cyber alerts | Free | LOW |
| P1 | CVE API (NVD) | Vulnerability tracking | Free | LOW |
| P1 | ONDC API | India e-commerce supply chain | Free | MEDIUM |
| P2 | IndiaStack/GSTN | GST trade flow data | Free | HIGH (auth) |
| P2 | Shodan API | Internet-exposed supply chain systems | Free tier | LOW |
| P2 | GreyNoise API | Threat intelligence enrichment | Free tier | LOW |
| P2 | AlienVault OTX | Open threat exchange | Free | LOW |
| P3 | Satellite imagery | Port activity monitoring | Paid/research | HIGH |
| P3 | OSINT Framework | Consolidated OSINT tools | Free | MEDIUM |
| P3 | Wayback Machine | Historical web data | Free | LOW |
| P3 | Reddit API | OSINT from geopolitical subreddits | Free | LOW |

### India APIs Still Missing (Beyond ULIP's 129)

| API | Ministry | Data | Status |
|-----|----------|------|--------|
| GSTN API | Finance | GST trade flows | Needs registration |
| NIC SMS Gateway | IT | Government notification feed | Restricted |
| DigiLocker API | IT | Document verification | Needs auth |
| UMANG API | IT | Unified govt services | Free |
| MyGov API | IT | Citizen engagement data | Free |
| IRCTC API | Railways | Rail freight movement | Restricted |
| FCI data portal | Food | Food supply chain | Open data |
| NHIDCL API | Highways | Border road status (LAC/LOC) | Restricted |

---

## PART D: Missing Skills (v9 → v10)

### Current: 14 Skills from v8

```
python-conventions, india-apis, llm-routing, circuit-breaker,
rag-patterns, testing-standards, multilingual-nlp, fact-checking,
supply-chain, security, moe-gateway, logging-integration,
infra-agents, dashboard-patterns
```

### New Skills Needed for v10

| # | Skill Name | File | Loaded By | Provides |
|---|-----------|------|-----------|----------|
| 15 | **knowledge-graph** | SKILL.md | KnowledgeGraphAgent, PerformanceLearner | NetworkX patterns, entity extraction, graph merge |
| 16 | **admin-cli** | SKILL.md | CLI agents, OverrideEngine | Click CLI patterns, Rich output, override safety |
| 17 | **autonomous-ops** | SKILL.md | AutonomousScheduler, DecisionEngine | Autonomy levels, decision rules, self-adjust |
| 18 | **marketing-content** | SKILL.md | ContentGenerator, TwitterPublisher | Tweet templates, approval flow, engagement |
| 19 | **cyber-intelligence** | SKILL.md | CyberThreatWorker, CyberDefenseAgent | MITRE ATT&CK mapping, threat scoring |
| 20 | **deployment** | SKILL.md | DeployAgent, StageAgent | Git strategy, canary deploy, rollback |
| 21 | **api-discovery** | SKILL.md | APIScanAgent | API testing patterns, schema gen, mock creation |
| 22 | **revenue-tracking** | SKILL.md | RevenueTracker, AnalyticsAgent | INR MRR tracking, growth metrics |
| 23 | **prediction-accuracy** | SKILL.md | PredictionAgent | Calibration, accuracy scoring, Brier score |
| 24 | **event-bus** | SKILL.md | All agents publishing/subscribing | Pub/sub patterns, dead letter, replay |

---

## PART E: Oversight Blind Spots

### BLIND SPOT 1: No Monitoring of Monitoring

```
PROBLEM: HealthCheckAgent monitors everything. But who monitors HealthCheckAgent?
FIX: Add watchdog timer. If HealthCheckAgent hasn't logged in 5 minutes,
     SelfHealingEngine triggers restart. Simple, effective.
```

### BLIND SPOT 2: Knowledge Graph Has No Backup

```
PROBLEM: KnowledgeGraph in NetworkX memory. If process crashes,
         accumulated knowledge lost. SQLite backup exists but
         no defined RPO (Recovery Point Objective).
FIX: Snapshot to SQLite after every pipeline run (every 6 hours).
     RPO = 6 hours max. Keep last 10 snapshots. Auto-restore on crash.
```

### BLIND SPOT 3: Marketing Agent Has No Kill Switch

```
PROBLEM: Tweet auto-publishing can go wrong. No fast way to stop
         all publishing and delete recent tweets.
FIX: Add to admin CLI:
     geosupply marketing halt    → stop all publishing
     geosupply marketing delete-last N  → delete last N tweets
     geosupply marketing purge   → delete last 24hr of tweets
```

### BLIND SPOT 4: No Disaster Recovery Plan

```
PROBLEM: Architecture handles graceful degradation but not
         total system failure (PC dies, all data lost).
FIX: Document DR plan:
     - GitHub has all code (offsite backup)
     - Supabase has all logs (cloud backup)
     - ChromaDB: daily backup to Google Drive (automated)
     - SQLite: daily backup to Google Drive (automated)
     - KnowledgeGraph: snapshot to Google Drive (every 6hr)
     - RTO (Recovery Time Objective): 4 hours
     - RPO (Recovery Point Objective): 6 hours
```

### BLIND SPOT 5: No Cost Projection

```
PROBLEM: Budget tracking is reactive (alert when exceeded).
         No forward-looking cost projection.
FIX: Add CostProjectionAgent:
     - Track cost rate (INR/hr) over last 7 days
     - Project monthly total from trend
     - Alert if projected monthly > ₹400 (80% of ₹500 cap)
     - Suggest cost reduction (downgrade tasks to lower tier)
```

---

## v10 Priority Queue

| Priority | Fix | Effort | Chapter |
|----------|-----|--------|---------|
| P0 | Knowledge graph write-buffer queue | Medium | GAP 1 |
| P0 | Internal circuit breakers | Low | GAP 4 |
| P0 | MoA aggregator fallback chain | Low | GAP 5 |
| P1 | Summarization verifier for marketing | Medium | GAP 2 |
| P1 | Source penalty escalation | Low | GAP 3 |
| P1 | Telegram channel fingerprinting | Medium | LOOPHOLE 1 |
| P1 | Override audit agent | Low | GAP 6 |
| P2 | Admin CLI rate limiting + TOTP | Low | LOOPHOLE 3 |
| P2 | STATIC decoder input length guard | Low | LOOPHOLE 2 |
| P2 | HealthCheck watchdog timer | Trivial | BLIND SPOT 1 |
| P2 | Knowledge graph backup RPO | Low | BLIND SPOT 2 |
| P2 | Marketing kill switch | Low | BLIND SPOT 3 |
| P3 | Disaster recovery plan | Documentation | BLIND SPOT 4 |
| P3 | Cost projection agent | Medium | BLIND SPOT 5 |
| P3 | 10 new skills (see Part D) | Medium | Skills |
| P3 | 14+ new APIs (see Part C) | Ongoing | APIs |

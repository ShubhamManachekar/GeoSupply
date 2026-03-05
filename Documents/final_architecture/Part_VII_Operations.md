# Part VII: Operations — Admin CLI, Portal, Autonomous Ops, DR, Cost
## FA v1 | Gap Mitigations: G7, G10 applied

## 7.1 Admin CLI Manager (`geosupply` command)

```
INSTALL: pip install geosupply-cli (or python -m geosupply)
AUTH: Password + TOTP for sensitive commands (v10)
RATE LIMIT: 5 failed attempts → 30 min lockout (v10)

COMMAND TREE:

geosupply status                     → Swarm health dashboard
    ├── status agents               → All 38 agent states
    ├── status workers              → All 40 worker states
    ├── status pipeline             → Current pipeline progress
    └── status loopholes            → Last LoopholeHunter report

geosupply pipeline <action>
    ├── pipeline run                → Trigger immediate pipeline
    ├── pipeline pause              → Pause scheduling
    ├── pipeline resume             → Resume scheduling
    └── pipeline history            → Last 10 pipeline run summaries

geosupply agents <action>
    ├── agents list                 → List with status/health
    ├── agents restart <name>       → Restart specific agent
    └── agents disable <name>       → Disable (requires TOTP)

geosupply override <action>           ← TOTP REQUIRED
    ├── override halt               → Emergency stop
    ├── override degraded <level>   → Force DEGRADED_MODE
    ├── override release            → Release from DEGRADED_MODE
    ├── override approve <id>       → Approve quarantined brief
    └── override rollback           → Rollback deployment

geosupply cost <period>
    ├── cost today                  → Today's spend (INR)
    ├── cost week                   → This week's spend
    ├── cost month                  → Monthly spend
    └── cost projection             → Projected monthly total

geosupply security <action>           ← TOTP REQUIRED
    ├── security rotate <key>       → Rotate specific API key
    ├── security rotate all         → Rotate ALL keys
    └── security audit              → Security audit report

geosupply loophole <action>
    ├── loophole run                → Run all 24 checks now
    ├── loophole findings           → All open findings
    ├── loophole history            → Trend over 30 days
    └── loophole accept <id>        → Accept risk for finding

geosupply marketing <action>
    ├── marketing queue             → Pending approvals
    ├── marketing approve <id>      → Approve for publish
    ├── marketing reject <id>       → Reject with reason
    ├── marketing halt              → Stop all publishing (v10)
    ├── marketing purge             → Delete last 24hr tweets (v10)
    └── marketing stats             → Engagement metrics

geosupply backup <action>
    ├── backup run                  → Trigger immediate backup
    ├── backup status               → Last backup timestamps
    ├── backup restore <target>     → Restore from backup
    └── backup verify               → Verify backup integrity

geosupply channel <action>
    ├── channel list                → All ingestion channels
    ├── channel verify <id>         → Re-verify channel fingerprint
    └── channel suspend <id>        → Suspend channel ingestion
```

---

## 7.2 Admin Web Portal (Streamlit)

```
12 DASHBOARD PAGES:

Page 1:  System Overview          → Health grid, pipeline status, cost
Page 2:  Agent Monitor            → 38 agent cards with state, latency, cost
Page 3:  Pipeline Tracker         → Real-time pipeline step progress
Page 4:  Intelligence Dashboard   → GeoRiskScore map, briefs, predictions
Page 5:  Cost Analytics           → INR spend charts, projections, budget
Page 6:  Source Manager           → Source credibility scores, quarantine queue
Page 7:  Knowledge Graph Viewer   → Interactive entity-relation graph (NetworkX vis)
Page 8:  Cyber Threat Dashboard   → Threat map, CyberThreatScores, MITRE ATT&CK
Page 9:  Marketing Dashboard      → Tweet queue, engagement analytics, revenue
Page 10: Admin Override Panel     → Approval queue, manual controls, audit trail
Page 11: Deployment Dashboard     → CI/CD pipeline status, canary metrics
Page 12: LoopholeHunter Dashboard → 24-check grid, findings timeline, health heatmap (v10)

ACCESS CONTROL:
    ADMIN:    All pages, all actions
    OPERATOR: Pages 1-9, view-only on 10-12
    VIEWER:   Pages 1-5, read-only
    API:      Pages 1-5, programmatic access

FA v1 G7 FIX — WebSocket JWT Specification:
    Claims: {
        sub: admin_id (UUID),
        scope: "portal" | "portal:read" | "portal:admin",
        pages: [1,2,...12],        # allowed page numbers
        exp: 900 (15 min),         # matches session timeout
        iat: timestamp,
        jti: unique_token_id       # for revocation
    }
    Handshake: wss://localhost:8501/ws?token=<JWT>
    Validation: verify signature → check exp → check scope → open connection
    Revocation: JTI blacklist in Redis/SQLite (checked every connection)
    Override page: JWT exp reduced to 300s (5 min)
```

---

## 7.3 Autonomous Operations Engine

### Four Autonomy Levels

```
LEVEL 0: SUPERVISED — Human approves every action
    Used during: initial deployment, incident response

LEVEL 1: GUIDED — Human approves critical, auto-runs routine
    Used during: early production (Week 1-4)

LEVEL 2: AUTONOMOUS — System runs independently, human notified
    Used during: stable production (Week 5+)
    DEFAULT LEVEL

LEVEL 3: FULL AUTONOMOUS — System self-adjusts, human reviews weekly
    Used during: mature production (Month 3+)
    Requires: proven accuracy track record
```

### Autonomous vs Human-Required Actions

```
FULLY AUTONOMOUS (no human):
    ✅ Scheduled pipeline runs (every 4-8 hours)
    ✅ Source credibility updates
    ✅ Knowledge graph updates
    ✅ Dashboard refresh
    ✅ Backup execution
    ✅ Prediction tweets (confidence >0.75)
    ✅ Data visualisation posts
    ✅ Security patch PRs
    ✅ LoopholeHunter checks
    ✅ DEGRADED_MODE Lv1-2 auto-recovery (v10)

HUMAN APPROVAL REQUIRED:
    ❌ Production deployment (canary → full)
    ❌ Breaking dependency upgrades
    ❌ New API integrations
    ❌ Insight threads (geopolitical sensitivity)
    ❌ Breaking news alerts
    ❌ DEGRADED_MODE Lv3-4 release
    ❌ Key rotation
    ❌ Knowledge graph major merge
    ❌ Content mentioning countries/leaders
    ❌ Budget cap changes
```

---

## 7.4 Disaster Recovery Plan

```
RPO (Recovery Point Objective):
    Knowledge Graph:  6 hours
    ChromaDB:        24 hours
    SQLite:          24 hours
    Config:           7 days
    Code:             0 hours (GitHub — always current)
    Logs:             0 hours (Supabase — cloud, always current)

RTO (Recovery Time Objective): 4 hours

BACKUP TARGETS:
    All → Google Drive /geosupply_backups/
    All encrypted with AES-256 (key from SecurityAgent, rotated monthly)

RECOVERY SCENARIOS:
    PC failure:      Clone + restore from Drive (2 hours)
    Data corruption: Restore from last backup (1 hour)
    Security breach: HALT + rotate keys + audit (30 min)
```

---

## 7.5 Cost Projection System

```
CostProjectionAgent tracks:
    Last 7-day cost rate (INR/hr)
    Daily/weekly/monthly projections with 5-10% buffer

ALERTS:
    Projected daily > ₹250    → WARN
    Projected daily > ₹270    → ALERT
    Projected monthly > ₹400  → WARN (80% of cap)
    Projected monthly > ₹450  → ALERT (90% of cap)

COST REDUCTION SUGGESTIONS:
    1. Reduce pipeline frequency (6hr → 8hr → 12hr)
    2. Downgrade Tier-3 to Tier-2 where quality sufficient
    3. Disable P3 tasks (dashboards, visualisations)
    4. Reduce MoA from 3 proposers to 2
    5. Skip non-critical ingestion sources
```

## CROSS-CHECK ✅
```
✓ Admin CLI has TOTP for sensitive commands (LOOPHOLE 3)
✓ Rate limiting: 5 failures → 30 min lockout
✓ Marketing kill switch: halt + purge (BLIND SPOT 3)
✓ Backup encrypted AES-256 (LOOPHOLE 10)
✓ Portal session timeout: 15min idle lock, 30min expire (LOOPHOLE 11)
✓ 4 autonomy levels documented with action matrix
✓ DR plan: RTO 4hr, RPO 6hr (BLIND SPOT 4)
✓ Cost projection with INR alerts (BLIND SPOT 5)
✓ [FA v1] WebSocket JWT claims/scope/revocation fully specified (G7)
✓ [FA v1] Test fixture strategy defined: factory pattern in tests/fixtures/ (G10)
```

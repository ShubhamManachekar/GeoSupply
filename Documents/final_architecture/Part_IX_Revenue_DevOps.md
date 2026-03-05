# Part IX: Revenue, Marketing, Tech Team, CI/CD & Dev Tooling
## FA v1 | Gap Mitigations: G10 applied

## 9.1 Marketing & Revenue Architecture

### Content Pipeline
```
Intelligence Pipeline Output
    ↓
ContentGeneratorAgent
    ↓ generates tweets, threads, visualisations
SummarizationVerifierSubAgent (v10)
    ↓ checks semantic accuracy
FactCheckAgent
    ↓ verifies claims
Content Approval Queue
    ↓ autonomous (>0.75) or human (threads/breaking)
TwitterPublisherAgent
    ↓ publishes to @GeoSupplyAI
AnalyticsAgent
    ↓ tracks engagement
RevenueTrackerAgent
    ↓ measures growth
```

### 4-Tier Monetisation Model

```
TIER 1 — FREE (Twitter/X)
    2-3 daily prediction tweets (morning/evening IST)
    1 daily data visualisation
    Weekly insight thread
    Monthly accuracy scorecard
    PURPOSE: build audience, establish credibility

TIER 2 — NEWSLETTER (email-gated, free)
    Weekly intelligence digest
    Deeper analysis than Twitter
    India-specific supply chain insights
    PURPOSE: build email list, direct relationship

TIER 3 — PREMIUM API (₹500/month)
    Real-time intelligence API
    GeoRiskScore queries
    Supply chain stress index API
    PURPOSE: B2B revenue

TIER 4 — CONSULTING (future)
    Custom intelligence reports
    Corporate geopolitical briefings
    PURPOSE: high-value revenue
```

### Content Approval Rules
```
AUTONOMOUS: Prediction tweets (>0.75 confidence, FactChecked)
AUTONOMOUS: Data visualisations, engagement responses
HUMAN:      Insight threads, breaking alerts
HUMAN:      Content mentioning countries/leaders/military
HUMAN:      Borderline confidence (0.70-0.75)
KILL SWITCH: geosupply marketing halt/purge (v10)
```

---

## 9.2 Tech Team Agents — CI/CD & API Discovery

### Agent Roster
```
TechScoutAgent    — Weekly tech stack scan (CVEs, new releases)
APIScanAgent      — Monthly API discovery (test + schema gen)
DepUpdateAgent    — Daily security scan, weekly feature updates
DeployAgent       — 6-stage deployment pipeline
```

### 6-Stage Vertical Test Pipeline

```
STAGE 1 — UNIT (per commit)
    pytest per module, 80% coverage gate, mocked APIs

STAGE 2 — INTEGRATION (per phase)
    18 cross-module scenarios, message contract validation

STAGE 3 — STAGING (per deploy)
    Full pipeline with synthetic data, all 40 workers exercised

STAGE 4 — SMOKE (post-deploy)
    Hit all endpoints, verify dashboard, verify CLI, 10/10 pass

STAGE 5 — CANARY (first 6 hours)
    New pipeline alongside old, compare quality/latency/cost
    If new worse on any metric → auto-rollback

STAGE 6 — LIVE (after canary passes)
    All traffic on new version, 24-hour intensive monitoring
    Old version warm for 48-hour rollback window
```

### Git Strategy
```
main       → production
develop    → staging
feature/*  → per-module dev
release/*  → release candidates
hotfix/*   → emergency patches
```

---

## 9.3 Development Tooling — Three-Tool Strategy

### Tool Roles (Clear Separation)

| Tool | Role | When Used | Scope |
|------|------|-----------|-------|
| **GitHub Copilot** | Inline coding assistant | During development | Single file, autocomplete |
| **Antigravity** | IDE orchestrator + builder | Module development | Multi-file, test runner, CI |
| **Claude** | Architect + auditor | Design reviews | Architecture, grading, cost analysis |

### Copilot Configuration (`.github/copilot-instructions.md`)
```markdown
# GeoSupply AI — Copilot Instructions

## Architecture Rules
- Every agent class inherits from BaseWorker/BaseSubAgent/BaseAgent/BaseSupervisor
- All inter-agent communication uses AgentMessage Pydantic model
- All costs tracked in INR, never USD
- HALLUCINATION_FLOOR = 0.70 (never lower this)
- Tier-1 workers MUST use STATIC decoder
- No lateral worker-to-worker communication

## Code Style
- Python 3.10+, type hints everywhere
- Pydantic v2 for all schemas
- async/await for all I/O
- @breaker decorator for external API calls
- @internal_breaker for Tier-3+ agent calls (v10)
- SecurityAgent.get_key() for all API keys

## Testing
- pytest with 80% coverage minimum
- All workers must have mock fixtures
- Integration tests use synthetic data only
```

### FA v1: G10 FIX — Test Fixture Strategy

```
SHARED FIXTURE APPROACH:
    tests/fixtures/
    ├── mock_worker.py      ← MockWorker factory: create_mock_worker(name, tier, caps)
    ├── mock_agent.py       ← MockAgent factory: create_mock_agent(name, domain)
    ├── mock_subagent.py    ← MockSubAgent factory: create_mock_subagent(name, steps)
    ├── mock_eventbus.py    ← InMemoryEventBus for testing without side effects
    ├── synthetic_data.py   ← Generators for: news articles, telegram msgs, API responses
    └── conftest.py         ← Shared pytest fixtures: db, chromadb, event_bus, security

PATTERN:
    - All mocks use Pydantic models for input/output (schema-validated)
    - `@pytest.fixture` for setup/teardown, `@pytest.mark.asyncio` for async tests
    - Integration tests use `synthetic_data.py` generators (never real data)
    - Coverage report: `pytest --cov=src/geosupply --cov-report=html`
```

### Development Workflow
```
1. Claude designs architecture/module spec
2. Antigravity scaffolds module structure
3. Copilot assists inline coding
4. Antigravity runs tests + lint
5. Claude reviews architecture compliance
6. DeployAgent stages → canary → live
```

## CROSS-CHECK ✅
```
✓ Marketing pipeline includes SummarizationVerifier (GAP 2)
✓ Marketing includes kill switch (BLIND SPOT 3)
✓ 4-tier monetisation documented with INR pricing
✓ 6-stage deploy pipeline documented
✓ Git strategy documented
✓ All 3 dev tools have clear role separation
✓ Copilot instructions enforce architecture rules
✓ DeployAgent handles canary + auto-rollback
✓ [FA v1] Test fixture strategy with factory pattern defined (G10)
```

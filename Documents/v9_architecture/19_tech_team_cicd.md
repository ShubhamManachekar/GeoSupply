# Chapter 19: Tech Team Agents — CI/CD, API Discovery, Staging & Deployment

## Design Philosophy

> **The tech team never sleeps. It finds new APIs, tests them, stages changes, and deploys — all autonomously.**
> Human reviews PRs and approves production deploys. Everything else is automated.

---

## Tech Team Agent Inventory

```
┌──────────────────────────────────────────────────────────────────┐
│                    TECH TEAM AGENT LAYER (NEW v9)               │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │ TechScoutAgent │  │ APIScanAgent   │  │ DepUpdateAgent │    │
│  │ Latest tech    │  │ Find new APIs  │  │ Dependency     │    │
│  │ stack tracking │  │ Test endpoints │  │ updates + audit│    │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘    │
│          │                    │                    │              │
│          ▼                    ▼                    ▼              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │ StageAgent     │  │ VerticalTest   │  │ DeployAgent    │    │
│  │ Staging env    │  │ Agent          │  │ Production     │    │
│  │ validation     │  │ Stage-by-stage │  │ deployment     │    │
│  └───────┬────────┘  │ test pipeline  │  │ + rollback     │    │
│          │           └───────┬────────┘  └───────┬────────┘    │
│          │                    │                    │              │
│          ▼                    ▼                    ▼              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TechSupervisor                         │  │
│  │  Orchestrates all tech team agents                        │  │
│  │  Enforces: discover → test → stage → verify → deploy     │  │
│  │  Human approval gate before production                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## TechScoutAgent — Latest Tech Stack Monitoring

```python
class TechScoutAgent(BaseAgent):
    """
    Continuously monitors for latest tech stack updates relevant
    to GeoSupply. Recommends upgrades when beneficial.

    MONITORS:
        Python ecosystem:
            - Python version updates (3.10 → 3.11 → 3.12+)
            - FastAPI releases (new features, security patches)
            - Pydantic v2 updates
            - Streamlit updates (new components, performance)
            - ChromaDB releases (new features, perf improvements)
            - XGBoost updates

        LLM ecosystem:
            - New Ollama models (better 3b/14b/20b alternatives)
            - Groq API changes (new models, rate limit changes)
            - New STATIC decoder techniques
            - Embedding model improvements (sentence-transformers)

        Infrastructure:
            - GitHub Actions runner updates
            - Supabase feature releases
            - Qdrant Cloud updates
            - Docker/container security patches

        Security:
            - CVE alerts for all dependencies
            - Python package vulnerability reports
            - OWASP top-10 changes relevant to LLM systems

    SCHEDULE: Weekly scan (Sunday, after regression tests)
    OUTPUT: TechScoutReport → TechSupervisor → Admin notification

    ACTIONS:
        LOW risk update  → auto-create PR with changelog
        MEDIUM risk      → create PR + flag for admin review
        HIGH risk        → report only, no PR, admin must decide
        SECURITY patch   → auto-create PR + CRITICAL alert
    """
    name = "TechScoutAgent"
    domain = "tech_team"

    SOURCES = [
        "https://pypi.org/rss/updates.xml",
        "https://github.com/advisories",
        "https://ollama.ai/library",
        "https://api.github.com/repos/pydantic/pydantic/releases",
        "https://api.github.com/repos/chroma-core/chroma/releases",
    ]

    async def scan(self) -> 'TechScoutReport':
        """Weekly tech stack scan."""
        updates = []
        for source in self.SOURCES:
            new_versions = await self._check_source(source)
            updates.extend(new_versions)

        # Categorise by risk
        report = TechScoutReport(
            security_patches=[u for u in updates if u.is_security],
            feature_updates=[u for u in updates if u.is_feature],
            breaking_changes=[u for u in updates if u.is_breaking],
            recommendations=self._generate_recommendations(updates)
        )
        return report
```

---

## APIScanAgent — API Discovery & Integration

```python
class APIScanAgent(BaseAgent):
    """
    Discovers new APIs that could enhance GeoSupply's data coverage.
    Tests endpoints, validates response schemas, and prepares connectors.

    DISCOVERY TARGETS:
        Geopolitical data:
            - New OSINT data feeds
            - Government open data portals (India + global)
            - Think tank API endpoints (SIPRI, IISS, etc.)
            - UN agencies data services

        Supply chain data:
            - New shipping/logistics APIs
            - Port authority data feeds
            - Commodity price APIs
            - Trade flow databases

        India-specific:
            - New data.gov.in datasets
            - State-level API endpoints
            - New ULIP integrations (129 → more)
            - ONDC (Open Network for Digital Commerce)
            - DigiLocker integration potential
            - IndiaStack APIs (UPI, Aadhaar, GSTN)

        Cyber threat data:
            - New threat intelligence feeds
            - Vulnerability databases
            - Dark web monitoring APIs

    WORKFLOW:
        1. DISCOVER: Scan registries, docs, announcements for new APIs
        2. TEST:     Hit endpoint with test queries, validate response
        3. SCHEMA:   Generate Pydantic model from response
        4. MOCK:     Create mock fixture for testing
        5. ESTIMATE: Calculate rate limits, cost (INR), reliability
        6. PROPOSE:  Create integration proposal → TechSupervisor
        7. AWAIT:    Human approves → StageAgent deploys connector
    """
    name = "APIScanAgent"
    domain = "tech_team"

    async def discover_and_test(self) -> list['APIProposal']:
        """Monthly API discovery scan."""
        proposals = []

        # Check known API registries
        for registry in self.API_REGISTRIES:
            candidates = await self._scan_registry(registry)
            for api in candidates:
                test_result = await self._test_endpoint(api)
                if test_result.is_valid:
                    proposal = APIProposal(
                        name=api.name,
                        url=api.url,
                        data_type=api.category,
                        response_schema=self._generate_schema(test_result.response),
                        rate_limit=test_result.rate_limit,
                        cost_inr=test_result.estimated_cost_inr,
                        reliability_score=test_result.uptime_estimate,
                        integration_effort="LOW" if test_result.is_rest_json else "MEDIUM",
                        mock_fixture=self._create_mock(test_result.response),
                    )
                    proposals.append(proposal)

        return proposals
```

---

## DepUpdateAgent — Dependency Management

```python
class DepUpdateAgent(BaseAgent):
    """
    Keeps all Python dependencies updated and secure.

    RESPONSIBILITIES:
        1. Weekly pip audit for known vulnerabilities
        2. Monthly dependency update check (non-breaking)
        3. Quarterly major version review
        4. Generate SBOM (Software Bill of Materials) per release
        5. Pin all versions in requirements.txt (no floating)

    WORKFLOW:
        1. pip audit --json → list of vulnerable packages
        2. For each CVE: assess severity + impact on GeoSupply
        3. CRITICAL/HIGH: auto-create PR with fix
        4. MEDIUM: flag for next update cycle
        5. LOW: log for quarterly review

    OUTPUT: DepUpdateReport with all changes + risk assessment
    """
    name = "DepUpdateAgent"
    domain = "tech_team"
```

---

## Vertical Test Pipeline — Stage-by-Stage

```
VERTICAL TEST STAGES (run by VerticalTestAgent):

STAGE 1 — UNIT (per module)
    pytest per module
    80% coverage gate
    Mocked external APIs
    Runs: every commit

STAGE 2 — INTEGRATION (per phase)
    Cross-module data flows
    9 integration scenarios
    Message contract validation
    Runs: phase complete

STAGE 3 — STAGING (full system)
    Deploy to staging environment (local FastAPI)
    Full pipeline run with synthetic data
    All 32 workers exercised
    Dashboard renders verified
    Admin CLI commands tested
    Runs: before production deploy

STAGE 4 — SMOKE (post-deploy)
    Hit production endpoints
    Verify dashboard loads
    Verify pipeline triggers
    Verify admin CLI connects
    10/10 must pass to keep deployment
    Runs: immediately after deploy

STAGE 5 — CANARY (gradual rollout)
    Run new pipeline alongside old for 1 cycle
    Compare brief quality (old vs new)
    Compare latency + cost
    If new is worse on any metric → auto-rollback
    Runs: first 6-hour cycle after deploy

STAGE 6 — LIVE (full production)
    All traffic on new version
    Monitoring intensified for 24 hours
    SelfHealingEngine on high alert
    Old version kept warm for rollback (48hr retention)
    Runs: after canary passes
```

---

## DeployAgent — Production Deployment Pipeline

```python
class DeployAgent(BaseAgent):
    """
    Manages the full deployment lifecycle.

    DEPLOYMENT TARGETS:
        FastAPI backend  → local PC (Mon-Thu 10am-6pm) or GCP
        Streamlit dashboard → Streamlit Cloud (free tier)
        GitHub Actions   → CI/CD pipeline
        ChromaDB        → local persistent store
        Supabase        → cloud database (logs, audit)

    DEPLOYMENT FLOW:
        1. All vertical tests pass (Stage 1-2)
        2. Deploy to staging (Stage 3)
        3. Staging smoke tests pass (Stage 4)
        4. Human approval (admin CLI or portal)
        5. Canary deploy (Stage 5)
        6. Canary passes → full rollout (Stage 6)
        7. Monitor 24hr → stable → mark release

    ROLLBACK:
        Automatic: canary fails → instant rollback
        Manual: admin CLI `geosupply override rollback`
        Time limit: old version kept warm for 48 hours
        Database: migration rollback scripts per release

    GIT STRATEGY:
        main branch   → production
        develop branch→ staging
        feature/*     → per-module development
        release/*     → release candidates
        hotfix/*      → emergency patches
    """
    name = "DeployAgent"
    domain = "tech_team"
```

---

## TechSupervisor — Orchestrates All Tech Team Agents

```
SCHEDULE:
    DAILY:     DepUpdateAgent security scan
    WEEKLY:    TechScoutAgent tech stack scan (Sunday)
    MONTHLY:   APIScanAgent API discovery
    PER-COMMIT: VerticalTestAgent Stage 1
    PER-PHASE:  VerticalTestAgent Stage 2
    PER-DEPLOY: Full Stage 3-6 pipeline

HUMAN GATES:
    ✅ Auto: Security patches (auto-PR)
    ✅ Auto: Minor dependency updates (auto-PR)
    ❌ Human: Breaking dependency changes
    ❌ Human: New API integrations
    ❌ Human: Production deployment approval
    ❌ Human: Major version upgrades
```

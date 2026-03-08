# Part IV: Agent Layer — 39 Agents + Capability Advertising
## FA v1 | Gap Mitigations: G2 applied

## 4.1 BaseAgent Class

```python
class BaseAgent(ABC):
    """
    Agents own a domain. They manage pools of workers and subagents.
    Agents advertise capabilities so MoE can route tasks dynamically.

    STATE MACHINE:
        IDLE → BUSY → DONE → IDLE
                  ↓
              ERROR → RECOVERY → IDLE

    CAPABILITY ADVERTISING:
        Each agent declares what it can do:
            {"name": "FactCheckAgent", "capabilities": ["FACT_CHECK", "CLAIM_VERIFY"],
             "cost_per_call_inr": 0.02, "avg_latency_ms": 1500}
        MoE routing uses this to select the best agent for each task.

    INTERNAL CIRCUIT BREAKER (v10):
        All Tier-3 agent calls protected by @internal_breaker:
            timeout_s: 30 (FactCheck), 20 (Auditor), 60 (BriefSynth)
            max_failures: 3 → OPEN → safe default → HALF_OPEN probe (5min)
    """

    name: str
    domain: str
    capabilities: set[str]
    max_concurrent: int = 3
    _state: Literal["IDLE", "BUSY", "DONE", "ERROR", "RECOVERY"] = "IDLE"

    # --- FA v1: G2 FIX — State transition guards ---
    _VALID_TRANSITIONS = {
        "IDLE":     {"BUSY"},
        "BUSY":     {"DONE", "ERROR"},
        "DONE":     {"IDLE"},
        "ERROR":    {"RECOVERY"},
        "RECOVERY": {"IDLE"},
    }

    def _transition(self, new_state: str) -> None:
        """Guarded state transition. Raises InvalidTransition if illegal."""
        if new_state not in self._VALID_TRANSITIONS.get(self._state, set()):
            raise InvalidStateTransition(
                f"{self.name}: {self._state} → {new_state} is not allowed"
            )
        self._prev_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.utcnow()
```

---

## 4.2 Complete Agent Census (39 Agents, 7 Groups)

### Group A: Infrastructure Singletons (9) — Always On, Off Critical Path

| # | Agent | Key Contract | v8/v9/v10 |
|---|-------|-------------|-----------|
| 1 | **LoggingAgent** | `log(event, *, cost_inr, trace_id, severity)` → Supabase `swarm_logs` | v8 |
| 2 | **FactCheckAgent** | `verify(claims[]) → {status, scores[], quarantined[]}` 7-step pipeline, 0.70 floor | v8 |
| 3 | **HealthCheckAgent** | `check() → {status_28_apis, latency, queue_depth}` monitors 28 APIs every 5 min | v8 |
| 4 | **SecurityAgent** | `get_key(service) → str` rotation every 30 days, vault-backed | v8 |
| 5 | **AuditorAgent** | `audit(pipeline_output) → AuditResult` stratified sampling (5-20%) | v8 |
| 6 | **SourceFeedbackAgent** | `update_credibility(source, delta)` manages source scores SQLite | v8 |
| 7 | **CyberDefenseAgent** | `scan_input_for_injection(text) → {is_suspicious, patterns}` prompt injection + anomaly | v9 |
| 8 | **WatchdogAgent** | Separate process. Monitors HealthCheck (5min), LoopholeHunter (30min), LoggingAgent (10min) | **v10** |
| 9 | **InputGuardAgent** | Pre-processing sanitisation: token count → injection scan → unicode normalise → sanitise | **v10** |

### Group B: Intelligence & Knowledge (5)

| # | Agent | Role | v8/v9/v10 |
|---|-------|------|-----------|
| 10 | **KnowledgeGraphAgent** | NetworkX graph of geopolitical entities/relations. v10: write-buffer queue (single-writer) | v9 |
| 11 | **PerformanceLearnerAgent** | XGBoost model predicts optimal tier routing. v10: A/B test before committing changes | v9 |
| 12 | **SourceClusterAgent** | Detects coordinated source networks by IP/domain/author/style embedding | **v10** |
| 13 | **ChannelVerificationAgent** | Telegram/RSS channel integrity via fingerprinting + KL divergence drift detection | **v10** |
| 13b| **TimelineGeneratorAgent** | Parses GeoEventRecords to build chronological/spatial event graphs + trend detection | **FA v1.1** |

### Group C: Dev Agents (4) — Build-Time Only

| # | Agent | Role | Copilot Integration |
|---|-------|------|---------------------|
| 14 | **ScaffoldAgent** | Generate module skeleton from spec | Copilot suggests boilerplate |
| 15 | **CodeReviewAgent** | Static analysis + best practice checks | Copilot reviews inline |
| 16 | **DocGenAgent** | Auto-generate docstrings + README sections | Copilot drafts docs |
| 17 | **RefactorAgent** | Identify + apply refactoring patterns | Antigravity orchestrates |

### Group D: Test Agents (5) — Build + Production

| # | Agent | Gate | Threshold |
|---|-------|------|-----------|
| 18 | **UnitTestAgent** | Coverage | ≥80% per module |
| 19 | **IntegrationTestAgent** | Scenarios | 18 scenarios all pass |
| 20 | **LoadTestAgent** | SLA | <12 min full pipeline |
| 21 | **RegressionTestAgent** | Baseline | No regression from baseline |
| 22 | **ContractTestAgent** | Schema | All AgentMessage schemas valid |

### Group E: Tech Team (4)

| # | Agent | Schedule | Role |
|---|-------|----------|------|
| 23 | **TechScoutAgent** | Weekly (Sunday) | Scan Python/LLM/infra updates, CVEs |
| 24 | **APIScanAgent** | Monthly | Discover + test new APIs, generate schemas |
| 25 | **DepUpdateAgent** | Daily (security), Monthly (features) | pip audit, SBOM, dependency PR |
| 26 | **DeployAgent** | Per-release | 6-stage pipeline: Unit→Integ→Stage→Smoke→Canary→Live |

### Group F: Marketing & Revenue (6)

| # | Agent | Role | Auto/Manual |
|---|-------|------|-------------|
| 27 | **ContentGeneratorAgent** | Generate tweets, threads, visualisations from intelligence | Auto (>0.75 confidence) |
| 28 | **TwitterPublisherAgent** | Post to @GeoSupplyAI, track engagement | Auto (predictions), Manual (threads/breaking) |
| 29 | **PredictionAgent** | Generate market-ready predictions with accuracy tracking | Auto |
| 30 | **RevenueTrackerAgent** | Track follower growth, MRR, engagement in INR | Auto |
| 31 | **AnalyticsAgent** | Twitter engagement analytics + content strategy | **v10** |
| 32 | **NewsletterAgent** | Email newsletter via SendGrid/Resend | **v10** |

### Group G: Audit & Security (6)

| # | Agent | Schedule | Fixes |
|---|-------|----------|-------|
| 33 | **LoopholeHunterAgent** | Every pipeline run (24 checks) | All v9 gaps proactively |
| 34 | **OverrideAuditAgent** | Weekly | v9 GAP 6 (write-only audit) |
| 35 | **PenTestAgent** | Weekly (Sunday) | 8 penetration tests |
| 36 | **SummarizationAuditAgent** | Per marketing content | v9 GAP 2 (semantic distortion) |
| 37 | **BackupAgent** | Schedule-based | v9 BLIND SPOT 4 (no DR) |
| 38 | **CostProjectionAgent** | Daily | v9 BLIND SPOT 5 (reactive budget) |

## CROSS-CHECK ✅
```
✓ 39 agents listed (9 infra + 4 intel + 4 dev + 5 test + 4 tech + 6 marketing + 6 audit)
✓ All agents have capabilities and contracts
✓ All v10 agents map to loophole/gap fixes
✓ Internal circuit breakers on all Tier-3 calls (v10)
✓ WatchdogAgent runs as separate process
✓ FactCheckAgent maintains 0.70 floor (LOCKED)
✓ SecurityAgent handles all API keys
✓ [FA v1] State transition guards with _VALID_TRANSITIONS map (G2)
```

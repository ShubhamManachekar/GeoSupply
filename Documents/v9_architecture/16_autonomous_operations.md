# Chapter 16: Autonomous Operations + Manual Override

## Design Philosophy

> **The swarm runs itself. The admin watches. The override exists for when the swarm is wrong.**

---

## Autonomy Spectrum

```
LEVEL 0 — FULLY MANUAL        (NOT used in v9)
    Human triggers every pipeline run, approves every brief

LEVEL 1 — SUPERVISED AUTONOMY  (v8 default)
    Swarm runs on schedule, human reviews critical outputs

LEVEL 2 — OPERATIONAL AUTONOMY (v9 DEFAULT) ◄── THIS
    Swarm runs, learns, self-heals autonomously
    Human gets alerts only for anomalies
    Manual override available for everything
    Critical decisions (HALT, budget change) require human

LEVEL 3 — FULL AUTONOMY        (v9 FUTURE)
    Swarm adjusts its own routing, models, and budgets
    Human reviews weekly summary only
    Requires 6+ months of operational history
```

---

## Autonomous Operations Engine

### AutonomousScheduler

```python
class AutonomousScheduler:
    """
    Manages the 6-hour pipeline cycle + secondary schedules.

    SCHEDULES (all autonomous):
        Every 6 hours:   Full pipeline (ingest → brief → dashboard)
        Every 2 minutes: PC Ollama health check
        Every 15 minutes: External API health check
        Every 5 minutes:  ChromaDB queue flush check
        Every 24 hours:   GCP credit balance check
        Every Tuesday:    ML model retrain (ConflictPredictor)
        Every Thursday:   ML model retrain (drift adjustment)
        Every Sunday:     Full audit + regression test suite
        Weekly:           SemanticDriftMonitor analysis
        Monthly:          OFAC list update + key rotation

    SELF-ADJUSTING:
        If pipeline takes >12 min: extend next interval to 8 hours
        If pipeline takes <5 min:  shrink interval to 4 hours (more fresh data)
        If budget >80% consumed:   reduce to 1 run/day
        If all APIs healthy:       run extra off-schedule ingestion batch

    MANUAL OVERRIDE:
        CLI: geosupply pipeline run     → immediate run
        CLI: geosupply pipeline pause   → suspend schedule
        Portal: Run Now button          → immediate run
        All overrides logged to audit trail
    """

    def __init__(self):
        self.default_interval_hours = 6
        self.current_interval_hours = 6
        self._paused = False
        self._override_active = False

    async def run_cycle(self):
        while True:
            if self._paused:
                await asyncio.sleep(60)  # Check pause every minute
                continue

            if self._override_active:
                self._override_active = False
                # Override run — immediate

            # Execute full pipeline
            result = await SwarmMaster.handle_pipeline_cycle()

            # Self-adjust interval
            if result.latency_ms > 720_000:  # >12 min
                self.current_interval_hours = min(8, self.current_interval_hours + 1)
            elif result.latency_ms < 300_000:  # <5 min
                self.current_interval_hours = max(4, self.current_interval_hours - 0.5)

            await asyncio.sleep(self.current_interval_hours * 3600)
```

### AutonomousDecisionEngine

```python
class AutonomousDecisionEngine:
    """
    Makes operational decisions WITHOUT human input.

    CAN DECIDE AUTONOMOUSLY:
        ✅ Switch model fallback (PC→Groq→Claude)
        ✅ Activate DEGRADED_MODE Level 1 or 2
        ✅ Reset circuit breakers
        ✅ Flush stuck queues
        ✅ Adjust pipeline interval
        ✅ Re-route tasks to different tier
        ✅ Apply source penalties
        ✅ Trigger extra ingestion batch
        ✅ Skip non-critical pipeline stages

    REQUIRES HUMAN APPROVAL:
        ❌ Activate DEGRADED_MODE Level 3 or 4
        ❌ Change budget caps
        ❌ Modify HALLUCINATION_FLOOR
        ❌ Release from EMERGENCY HALT
        ❌ Override quarantined brief (manual approve)
        ❌ Change MoE routing table
        ❌ Deploy new model
        ❌ Modify security keys

    NOTIFICATION POLICY:
        AUTONOMOUS decisions → logged, no alert
        AUTONOMOUS decisions with risk → logged + Telegram alert
        HUMAN-REQUIRED decisions → Telegram alert + CLI notification
        EMERGENCY → Telegram + email + CLI + dashboard banner
    """

    AUTONOMOUS_ACTIONS = {
        "model_fallback":      {"risk": "low",    "notify": False},
        "degraded_mode_1":     {"risk": "medium", "notify": True},
        "degraded_mode_2":     {"risk": "medium", "notify": True},
        "circuit_reset":       {"risk": "low",    "notify": False},
        "queue_flush":         {"risk": "low",    "notify": False},
        "interval_adjust":     {"risk": "low",    "notify": False},
        "tier_reroute":        {"risk": "low",    "notify": False},
        "source_penalty":      {"risk": "low",    "notify": False},
        "extra_ingestion":     {"risk": "low",    "notify": False},
        "skip_stage":          {"risk": "medium", "notify": True},
    }

    HUMAN_REQUIRED_ACTIONS = {
        "degraded_mode_3":     {"risk": "high",     "escalation": "telegram+cli"},
        "degraded_mode_4":     {"risk": "critical",  "escalation": "telegram+email+cli"},
        "budget_change":       {"risk": "high",     "escalation": "cli"},
        "brief_override":      {"risk": "medium",   "escalation": "cli"},
        "routing_change":      {"risk": "high",     "escalation": "cli"},
        "emergency_halt":      {"risk": "critical",  "escalation": "all"},
        "emergency_release":   {"risk": "critical",  "escalation": "all"},
    }
```

---

## Manual Override System

### Override Priority Chain

```
OVERRIDE PRIORITY (highest wins):

1. EMERGENCY HALT (CLI or Portal)
   → ALL operations stop immediately
   → Only 'release' command resumes
   → Logged with timestamp + reason

2. DEGRADED_MODE forced by admin
   → Overrides autonomous degradation
   → Level set by admin takes precedence

3. Brief approval/rejection by admin
   → Overrides FactCheckAgent decision
   → Logged as "manual_override" in audit trail
   → FactCheckAgent learns from override (v9 learning loop)

4. Model switch by admin
   → Overrides MoE routing for specific task type
   → Expires after 24 hours (auto-revert to MoE)
   → Can be made permanent via config change

5. Source score override by admin
   → Overrides SourceFeedbackSubAgent score
   → Logged with admin justification
   → Score locked for 7 days (no automated changes)
```

### Override Audit Trail

```python
class OverrideRecord(BaseModel):
    """Every manual override is permanently recorded."""
    override_id: str        # UUID
    timestamp: datetime
    admin_user: str
    action: str             # e.g. "brief_approve", "halt", "source_override"
    target: str             # What was overridden
    old_value: str          # Previous state/value
    new_value: str          # Admin's override value
    justification: str      # Admin MUST provide reason
    auto_revert_at: Optional[datetime]  # When override expires
    reverted: bool = False
```

---

## Notification System

```
CHANNELS:
    Telegram Bot    → real-time alerts (WARN, ALERT, CRITICAL)
    CLI notifications → visible on next command
    Dashboard banner → persistent until acknowledged
    Email (future)   → for CRITICAL only

ALERT LEVELS:
    INFO     → Autonomous decision logged (no notification)
    WARN     → Autonomous decision with risk (Telegram)
    ALERT    → Human attention recommended (Telegram + CLI)
    CRITICAL → Human action REQUIRED (all channels)

EXAMPLES:
    INFO:     "Model fallback activated: PC→Groq for NER tasks"
    WARN:     "DEGRADED_MODE Level 1 activated: P3 tasks suspended"
    ALERT:    "Budget at 80% (₹240/₹300 daily limit)"
    CRITICAL: "EMERGENCY: All Groq API calls failing. Need manual review."
```

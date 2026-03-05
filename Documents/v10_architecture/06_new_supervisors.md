# Chapter 6: 2 New Supervisors + Upgraded Orchestrator

## New Supervisors

v9: 12 supervisors → **v10: 14 supervisors (+2)**

---

### LoopholeHunterSupervisor

```python
class LoopholeHunterSupervisor(BaseSupervisor):
    """
    Orchestrates all audit, security, and verification agents.

    AGENTS MANAGED:
        LoopholeHunterAgent     — 24-check continuous audit
        OverrideAuditAgent      — Weekly admin pattern review
        PenTestAgent            — Weekly penetration testing
        CyberDefenseAgent       — Real-time threat detection
        SummarizationAuditAgent — Marketing content verification

    SCHEDULE:
        Per pipeline run: LoopholeHunter 24 checks
        Daily:            CyberDefense scan + LoopholeHunter summary
        Weekly (Sunday):  PenTest full suite + OverrideAudit
        Weekly (Monday):  SummarizationAudit on weekly content

    BUDGET: Minimal — all checks are local/rule-based, no LLM calls
    PRIORITY: P1 — security never gets deprioritised

    REPORTING:
        Weekly: AuditReport → admin portal + CLI
        Monthly: SecurityReport → admin email
        Per finding: CRITICAL → immediate Telegram alert
    """
    name = "LoopholeHunterSupervisor"
    domain = "audit"
    max_queue_depth = 20  # Low — checks are fast

    def _select_agent(self, task, available):
        task_map = {
            "LOOPHOLE_CHECK": "LoopholeHunterAgent",
            "OVERRIDE_AUDIT": "OverrideAuditAgent",
            "PEN_TEST": "PenTestAgent",
            "CYBER_SCAN": "CyberDefenseAgent",
            "SUMMARY_AUDIT": "SummarizationAuditAgent",
        }
        target = task_map.get(task.task_type)
        return next((a for a in available if a.name == target), None)
```

---

### DisasterRecoverySupervisor

```python
class DisasterRecoverySupervisor(BaseSupervisor):
    """
    Manages backup, restore, watchdog, and cost projection agents.

    AGENTS MANAGED:
        BackupAgent           — Automated Google Drive backups
        WatchdogAgent         — Monitors the monitors
        CostProjectionAgent   — Forward-looking INR estimates

    SCHEDULE:
        Every 6 hours: KnowledgeGraph backup
        Daily:         ChromaDB + SQLite backup
        Daily:         Cost projection update
        Continuous:    Watchdog heartbeat monitoring
        Weekly:        Backup integrity verification

    BUDGET: ₹0 — all operations are local/Google Drive free tier
    PRIORITY: P0 — critical infrastructure, always active

    NEVER ENTERS DEGRADED_MODE.
    Cannot be paused by admin (safety invariant).
    """
    name = "DisasterRecoverySupervisor"
    domain = "infrastructure"

    BACKUP_SCHEDULE = {
        "knowledge_graph": {"interval_hours": 6, "target": "gdrive/kg/"},
        "chromadb": {"interval_hours": 24, "target": "gdrive/chromadb/"},
        "sqlite": {"interval_hours": 24, "target": "gdrive/sqlite/"},
        "config": {"interval_hours": 168, "target": "gdrive/config/"},  # Weekly
    }

    async def verify_backups(self) -> dict:
        """Weekly backup integrity check."""
        results = {}
        for target, config in self.BACKUP_SCHEDULE.items():
            latest_backup = await self._get_latest_backup(config["target"])
            age_hours = (datetime.utcnow() - latest_backup.timestamp).hours
            results[target] = {
                "status": "OK" if age_hours <= config["interval_hours"] * 1.5 else "STALE",
                "age_hours": age_hours,
                "size_mb": latest_backup.size_mb,
            }
        return results
```

---

## Upgraded Orchestrator — SwarmMaster v10

### What Changed from v9

```diff
  SwarmMaster v9:
    ├── MoE Gating Network
    ├── Task Decomposer
    ├── Dependency Resolver
    ├── Budget Manager (INR)
    ├── Session Coordinator (6 slots)
    ├── PipelineRectifier
    ├── RoutingAdvisor
    ├── ColdStartGuard
    └── BackpressureController

  SwarmMaster v10 ADDITIONS:
+   ├── InternalCircuitBreakerRegistry  ← NEW: tracks all internal breakers
+   ├── CostProjectionIntegration       ← NEW: proactive budget management
+   ├── LoopholeEventConsumer            ← NEW: listens for audit findings
+   ├── WatchdogRegistration             ← NEW: reports heartbeat to WatchdogAgent
+   ├── MoAFallbackIntegration           ← NEW: uses fallback chain on MoA failure
+   ├── SchemaVersionManager             ← NEW: handles schema migrations
+   └── EnhancedDegradedMode             ← NEW: auto-recovery timers
```

### SwarmMaster v10 Enhanced Routing Table

```python
class MoEGatingNetworkV10(MoEGatingNetwork):
    """v10 extends routing table with new task types."""

    ROUTING_TABLE_V10_ADDITIONS = {
        # New task types for v10 agents/workers
        "CHANNEL_FINGERPRINT":  ("IngestSupervisor",         0, False),
        "INPUT_SANITISE":       ("InfraSupervisor",          0, False),
        "COST_PROJECT":         ("DisasterRecoverySupervisor", 0, False),
        "TWEET_POST":           ("MarketingSupervisor",      0, False),
        "TWEET_ENGAGEMENT":     ("MarketingSupervisor",      0, False),
        "NEWSLETTER_SEND":      ("MarketingSupervisor",      0, False),
        "SBOM_GENERATE":        ("TechSupervisor",           0, False),
        "BACKUP_RUN":           ("DisasterRecoverySupervisor", 0, False),
        "LOOPHOLE_CHECK":       ("LoopholeHunterSupervisor", 0, False),
        "OVERRIDE_AUDIT":       ("LoopholeHunterSupervisor", 0, False),
        "PEN_TEST":             ("LoopholeHunterSupervisor", 0, False),
        "SUMMARY_VERIFY":       ("QualitySupervisor",        2, False),
        "SOURCE_CLUSTER":       ("IntelSupervisor",          1, True),
        "CONTENT_DEDUP":        ("MarketingSupervisor",      0, False),
        "KG_CANARY":            ("InfraSupervisor",          0, False),
        "SCHEMA_MIGRATE":       ("InfraSupervisor",          0, False),
    }
```

### Enhanced DEGRADED_MODE with Auto-Recovery

```python
class EnhancedDegradedMode:
    """
    v10 adds auto-recovery timers to DEGRADED_MODE.

    v9:  DEGRADED_MODE requires manual release (admin CLI).
    v10: Levels 1-2 have auto-recovery. Levels 3-4 still manual.

    AUTO-RECOVERY RULES:
        Level 1 (budget warning):
            → Auto-recover at next hour if budget resets
            → Timer: 60 minutes

        Level 2 (API failures):
            → Auto-recover when HealthCheck reports APIs healthy
            → Timer: 30 minutes between HALF_OPEN probes

        Level 3 (hardware offline):
            → MANUAL ONLY — admin must release
            → Reason: hardware may need physical intervention

        Level 4 (emergency):
            → MANUAL ONLY — admin must release
            → Reason: emergency may have external cause
    """

    AUTO_RECOVERY = {
        1: {"timer_min": 60, "auto": True, "condition": "budget_resets"},
        2: {"timer_min": 30, "auto": True, "condition": "apis_healthy"},
        3: {"timer_min": None, "auto": False, "condition": "admin_release"},
        4: {"timer_min": None, "auto": False, "condition": "admin_release"},
    }
```

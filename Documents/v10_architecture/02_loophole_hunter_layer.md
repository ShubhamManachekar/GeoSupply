# Chapter 2: LoopholeHunter — Cross-Layer Continuous Audit Engine

## Design Philosophy

> **v9 found loopholes at design time. v10 hunts them CONTINUOUSLY in production.**
> The LoopholeHunter is not a layer — it's a **cross-cutting sentinel** that watches every layer for logic gaps, security holes, data flow anomalies, and oversight failures.

---

## LoopholeHunter Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  LOOPHOLE HUNTER ENGINE (v10)                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              LoopholeHunterSupervisor                     │   │
│  │  Schedules all audit agents, collects findings,           │   │
│  │  generates weekly LoopholeReport                          │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────┐  ┌────────┴───────┐  ┌────────────────────┐    │
│  │ Loophole   │  │ Override       │  │ PenTest            │    │
│  │ Hunter     │  │ Audit          │  │ Agent              │    │
│  │ Agent      │  │ Agent          │  │                    │    │
│  └──────┬─────┘  └────────┬───────┘  └──────────┬─────────┘    │
│         │                  │                      │              │
│  ┌──────┴─────┐  ┌────────┴───────┐  ┌──────────┴─────────┐    │
│  │ Loophole   │  │ Override       │  │ Penetration        │    │
│  │ Detection  │  │ Pattern        │  │ Test               │    │
│  │ Worker     │  │ SubAgent       │  │ SubAgent           │    │
│  └────────────┘  └────────────────┘  └────────────────────┘    │
│                                                                  │
│  Subscribes to ALL EventBus topics                               │
│  Has READ access to ALL agent states                             │
│  Cannot MODIFY anything — report only                            │
│  Findings go to Admin CLI/Portal alerts                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## LoopholeHunterAgent

```python
class LoopholeHunterAgent(BaseAgent):
    """
    Continuous architecture audit engine. Runs 24 checks
    across all 7 layers every pipeline cycle.

    THIS AGENT IS READ-ONLY. It cannot modify state.
    It can only REPORT findings.

    CHECK CATEGORIES:
        LOGIC CHECKS      — data flow correctness
        SECURITY CHECKS    — injection, leakage, access
        CONSISTENCY CHECKS — schema compliance, contract violations
        PERFORMANCE CHECKS — latency regressions, cost spikes
        OVERSIGHT CHECKS   — monitoring gaps, backup freshness

    SCHEDULE:
        Per pipeline run:  ALL 24 checks
        Daily:             Summary report
        Weekly:            Deep audit with trend analysis
    """
    name = "LoopholeHunterAgent"
    domain = "audit"

    CHECKS = [
        # ── LOGIC CHECKS ─────────────────────────────────
        {
            "id": "LOGIC-001",
            "name": "Knowledge Graph Write Ordering",
            "check": "Verify KG write-buffer queue is processing in order",
            "severity": "HIGH",
            "layer": "worker",
            "fix_ref": "v9 GAP 1",
        },
        {
            "id": "LOGIC-002",
            "name": "MoA Proposer Output Preservation",
            "check": "Verify all 3 MoA proposals are saved before aggregation",
            "severity": "HIGH",
            "layer": "subagent",
            "fix_ref": "v9 GAP 5",
        },
        {
            "id": "LOGIC-003",
            "name": "Source Penalty Escalation",
            "check": "Verify escalating penalties (1st=-0.05, 2nd=-0.10, 3rd=-0.20)",
            "severity": "MEDIUM",
            "layer": "subagent",
            "fix_ref": "v9 GAP 3",
        },
        {
            "id": "LOGIC-004",
            "name": "Summarization Semantic Preservation",
            "check": "Verify tweets don't flip meaning of underlying data",
            "severity": "HIGH",
            "layer": "agent",
            "fix_ref": "v9 GAP 2",
        },
        {
            "id": "LOGIC-005",
            "name": "Internal Circuit Breaker Status",
            "check": "All Tier-3 agent calls have circuit breakers, none stuck OPEN",
            "severity": "CRITICAL",
            "layer": "agent",
            "fix_ref": "v9 GAP 4",
        },
        {
            "id": "LOGIC-006",
            "name": "Budget Waterfall Integrity",
            "check": "Sum of supervisor budgets <= global budget",
            "severity": "HIGH",
            "layer": "supervisor",
        },
        {
            "id": "LOGIC-007",
            "name": "Task Dependency Acyclicity",
            "check": "TaskDecomposer never produces circular dependencies",
            "severity": "CRITICAL",
            "layer": "orchestrator",
        },
        {
            "id": "LOGIC-008",
            "name": "Phase Gate Integrity",
            "check": "No phase N+1 work started before phase N complete",
            "severity": "HIGH",
            "layer": "supervisor",
        },

        # ── SECURITY CHECKS ──────────────────────────────
        {
            "id": "SEC-001",
            "name": "Prompt Injection Scan",
            "check": "All ingested text passed through InputGuardAgent",
            "severity": "CRITICAL",
            "layer": "worker",
        },
        {
            "id": "SEC-002",
            "name": "API Key Exposure",
            "check": "No API keys in logs, error messages, or agent outputs",
            "severity": "CRITICAL",
            "layer": "all",
        },
        {
            "id": "SEC-003",
            "name": "Telegram Channel Fingerprint",
            "check": "All ingested channels match baseline fingerprint",
            "severity": "HIGH",
            "layer": "worker",
            "fix_ref": "v9 LOOPHOLE 1",
        },
        {
            "id": "SEC-004",
            "name": "STATIC Decoder Input Length",
            "check": "No Tier-1 input exceeds 2048 tokens",
            "severity": "HIGH",
            "layer": "worker",
            "fix_ref": "v9 LOOPHOLE 2",
        },
        {
            "id": "SEC-005",
            "name": "Admin CLI Auth",
            "check": "No failed auth >3 times without lockout triggered",
            "severity": "MEDIUM",
            "layer": "admin",
            "fix_ref": "v9 LOOPHOLE 3",
        },
        {
            "id": "SEC-006",
            "name": "Message Contract Validation",
            "check": "No inter-agent messages violating AgentMessage schema",
            "severity": "MEDIUM",
            "layer": "all",
        },

        # ── CONSISTENCY CHECKS ────────────────────────────
        {
            "id": "CON-001",
            "name": "Schema Version Consistency",
            "check": "All agents use same Pydantic schema version",
            "severity": "MEDIUM",
            "layer": "all",
        },
        {
            "id": "CON-002",
            "name": "GeoRiskScore CI Propagation",
            "check": "Every GeoRiskScore has ci_low, ci_high, data_density",
            "severity": "HIGH",
            "layer": "worker",
        },
        {
            "id": "CON-003",
            "name": "INR Cost Attribution",
            "check": "Every span in trace has cost_inr >= 0 and in INR",
            "severity": "MEDIUM",
            "layer": "all",
        },
        {
            "id": "CON-004",
            "name": "Hallucination Floor Integrity",
            "check": "No output published with confidence < 0.70",
            "severity": "CRITICAL",
            "layer": "agent",
        },

        # ── PERFORMANCE CHECKS ────────────────────────────
        {
            "id": "PERF-001",
            "name": "Pipeline SLA",
            "check": "Full pipeline completes in <12 minutes",
            "severity": "MEDIUM",
            "layer": "orchestrator",
        },
        {
            "id": "PERF-002",
            "name": "Cost Spike Detection",
            "check": "No single pipeline run costs >₹50 INR",
            "severity": "HIGH",
            "layer": "orchestrator",
        },

        # ── OVERSIGHT CHECKS ─────────────────────────────
        {
            "id": "OVS-001",
            "name": "Watchdog Heartbeat",
            "check": "HealthCheckAgent has logged in last 5 minutes",
            "severity": "CRITICAL",
            "layer": "infrastructure",
            "fix_ref": "v9 BLIND SPOT 1",
        },
        {
            "id": "OVS-002",
            "name": "Knowledge Graph Backup Freshness",
            "check": "Last KG snapshot < 6 hours old",
            "severity": "HIGH",
            "layer": "agent",
            "fix_ref": "v9 BLIND SPOT 2",
        },
        {
            "id": "OVS-003",
            "name": "Override Frequency Audit",
            "check": "No admin has >5 overrides this week without review",
            "severity": "MEDIUM",
            "layer": "admin",
            "fix_ref": "v9 GAP 6",
        },
        {
            "id": "OVS-004",
            "name": "Marketing Kill Switch Ready",
            "check": "Marketing halt command operational and tested",
            "severity": "MEDIUM",
            "layer": "marketing",
            "fix_ref": "v9 BLIND SPOT 3",
        },
    ]

    async def run_all_checks(self) -> 'LoopholeReport':
        """Run all 24 checks and generate report."""
        findings = []
        for check in self.CHECKS:
            result = await self._execute_check(check)
            if not result.passed:
                findings.append(LoopholeFinding(
                    check_id=check["id"],
                    name=check["name"],
                    severity=check["severity"],
                    layer=check["layer"],
                    details=result.details,
                    recommendation=result.recommendation,
                ))

        return LoopholeReport(
            timestamp=datetime.utcnow(),
            total_checks=len(self.CHECKS),
            passed=len(self.CHECKS) - len(findings),
            failed=len(findings),
            findings=findings,
            critical_findings=[f for f in findings if f.severity == "CRITICAL"],
        )
```

---

## LoopholeReport Schema

```python
class LoopholeFinding(BaseModel):
    check_id: str           # e.g. "LOGIC-001"
    name: str               # Human-readable name
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    layer: str              # Which layer the issue is in
    details: str            # What went wrong
    recommendation: str     # How to fix it
    first_detected: datetime
    still_open: bool = True
    override_approved: bool = False  # Admin acknowledged and accepted risk

class LoopholeReport(BaseModel):
    timestamp: datetime
    total_checks: int
    passed: int
    failed: int
    findings: list[LoopholeFinding]
    critical_findings: list[LoopholeFinding]
    trend: Literal["improving", "stable", "degrading"] = "stable"

    @property
    def health_score(self) -> float:
        """0.0 = all checks failed, 1.0 = all passed."""
        return self.passed / self.total_checks if self.total_checks > 0 else 0.0
```

---

## Integration with Admin CLI/Portal

```
CLI Commands:
    geosupply loophole run        → run all 24 checks now
    geosupply loophole report     → last report summary
    geosupply loophole findings   → all open findings
    geosupply loophole history    → trend over last 30 days
    geosupply loophole accept <id>→ admin accepts risk for finding

Dashboard (Portal Page 12):
    - Check status grid (green/yellow/red per check)
    - Finding timeline (when did issues appear/resolve)
    - Layer health heatmap
    - Trend charts (improving/degrading over weeks)
```

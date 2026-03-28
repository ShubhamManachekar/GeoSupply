---
name: loophole-hunter
description: LoopholeHunter agent implementation — continuous security audit patterns, finding schema, pen-test automation, override monitoring, and Layer 7 integration for GeoSupply's cross-cutting security layer.
---

# LoopholeHunter — Layer 7 Continuous Security

> Custom GeoSupply skill — v10 architecture security audit agent

## LoopholeHunter Architecture

```
Layer 7 (Cross-cutting) — runs continuously, never on critical path
  ├── LoopholeHunterAgent      ← Central audit coordinator
  ├── PenTestAgent             ← Executes 8 automated pen test vectors
  ├── OverrideAuditAgent       ← Monitors Layer-0 manual overrides
  └── LoopholeFinding (Schema) ← Structured finding reports
```

**Key property**: LoopholeHunter NEVER blocks the pipeline. It observes, audits, and fires findings asynchronously. Hard blocks are only possible through BudgetManagerAgent (budget exhaustion) and SecurityAgent (key revocation).

---

## 1. Continuous Audit Loop

```python
class LoopholeHunterAgent(BaseAgent):
    name = "loophole_hunter"
    tier = LLMTier.LARGE_20B
    on_critical_path = False

    AUDIT_INTERVAL_SECONDS = 300   # Run full audit every 5 minutes

    async def setup(self) -> None:
        await super().setup()
        self._audit_task = asyncio.create_task(self._continuous_audit_loop())

    async def _continuous_audit_loop(self) -> None:
        while True:
            try:
                await self._run_all_audit_checks()
            except Exception as exc:
                logger.error("LoopholeHunter audit failed: %s", exc)
            await asyncio.sleep(self.AUDIT_INTERVAL_SECONDS)

    async def _run_all_audit_checks(self) -> None:
        checks = [
            self._check_hardcoded_secrets(),
            self._check_event_signatures(),
            self._check_budget_compliance(),
            self._check_hallucination_floor(),
            self._check_lateral_communication(),
            self._check_override_patterns(),
            self._check_state_machine_integrity(),
            self._check_schema_version_compliance(),
        ]
        findings = await asyncio.gather(*checks, return_exceptions=True)
        for finding in findings:
            if isinstance(finding, LoopholeFinding):
                await self._publish_finding(finding)
```

---

## 2. Finding Severity Matrix

```python
SEVERITY_MATRIX = {
    # CRITICAL — immediate action required, alert CTO
    "hardcoded_api_key":          "CRITICAL",
    "unsigned_event_accepted":    "CRITICAL",
    "hallucination_floor_breach": "CRITICAL",
    "budget_cap_bypass":          "CRITICAL",

    # HIGH — fix before next deployment
    "lateral_communication":      "HIGH",
    "schema_version_missing":     "HIGH",
    "state_machine_bypass":       "HIGH",
    "unaudited_override":         "HIGH",

    # MEDIUM — fix within 1 week
    "deprecated_datetime_utcnow": "MEDIUM",
    "bare_exception_swallow":     "MEDIUM",
    "missing_cost_tracking":      "MEDIUM",
    "breaker_not_applied":        "MEDIUM",

    # LOW — fix at next convenient time
    "missing_docstring":          "LOW",
    "test_coverage_below_85pct":  "LOW",
    "outdated_schema_version":    "LOW",
}
```

---

## 3. Static Code Audit (Runs at Startup)

```python
async def _check_hardcoded_secrets(self) -> LoopholeFinding | None:
    """Scan source tree for hardcoded API keys."""
    import ast, pathlib

    SECRET_PATTERNS = [
        r'["\']sk-[a-zA-Z0-9]{32,}["\']',      # OpenAI-style
        r'["\']Bearer [a-zA-Z0-9]{20,}["\']',   # Bearer tokens
        r'api_key\s*=\s*["\'][^"\']{10,}["\']', # Generic api_key assignments
        r'password\s*=\s*["\'][^"\']{6,}["\']', # Passwords
        r'secret\s*=\s*["\'][^"\']{10,}["\']',  # Secrets
    ]

    src_root = pathlib.Path("src/geosupply")
    for py_file in src_root.rglob("*.py"):
        content = py_file.read_text()
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, content):
                return LoopholeFinding(
                    severity="CRITICAL",
                    vector="PT-01",
                    component=str(py_file),
                    description=f"Hardcoded secret pattern found: {pattern}",
                    remediation="Use SecurityAgent.get_key() instead",
                    ...
                )
    return None
```

---

## 4. Runtime Override Monitoring (OverrideAuditAgent)

```python
class OverrideAuditAgent(BaseAgent):
    """Monitors Layer-0 manual overrides for abuse patterns."""
    name = "override_audit"
    tier = LLMTier.CPU_ONLY   # Pure logic, no LLM needed
    on_critical_path = False

    OVERRIDE_FREQUENCY_THRESHOLD = 10   # Overrides per hour → alert
    OVERRIDE_CRITICAL_ACTIONS = [       # These always get HMAC-verified
        "force_approve_spend",
        "lower_hallucination_floor",
        "disable_circuit_breaker",
        "bypass_input_sanitiser",
    ]

    async def _check_override_patterns(self) -> LoopholeFinding | None:
        recent = await self._get_recent_overrides(window_hours=1)
        if len(recent) > self.OVERRIDE_FREQUENCY_THRESHOLD:
            return LoopholeFinding(
                severity="HIGH",
                vector="PT-08",
                component="override_audit",
                description=f"Unusual override frequency: {len(recent)}/hour",
                remediation="Review override logs and verify admin intent",
                ...
            )
        # Check HMAC integrity of each override record
        for record in recent:
            if not self._verify_hmac(record):
                return LoopholeFinding(severity="CRITICAL", vector="PT-08", ...)
        return None
```

---

## 5. LoopholeReport (Weekly Aggregation)

```python
# Schema #17: LoopholeReport — weekly summary for admin review
class LoopholeReport(BaseModel):
    schema_version: int = 1
    report_id: str
    period_start: datetime
    period_end: datetime
    total_findings: int
    by_severity: dict[str, int]   # {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 3, "LOW": 8}
    by_vector: dict[str, int]     # {"PT-01": 0, "PT-02": 1, ...}
    resolved_findings: int
    open_findings: int
    security_score: float         # 0.0–10.0 (10 = perfect)
    top_risks: list[LoopholeFinding]
    recommendations: list[str]
    generated_at: datetime
```

---

## 6. Logic Gap Checks (24 Audit Checks)

The existing `cli/audit.py` runs these. LoopholeHunter extends them at runtime:

```python
RUNTIME_CHECKS = [
    # Structural checks (static — run at startup)
    "C01: All BaseWorker subclasses override process()",
    "C02: All BaseAgent subclasses have _VALID_TRANSITIONS",
    "C03: All schemas in ALL_SCHEMAS have SCHEMA_VERSIONS entry",
    "C04: No worker-to-worker direct method calls",

    # Behavioral checks (dynamic — run continuously)
    "C05: EventBus rejects unsigned messages",
    "C06: BudgetManager blocks at BUDGET_CAP_INR",
    "C07: HALLUCINATION_FLOOR = 0.70 (cannot be changed at runtime)",
    "C08: All costs returned as cost_inr (never usd)",
    "C09: No datetime.utcnow() in any executed code path",
    "C10: SecurityAgent.get_key() called for all API access",

    # Override checks (event-driven — run on each override)
    "C11: All Layer-0 overrides logged to OverrideRecord",
    "C12: OverrideRecord HMAC matches SecurityAgent signing key",
    "C13: No critical action override without admin JWT scope",
    "C14: Override frequency within normal bounds",
]
```

---

## 7. LoopholeHunter Test Coverage Requirements

```python
# Required tests for LoopholeHunterAgent:
# - test_detects_hardcoded_secret_in_dummy_file()
# - test_rejects_unsigned_event()
# - test_flags_budget_cap_bypass_attempt()
# - test_detects_override_frequency_spike()
# - test_verifies_override_record_hmac()
# - test_generates_weekly_report_with_correct_schema()
# - test_continuous_loop_survives_check_exception()
# - test_finding_published_to_eventbus_on_critical()
```

---

## Related Skills
- `security-auditor` — Upstream security patterns and PT vectors
- `agent-designer` — LoopholeHunter inherits from BaseAgent
- `phase-gate-auditor` — Security gate checks before phase closure
- `geosupply-dev` — Core security rules enforced by LoopholeHunter

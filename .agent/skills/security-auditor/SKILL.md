---
name: security-auditor
description: Security scanning, penetration testing, and LoopholeHunter agent patterns for GeoSupply. Covers API key exposure, unsigned event injection, schema bypass, budget evasion, and override tampering — aligned to FA v3 v10 security architecture.
---

# Security Auditor — GeoSupply LoopholeHunter Edition

> Upstream source: alirezarezvani/claude-skills · engineering (security domain)
> Adapted for: GeoSupply FA v3 v10, LoopholeHunterAgent, 8 pen-test vectors, HMAC-SHA256 EventBus

## GeoSupply Security Architecture

```
SecurityAgent     ← API key vault (HMAC-SHA256 per-agent signing keys)
LoopholeHunter    ← Continuous audit agent (Layer 7, cross-cutting)
OverrideAuditAgent← Logs all manual Layer-0 overrides
PenTestAgent      ← Executes 8 registered penetration test scenarios
InputSanitiser    ← First-line defense at all ingestion entry points
```

**Security Principle**: TRUST NOTHING. Every data flow has a validator.

---

## 1. The 8 Penetration Test Vectors (v10)

### PT-01: API Key Exposure
```python
# Test: Scan all source files for hardcoded secrets
# Expected: Zero matches for patterns: sk-, Bearer, api_key=, password=
# Fail condition: Any key found outside SecurityAgent vault
import re
PATTERNS = [r'sk-[a-zA-Z0-9]{32,}', r'Bearer [a-zA-Z0-9]{20,}',
            r'api_key\s*=\s*["\'][^"\']{10,}', r'password\s*=\s*["\'][^"\']{6,}']
```

### PT-02: Unsigned Event Injection
```python
# Test: Publish event to EventBus WITHOUT valid HMAC signature
# Expected: EventBus rejects event, publishes security alert
# Fail condition: Unsigned event is processed by any subscriber
msg_tampered = AgentMessage(..., signature=b"invalid_sig")
result = await event_bus.publish(channel="intel", message=msg_tampered)
assert result.rejected == True
```

### PT-03: Schema Version Bypass
```python
# Test: Submit AgentMessage with schema_version=0 (invalid)
# Expected: Pydantic validation raises ValidationError before processing
# Fail condition: Message with schema_version < 1 is processed
with pytest.raises(ValidationError):
    AgentMessage(schema_version=0, ...)
```

### PT-04: Budget Cap Evasion
```python
# Test: Attempt to process tasks after BUDGET_CAP_INR (₹500) is exhausted
# Expected: BudgetManagerAgent blocks all Tier-3 calls
# Fail condition: Any LLM call succeeds when budget = 0
budget_agent._remaining_inr = 0.0
result = await budget_agent.execute("approve_spend", {"amount_inr": 1.0})
assert result["approved"] == False
```

### PT-05: Hallucination Threshold Lowering
```python
# Test: Attempt to set HALLUCINATION_FLOOR < 0.70 via config override
# Expected: Config validation rejects value; floor remains 0.70
# Fail condition: Any generation proceeds with confidence < 0.70
with pytest.raises(ValueError, match="HALLUCINATION_FLOOR cannot be lowered"):
    override_config(HALLUCINATION_FLOOR=0.50)
```

### PT-06: State Machine Transition Violation
```python
# Test: Force agent from IDLE → DONE (skipping BUSY)
# Expected: InvalidStateTransition exception raised
# Fail condition: Agent accepts illegal transition
agent._state = AgentState.IDLE
with pytest.raises(InvalidStateTransition):
    await agent._transition(AgentState.DONE)
```

### PT-07: Worker Process Isolation
```python
# Test: Worker A attempts to call Worker B directly (lateral communication)
# Expected: No route exists; EventBus routing table rejects peer-to-peer
# Fail condition: Worker message reaches another worker without supervisor mediation
```

### PT-08: Override Tampering
```python
# Test: Modify OverrideRecord after it has been logged
# Expected: HMAC signature mismatch detected; tamper alert published
# Fail condition: Modified override record passes validation
```

---

## 2. LoopholeHunter Agent Implementation Pattern

```python
class LoopholeHunterAgent(BaseAgent):
    """Continuous security audit agent — Layer 7, cross-cutting."""
    name = "loophole_hunter"
    tier = LLMTier.LARGE_20B  # Needs reasoning for vulnerability analysis
    on_critical_path = False   # Never blocks pipeline

    async def execute(self, action: str, payload: dict) -> dict:
        handlers = {
            "scan_secrets":       self._scan_hardcoded_secrets,
            "audit_signatures":   self._audit_event_signatures,
            "check_budget_floor": self._check_budget_compliance,
            "review_overrides":   self._review_override_patterns,
            "run_pentest":        self._run_pentest_suite,
        }
        if action not in handlers:
            return {"error": f"Unknown action: {action}", "meta": {"cost_inr": 0.0}}
        finding = await handlers[action](payload)
        if finding:
            await self._publish_loophole_finding(finding)
        return {"result": finding, "meta": {"cost_inr": self._last_cost}}

    async def _publish_loophole_finding(self, finding: LoopholeFinding) -> None:
        await self.event_bus.publish("security.findings", AgentMessage(
            sender_id=self.id,
            recipient_id="security_supervisor",
            payload=finding.model_dump(),
            trace_id=generate_trace_id(),
        ))
```

---

## 3. Input Sanitization Rules (InputSanitiserWorker)

```python
SANITIZATION_RULES = {
    "max_text_length":      10_000,     # chars
    "allowed_languages":    ["en", "hi", "ur", "ta", "te", "bn", "ar", "zh"],
    "block_patterns":       [r"<script", r"javascript:", r"--", r"'; DROP"],
    "entity_allow_list":    None,       # All entities allowed (KG will filter)
    "min_credibility_score": 0.20,      # Block sources below floor
    "require_source_id":    True,       # Every message must have traceable source
}
```

---

## 4. Key Rotation Schedule

```python
# SecurityAgent key rotation (HMAC signing keys)
KEY_ROTATION_DAYS = 30
GRACE_WINDOW_DAYS = 2   # Old key still valid for 2 days post-rotation

# JWT token expiry
PORTAL_SESSION_TTL = 3600       # 1 hour
PORTAL_REFRESH_TTL = 86400      # 24 hours (refresh token)
API_KEY_TTL = 2592000           # 30 days

# Backup encryption
BACKUP_ALGORITHM = "AES-256-GCM"
BACKUP_KEY_ROTATION = 90        # days
```

---

## 5. Audit Checklist (Run Before Every Phase Gate)

```markdown
## Security Audit Checklist
- [ ] PT-01: Zero hardcoded secrets in codebase (grep scan)
- [ ] PT-02: All EventBus messages have valid HMAC signatures
- [ ] PT-03: All schemas reject schema_version < 1
- [ ] PT-04: BudgetManager blocks calls at cap
- [ ] PT-05: HALLUCINATION_FLOOR cannot be lowered below 0.70
- [ ] PT-06: All agent state machines reject illegal transitions
- [ ] PT-07: No worker-to-worker direct communication exists
- [ ] PT-08: Override records detect tampering
- [ ] InputSanitiserWorker active on all ingestion workers
- [ ] SecurityAgent.get_key() used for ALL API key access
- [ ] No raw exception swallowing (bare `except: pass`)
- [ ] All API calls wrapped with @breaker decorator
```

---

## 6. LoopholeFinding Schema Reference

```python
# Schema #16 (schemas.py)
class LoopholeFinding(BaseModel):
    schema_version: int = 1
    finding_id: str           # UUID
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    vector: str               # PT-01 through PT-08
    component: str            # Which agent/worker/schema
    description: str
    evidence: dict            # Specific proof/artifact
    remediation: str          # How to fix
    detected_at: datetime
    trace_id: str
```

---

## Related Skills
- `loophole-hunter` — Full LoopholeHunter agent development patterns
- `agent-designer` — Security agent archetype and patterns
- `phase-gate-auditor` — Security checks integrated into phase gates
- `geosupply-dev` — General development security rules

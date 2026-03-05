# Part VIII: Security — Hardening, LoopholeHunter, Penetration Testing
## FA v1 | Gap Mitigations: G3 applied

## 8.1 Security Principles

```
1. Defence in depth — multiple layers, no single point of failure
2. Least privilege — agents only access what they need
3. Fail secure — on error, quarantine (don't publish)
4. Audit everything — every action logged to Supabase
5. Rotate regularly — API keys every 30 days
6. Trust nothing — verify every input, output, and agent message
```

---

## 8.2 LoopholeHunter — 24 Continuous Audit Checks

| ID | Check | Severity | Layer | Category |
|----|-------|----------|-------|----------|
| LOGIC-001 | KG write-buffer queue ordering | HIGH | Worker | Logic |
| LOGIC-002 | MoA proposals saved before aggregation | HIGH | SubAgent | Logic |
| LOGIC-003 | Source penalty escalation applied | MEDIUM | SubAgent | Logic |
| LOGIC-004 | Summary semantic preservation | HIGH | Agent | Logic |
| LOGIC-005 | Internal circuit breaker states | CRITICAL | Agent | Logic |
| LOGIC-006 | Budget waterfall integrity | HIGH | Supervisor | Logic |
| LOGIC-007 | Task dependency acyclicity | CRITICAL | Orchestrator | Logic |
| LOGIC-008 | Phase gate integrity | HIGH | Supervisor | Logic |
| SEC-001 | Prompt injection scan coverage | CRITICAL | Worker | Security |
| SEC-002 | API key exposure check | CRITICAL | All | Security |
| SEC-003 | Telegram channel fingerprint | HIGH | Worker | Security |
| SEC-004 | STATIC decoder input length | HIGH | Worker | Security |
| SEC-005 | Admin CLI auth lockout | MEDIUM | Admin | Security |
| SEC-006 | Message contract validation | MEDIUM | All | Security |
| CON-001 | Schema version consistency | MEDIUM | All | Consistency |
| CON-002 | GeoRiskScore CI propagation | HIGH | Worker | Consistency |
| CON-003 | INR cost attribution (every span) | MEDIUM | All | Consistency |
| CON-004 | Hallucination floor 0.70 | CRITICAL | Agent | Consistency |
| PERF-001 | Pipeline SLA (<12 min) | MEDIUM | Orchestrator | Performance |
| PERF-002 | Cost spike detection (>₹50/run) | HIGH | Orchestrator | Performance |
| OVS-001 | Watchdog heartbeat (HealthCheck) | CRITICAL | Infrastructure | Oversight |
| OVS-002 | KG backup freshness (<6hr) | HIGH | Agent | Oversight |
| OVS-003 | Override frequency audit | MEDIUM | Admin | Oversight |
| OVS-004 | Marketing kill switch operational | MEDIUM | Marketing | Oversight |

---

## 8.3 All Security Loopholes — Found & Fixed

### 3 from v9 Audit

| # | Loophole | Fix | Check ID |
|---|----------|-----|----------|
| 1 | Telegram channel poisoning | ChannelFingerprintWorker KL divergence | SEC-003 |
| 2 | STATIC decoder prompt length bypass | InputSanitiserWorker 2048 token limit | SEC-004 |
| 3 | Admin CLI brute force | Rate limit 5→lockout + TOTP for overrides | SEC-005 |

### 8 NEW from v10 Deep Audit

| # | Loophole | Fix |
|---|----------|-----|
| 4 | EventBus events not authenticated | Event signing with per-agent key |
| 5 | Groq API key shared across workers | Short-lived proxy tokens (1hr, scoped) |
| 6 | ChromaDB reads not audited | Read audit middleware (who read what) |
| 7 | KG entity injection (fake countries) | Verification against ISO/MCA/LOCODE |
| 8 | No tweet content signing | Hash in thread footer, verifiable on dashboard |
| 9 | Dashboard WebSocket no auth | JWT-authenticated WebSocket handshake (FA v1 G7) |
| 10 | Backup files not encrypted | AES-256 encryption before Google Drive upload |
| 11 | No admin portal session timeout | 15min idle lock, 30min expire, 5min for override page |

### FA v1: G3 FIX — EventBus Signing Key Management

```
EVENT SIGNING PROTOCOL:
    1. Each registered agent gets a unique signing key from SecurityAgent
       Key format: HMAC-SHA256, 256-bit, agent-scoped
    2. Event structure (signed):
       {
           topic: str,
           source: str,        # agent name
           payload: dict,
           timestamp: datetime,
           signature: str      # HMAC of (topic + source + payload_json + timestamp)
       }
    3. EventBus verifies signature on every publish()
       Invalid signature → reject + log SECURITY_EVENT + alert admin
    4. Key rotation: 30 days (matching API key rotation schedule)
       SecurityAgent.rotate_event_keys() → all agents get new keys
       Old keys valid for 60-second grace window during rotation
    5. Key storage: SecurityAgent vault (same as API keys)
       Never in env vars, never in logs, never in event payloads
```

---

## 8.4 Penetration Test Suite (8 Tests, Weekly)

| # | Test | What It Does | Expected Result |
|---|------|-------------|-----------------|
| 1 | Prompt injection | Feed injection payloads via TelegramWorker | InputGuardAgent catches ALL |
| 2 | Schema bypass | Send >2048 token to Tier-1 | InputSanitiserWorker truncates |
| 3 | Source gaming | Simulate 4 quarantines same source | Permanent flag applied |
| 4 | Key leakage | Grep all logs for API key patterns | Zero matches |
| 5 | CLI brute force | 6 wrong passwords | Lockout activates |
| 6 | Contract violation | Malformed AgentMessage | Rejected by schema |
| 7 | ChromaDB bypass | Direct write without RAGManager | Single-writer blocks |
| 8 | Rate limit flood | Flood ingestion endpoint | Circuit breaker opens |

---

## 8.5 STATIC Decoder Security

```
PURPOSE:
    STATIC (Schema-Typed Allocation and Token Inference Codec)
    constrains LLM output at decode time to valid Pydantic schemas.
    CSR sparse matrix precomputes valid token transitions.
    
    RESULT: LLM CANNOT output non-schema-conforming JSON.
    No post-processing needed. Schema compliance guaranteed.

PROTECTED WORKERS (Tier-1):
    SentimentWorker, NERWorker, ClaimWorker, SourceCredWorker,
    CyberThreatWorker, SupplierWorker, SanctionsWorker

INPUT GUARD (v10):
    InputSanitiserWorker enforces 2048 token limit on all Tier-1 inputs.
    Prevents context window overflow that could bypass schema constraints.
```

## CROSS-CHECK ✅
```
✓ All 24 LoopholeHunter checks listed with IDs
✓ All 11 security loopholes (3 v9 + 8 v10) documented with fixes
✓ All 8 penetration tests documented and scheduled
✓ STATIC decoder explained with input guard (v10)
✓ Event signing, proxy tokens, backup encryption all documented
✓ Session timeout, TOTP, rate limiting all documented
✓ [FA v1] EventBus signing key rotation protocol specified (G3)
```

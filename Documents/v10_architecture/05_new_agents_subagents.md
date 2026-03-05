# Chapter 5: 12 New Agents + 5 New SubAgents

## New Agents in v10

v9: 26 agents → **v10: 38 agents (+12)**

---

### 1. LoopholeHunterAgent
- **Domain**: audit
- **Role**: Runs 24 continuous architecture checks (see Ch 2)
- **Fixes**: All v9 gaps proactively detected in production
- **Schedule**: Every pipeline run + daily summary + weekly deep audit

### 2. OverrideAuditAgent
- **Domain**: audit
- **Role**: Weekly analysis of admin override patterns
- **Fixes**: v9 GAP 6 (write-only audit log)
- **Checks**: Volume, patterns, time clustering, bypass rate

### 3. CostProjectionAgent
- **Domain**: infrastructure
- **Role**: Forward-looking INR cost projection from 7-day trend
- **Fixes**: v9 BLIND SPOT 5 (reactive-only budget tracking)
- **Alerts**: Projected monthly > ₹400 → WARN, > ₹450 → ALERT

### 4. WatchdogAgent
- **Domain**: infrastructure (singleton)
- **Role**: Monitors the monitors — ensures HealthCheckAgent is alive
- **Fixes**: v9 BLIND SPOT 1 (who monitors HealthCheckAgent?)
- **Mechanism**: If HealthCheck doesn't log for 5 min → restart it
- **Self-watching**: Separate lightweight process, not part of main swarm

```python
@singleton
class WatchdogAgent:
    """
    Runs as SEPARATE PROCESS from main swarm.
    Monitors HealthCheckAgent heartbeat.
    If heartbeat missing >5 min → restart HealthCheckAgent.
    If HealthCheck restart fails 3x → EMERGENCY ALERT.

    ALSO WATCHES:
        - LoopholeHunterAgent heartbeat (every 30 min)
        - EventBus queue depth (< 1000 events)
        - Main process memory usage (< 8GB)
        - Disk space (> 10GB free for ChromaDB)
    """
    HEARTBEAT_CHECKS = {
        "HealthCheckAgent": {"interval_min": 5, "max_restarts": 3},
        "LoopholeHunterAgent": {"interval_min": 30, "max_restarts": 2},
        "LoggingAgent": {"interval_min": 10, "max_restarts": 3},
    }
```

### 5. BackupAgent
- **Domain**: infrastructure (singleton)
- **Role**: Manages automated backups to Google Drive
- **Fixes**: v9 BLIND SPOT 4 (no disaster recovery)
- **RPO**: 6 hours (KG) / 24 hours (SQLite, ChromaDB)

### 6. InputGuardAgent
- **Domain**: infrastructure (singleton)
- **Role**: Pre-processing input sanitisation coordinator
- **Fixes**: v9 LOOPHOLE 2 (STATIC decoder prompt bypass)
- **Pipeline**: Token count → injection scan → unicode normalise → sanitise

### 7. ChannelVerificationAgent
- **Domain**: ingestion
- **Role**: Telegram/RSS channel integrity verification
- **Fixes**: v9 LOOPHOLE 1 (channel poisoning)
- **Mechanism**: Channel fingerprint baseline + drift detection

### 8. SummarizationAuditAgent
- **Domain**: marketing
- **Role**: Verifies marketing content accuracy against source data
- **Fixes**: v9 GAP 2 (summarisation distortion)
- **Pipeline**: Uses SummarizationVerifierSubAgent per content piece

### 9. SourceClusterAgent
- **Domain**: intelligence
- **Role**: Detects coordinated source networks
- **Fixes**: v9 GAP 3 (source gaming through cycling)
- **Mechanism**: Cluster by IP/domain/author/style embedding

### 10. PenTestAgent
- **Domain**: security
- **Role**: Automated penetration testing against the swarm
- **Schedule**: Weekly (Sunday, after all tests)

```python
class PenTestAgent(BaseAgent):
    """
    Automated penetration testing. Tries to BREAK the system intentionally.

    TESTS:
        1. Prompt injection via crafted articles
           → Feed injection payloads through TelegramWorker
           → Verify InputGuardAgent catches them ALL

        2. Schema bypass attempt
           → Send >2048 token input to Tier-1 worker
           → Verify InputSanitiserWorker truncates correctly

        3. Source credibility gaming
           → Simulate 4 quarantines for same source
           → Verify permanent flag is applied

        4. API key leakage check
           → Grep all log outputs for key patterns
           → Verify zero matches

        5. Admin CLI brute force
           → Send 6 wrong passwords
           → Verify lockout activates

        6. Message contract violation
           → Send malformed AgentMessage between agents
           → Verify rejection

        7. ChromaDB direct write attempt
           → Try to write without going through RAGManager
           → Verify single-writer authority blocks it

        8. Rate limit verification
           → Flood ingestion endpoint
           → Verify circuit breaker opens

    RESULTS: Weekly PenTestReport → admin portal
    """
    name = "PenTestAgent"
    domain = "security"
```

### 11. AnalyticsAgent
- **Domain**: marketing
- **Role**: Twitter engagement analytics + growth tracking
- **Tracks**: Impressions, likes, retweets, follower growth, content performance
- **Outputs**: Weekly analytics report + content strategy recommendations

### 12. NewsletterAgent
- **Domain**: marketing
- **Role**: Email newsletter creation + subscriber management
- **API**: SendGrid/Resend
- **Schedule**: Weekly digest (Monday), breaking alerts (immediate)

---

## 5 New SubAgents in v10

v9: 8 subagents → **v10: 13 subagents (+5)**

---

### 1. SummarizationVerifierSubAgent
- **Fixes**: v9 GAP 2
- **Pipeline**: Extract numerical claims → compare directional language → magnitude band check
- **Blocks**: Any tweet/summary that amplifies or diminishes underlying data

### 2. SourceClusterSubAgent
- **Fixes**: v9 GAP 3
- **Algorithm**: Source embedding → cosine similarity clustering → penalty propagation
- **Thresholds**: Cosine > 0.90 writing style = same cluster

### 3. OverridePatternSubAgent
- **Fixes**: v9 GAP 6
- **Patterns**: Volume spikes, source favouritism, time clustering, bypass rate
- **Output**: Findings list to OverrideAuditAgent

### 4. MoAFallbackSubAgent
- **Fixes**: v9 GAP 5
- **Chain**: GPT-OSS → Groq → Scoring → Manual
- **Invariant**: Proposals saved to SQLite BEFORE any aggregation attempt

### 5. PenetrationTestSubAgent
- **Supports**: PenTestAgent
- **Runs**: Individual test cases from the 8-test suite
- **Reports**: Pass/fail per test with evidence

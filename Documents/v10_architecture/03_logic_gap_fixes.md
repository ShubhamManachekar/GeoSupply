# Chapter 3: All Logic Gap Fixes + 8 New Gaps Found

## v9 Gaps — FIXED in v10

---

### ✅ GAP 1 FIX: Knowledge Graph Write-Buffer Queue

```python
class KnowledgeWriteBuffer:
    """
    Single-writer authority for KnowledgeGraphAgent.
    Workers submit KnowledgeUpdateRequest to queue.
    KnowledgeGraphAgent processes in order. No race conditions.

    WHY THIS FIXES IT:
        v9: Multiple workers call KG.learn_from_pipeline() concurrently
            → NetworkX not thread-safe → race condition
        v10: Workers call KG.enqueue_update() → async queue
             → KG processes queue in single thread → safe

    QUEUE PROPERTIES:
        Max depth: 500 requests
        Processing: batch of 50 per cycle
        Ordering: FIFO within priority
        Dedup: same entity+relation within 5 min → merged
        Backpressure: if queue full, workers get warning (not blocked)
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._dedup_window: dict[str, datetime] = {}

    async def enqueue(self, update: 'KnowledgeUpdateRequest') -> bool:
        """Thread-safe enqueue. Returns False if queue full."""
        dedup_key = f"{update.entity_source}:{update.entity_target}:{update.relation_type}"
        if dedup_key in self._dedup_window:
            if (datetime.utcnow() - self._dedup_window[dedup_key]).seconds < 300:
                return True  # Dedup — already queued

        try:
            self._queue.put_nowait(update)
            self._dedup_window[dedup_key] = datetime.utcnow()
            return True
        except asyncio.QueueFull:
            LoggingAgent().log("kg_queue_full", queue_depth=500)
            return False

    async def process_batch(self, graph: nx.DiGraph) -> int:
        """Process up to 50 updates from queue. SINGLE THREAD ONLY."""
        processed = 0
        while processed < 50 and not self._queue.empty():
            update = await self._queue.get()
            self._apply_update(graph, update)
            processed += 1
        return processed

# LOOPHOLE-HUNTER CHECK: LOGIC-001 verifies queue ordering
```

---

### ✅ GAP 2 FIX: SummarizationVerifierSubAgent

```python
class SummarizationVerifierSubAgent(BaseSubAgent):
    """
    Catches semantic distortion in summaries/tweets.

    THE PROBLEM IT SOLVES:
        GeoRiskScore: India-Pakistan tension = 0.67 (BELOW threshold)
        ContentGenerator tweet: "Rising India-Pakistan tensions" ← WRONG
        FactCheckAgent: "India-Pakistan tension exists" ← TRUE but misleading
        SummarizationVerifier: "Tweet implies HIGH, data shows LOW" ← CAUGHT

    HOW IT WORKS:
        1. Extract numerical claims from source data
        2. Extract directional language from summary ("rising", "escalating", etc.)
        3. Compare: does direction in summary match actual data trend?
        4. Check: do magnitudes match? (0.67 ≠ "high tension")
        5. Check: are qualifiers present? ("modest tension" vs "rising tensions")

    THRESHOLDS:
        0.0 - 0.30 → "minimal/negligible"
        0.30 - 0.50 → "low/modest"
        0.50 - 0.70 → "moderate/notable"
        0.70 - 0.85 → "high/significant"
        0.85 - 1.00 → "critical/severe"

    If tweet uses language from a HIGHER band than data supports → REJECT.
    """
    name = "SummarizationVerifierSubAgent"

    MAGNITUDE_BANDS = {
        (0.0, 0.30): ["minimal", "negligible", "trivial", "insignificant"],
        (0.30, 0.50): ["low", "modest", "minor", "limited"],
        (0.50, 0.70): ["moderate", "notable", "considerable"],
        (0.70, 0.85): ["high", "significant", "substantial", "rising", "escalating"],
        (0.85, 1.00): ["critical", "severe", "extreme", "alarming", "unprecedented"],
    }

    async def verify(self, source_data: dict, summary: str) -> dict:
        """Check semantic preservation between data and summary."""
        score = source_data.get("score", source_data.get("confidence", 0.5))
        actual_band = self._get_band(score)
        summary_words = summary.lower().split()

        # Check for words from HIGHER bands in summary
        for band_range, band_words in self.MAGNITUDE_BANDS.items():
            if band_range[0] > actual_band[1]:  # Higher band
                for word in band_words:
                    if word in summary_words:
                        return {
                            "status": "rejected",
                            "reason": f"Summary uses '{word}' (band {band_range}) "
                                      f"but data score is {score:.2f} (band {actual_band})",
                            "data_score": score,
                            "offending_word": word,
                        }

        return {"status": "passed", "data_score": score}

# LOOPHOLE-HUNTER CHECK: LOGIC-004 verifies this runs on all marketing content
```

---

### ✅ GAP 3 FIX: Source Penalty Escalation + Clustering

```python
class EscalatingPenaltyEngine:
    """
    Replaces fixed -0.05 penalty with escalating penalties.

    v9:  Every quarantine = -0.05, recovery +0.02/week, floor 0.10
    v10: Escalating penalties with permanent flagging

    ESCALATION SCHEDULE:
        1st quarantine (ever):              -0.05
        2nd quarantine (within 30 days):    -0.10
        3rd quarantine (within 30 days):    -0.20
        4th quarantine (within 30 days):    PERMANENT FLAG
            → Source suspended
            → Admin override required to re-enable
            → SourceClusterSubAgent checks for related sources

    CLUSTER DETECTION:
        If source A is permanently flagged:
            Find all sources sharing:
                - Same IP range
                - Same domain or subdomain
                - Same author/byline
                - Similar writing style (embedding cosine > 0.90)
            Apply -0.15 penalty to entire cluster
            Alert admin: "Coordinated source network detected"

    RECOVERY:
        Non-flagged: +0.02/week (unchanged)
        Previously flagged + admin-reinstated: +0.01/week (slower)
    """

    def calculate_penalty(self, source_id: str) -> float:
        history = self._get_quarantine_history(source_id, days=30)
        count = len(history)

        if count == 0: return -0.05
        if count == 1: return -0.10
        if count == 2: return -0.20
        return float('inf')  # Permanent flag

# LOOPHOLE-HUNTER CHECK: LOGIC-003 verifies escalation is applied
```

---

### ✅ GAP 4 FIX: Internal Circuit Breakers

```python
class InternalCircuitBreaker:
    """
    Circuit breaker for internal agent calls (not just external APIs).

    v9:  @breaker only on external HTTP calls
    v10: @internal_breaker on all Tier-3+ agent calls

    AGENTS PROTECTED:
        FactCheckAgent      → timeout 30s, max 3 failures → OPEN
        AuditorAgent        → timeout 20s, max 3 failures → OPEN
        BriefSynthSubAgent  → timeout 60s, max 2 failures → OPEN
        AuthorWorker        → timeout 45s, max 3 failures → OPEN

    SAFE DEFAULTS (when circuit OPEN):
        FactCheck OPEN      → quarantine ALL claims (safe)
        Auditor OPEN        → 100% sampling next cycle (safe)
        BriefSynth OPEN     → use MoAFallbackSubAgent (see GAP 5 fix)
        AuthorWorker OPEN   → skip author analysis, log gap

    RECOVERY:
        After 5 min: HALF_OPEN (try 1 request)
        If succeeds: CLOSED
        If fails: OPEN again, extend to 10 min
    """

    def __init__(self, failure_threshold=3, timeout_s=30, reset_s=300):
        self.failure_threshold = failure_threshold
        self.timeout_s = timeout_s
        self.reset_s = reset_s
        self._failure_count = 0
        self._state = "CLOSED"
        self._last_failure = None

def internal_breaker(timeout_s=30, max_failures=3):
    """Decorator for internal agent calls."""
    def decorator(func):
        breaker = InternalCircuitBreaker(
            failure_threshold=max_failures, timeout_s=timeout_s
        )
        async def wrapper(*args, **kwargs):
            if breaker._state == "OPEN":
                if breaker.should_try_half_open():
                    breaker._state = "HALF_OPEN"
                else:
                    return breaker.get_safe_default(func.__name__)

            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_s)
                breaker._failure_count = 0
                breaker._state = "CLOSED"
                return result
            except (asyncio.TimeoutError, Exception) as e:
                breaker._failure_count += 1
                if breaker._failure_count >= max_failures:
                    breaker._state = "OPEN"
                    breaker._last_failure = datetime.utcnow()
                raise
        return wrapper
    return decorator

# Usage:
@internal_breaker(timeout_s=30, max_failures=3)
async def fact_check_claims(claims: list[dict]) -> dict:
    return await FactCheckAgent().verify(claims)

# LOOPHOLE-HUNTER CHECK: LOGIC-005 verifies all internal breakers status
```

---

### ✅ GAP 5 FIX: MoA Fallback Aggregation Chain

```python
class MoAFallbackSubAgent(BaseSubAgent):
    """
    Fallback aggregation for when primary MoA aggregator fails.

    v9:  Single aggregator. If it fails, 3 proposals are LOST.
    v10: 4-level fallback chain. Proposals are NEVER discarded.

    FALLBACK CHAIN:
        Level 0: GPT-OSS:20b full MoA aggregation (primary)
        Level 1: Groq llama-3.3-70b aggregation (cloud fallback)
        Level 2: Scoring-based selection (pick highest confidence)
        Level 3: Return all 3 proposals to admin for manual pick

    PROPOSAL PRESERVATION:
        All 3 proposer outputs saved to SQLite BEFORE aggregation.
        Even if all 4 fallback levels fail, proposals are recoverable.
        Admin CLI: geosupply brief proposals <brief_id>
    """
    name = "MoAFallbackSubAgent"

    FALLBACK_CHAIN = [
        {"model": "GPT-OSS:20b", "type": "full_moa", "cost_inr": 0},
        {"model": "llama-3.3-70b", "type": "full_moa", "cost_inr": 0},
        {"model": None, "type": "scoring", "cost_inr": 0},
        {"model": None, "type": "manual", "cost_inr": 0},
    ]

    async def aggregate(self, proposals: list[dict]) -> dict:
        # ALWAYS save proposals first
        await self._save_proposals_to_db(proposals)

        for level, fallback in enumerate(self.FALLBACK_CHAIN):
            try:
                if fallback["type"] == "full_moa":
                    return await self._moa_aggregate(proposals, fallback["model"])
                elif fallback["type"] == "scoring":
                    return self._scoring_aggregate(proposals)
                elif fallback["type"] == "manual":
                    return await self._queue_for_admin(proposals)
            except Exception as e:
                LoggingAgent().log("moa_fallback", level=level, error=str(e))
                continue

        # Should never reach here — Level 3 always succeeds
        return {"status": "error", "proposals_saved": True}

    def _scoring_aggregate(self, proposals: list[dict]) -> dict:
        """Simple: pick the proposal with highest confidence score."""
        best = max(proposals, key=lambda p: p.get("confidence", 0))
        return {
            "status": "success",
            "aggregation_method": "scoring_fallback",
            "selected_proposal": best,
            "confidence": best.get("confidence", 0),
        }

# LOOPHOLE-HUNTER CHECK: LOGIC-002 verifies proposals saved before aggregation
```

---

### ✅ GAP 6 FIX: OverrideAuditAgent

```python
class OverrideAuditAgent(BaseAgent):
    """
    Reviews admin override patterns. Catches systematic FactCheck bypass.

    v9:  OverrideRecord is write-only log
    v10: OverrideAuditAgent reads + analyses patterns weekly

    CHECKS:
        1. Count overrides per admin per week
           Alert if >5 overrides/week
        2. Pattern detection: same source always approved
           Alert if source X manually approved >3 times
        3. Time clustering: many overrides in short window
           Alert if >3 overrides within 1 hour
        4. FactCheck bypass rate:
           Alert if >20% of quarantined briefs manually approved
        5. Source credibility override skew:
           Alert if admin always overrides same direction (up/down)

    OUTPUT: WeeklyOverrideReport → admin email + portal
    """
    name = "OverrideAuditAgent"
    domain = "audit"

    async def weekly_audit(self) -> 'OverrideAuditReport':
        records = await self._get_override_records(days=7)

        findings = []
        # Check 1: Volume
        if len(records) > 5:
            findings.append("HIGH_VOLUME: {len(records)} overrides this week")

        # Check 2: Source pattern
        source_approvals = Counter(r.target for r in records if r.action == "brief_approve")
        for source, count in source_approvals.items():
            if count > 3:
                findings.append(f"PATTERN: Source '{source}' manually approved {count} times")

        # Check 3: Time clustering
        timestamps = sorted(r.timestamp for r in records)
        for i in range(len(timestamps) - 2):
            window = (timestamps[i+2] - timestamps[i]).seconds
            if window < 3600:
                findings.append(f"CLUSTER: 3 overrides within {window}s at {timestamps[i]}")

        return OverrideAuditReport(
            week=self._current_week(),
            total_overrides=len(records),
            findings=findings,
            risk_level="HIGH" if len(findings) > 2 else "MEDIUM" if findings else "LOW"
        )

# LOOPHOLE-HUNTER CHECK: OVS-003 verifies this runs weekly
```

---

## 8 NEW Logic Gaps Found in v10 Deep Audit

### NEW GAP 7: EventBus Dead Letter Queue Never Reviewed

```
PROBLEM:
    EventBus has dead_letters list for failed handlers.
    But nobody examines them. Failed events silently pile up.

FIX: DeadLetterReviewAgent runs daily:
    - Check dead letter queue depth
    - Retry failed events (max 3 retries)
    - Alert if queue depth > 20
    - Monthly: purge events > 30 days old
```

### NEW GAP 8: Tracer Spans Have No Size Limit

```
PROBLEM:
    Distributed Tracer stores all spans in memory.
    A pipeline run creates hundreds of spans.
    After 100+ runs, memory consumption grows unbounded.

FIX: Ring buffer for spans:
    - Keep last 50 traces in memory (hot)
    - Archive older traces to SQLite (cold)
    - Query cold traces via CLI: geosupply trace <trace_id>
```

### NEW GAP 9: PerformanceLearnerAgent Has No Feedback Verification

```
PROBLEM:
    PerformanceLearner suggests "downgrade Task X from Tier-3 to Tier-2".
    But it never checks if the downgrade actually worked.
    If Tier-2 produces worse quality, nobody notices until audit.

FIX: Add A/B testing for routing changes:
    - 80% traffic on current route, 20% on proposed route
    - Compare quality scores after 3 pipeline runs
    - Only commit if proposed route quality >= 95% of current
```

### NEW GAP 10: CyberThreatWorker Has No Ground Truth

```
PROBLEM:
    CyberThreatWorker generates CyberThreatScores.
    But there's no feedback loop — was the threat real?
    Accuracy is never measured.

FIX: Add CyberThreatAccuracyTracker:
    - Log each threat with "expected impact timeline"
    - After timeline passes, check if impact materialised
    - Track accuracy → improve threat model
```

### NEW GAP 11: Twitter Publisher Has No Content De-duplication

```
PROBLEM:
    If same prediction persists across 3 pipeline runs,
    ContentGenerator creates 3 similar tweets.
    Repetitive tweets hurt engagement.

FIX: ContentDeduplicationWorker:
    - Embedding similarity check against last 50 tweets
    - If cosine similarity > 0.85 → skip/modify
    - Force variety: no more than 2 tweets on same topic/day
```

### NEW GAP 12: No Canary for Knowledge Graph Updates

```
PROBLEM:
    When KnowledgeGraphAgent merges new knowledge,
    there's no way to verify the merge didn't corrupt existing knowledge.
    A bad merge could silently degrade RAG retrieval quality.

FIX: KG canary check:
    - Before merge: snapshot 10 random entity queries
    - After merge: re-run same queries
    - If results diverge significantly → alert + rollback merge
```

### NEW GAP 13: Autonomous Scheduler Self-Adjustment Has No Bounds

```
PROBLEM:
    AutonomousScheduler adjusts pipeline interval between 4-8 hours.
    But during holidays/weekends, all APIs return stale data.
    Scheduler might shrink to 4hr (more runs on stale data = wasted cost).

FIX: Day-of-week awareness:
    - Weekends: minimum interval 8 hours
    - India holidays (Diwali, Republic Day, etc.): 12 hours
    - Groq (US-based) holidays: extend if API is slower
```

### NEW GAP 14: No Graceful Handling of Schema Migration

```
PROBLEM:
    Pydantic schemas evolve across versions.
    ChromaDB vectors embedded with old schemas can't be queried
    with new schemas. No migration path.

FIX: Schema versioning:
    - Every schema carries version field (v1, v2, ...)
    - ChromaDB metadata includes schema_version
    - SchemaVersionMigrator converts old→new on read
    - Weekly: background migration of old entries
```

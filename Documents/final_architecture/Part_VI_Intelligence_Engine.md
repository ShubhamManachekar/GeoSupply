# Part VI: Intelligence Engine — Self-Learning, Knowledge Graph, Cyber Threat Intel
## FA v1 | Gap Mitigations: G5, G6 applied

## 6.1 Self-Learning Architecture — Three Pillars

### Pillar 1: Domain Knowledge Accumulation (KnowledgeGraphAgent)

```python
class KnowledgeGraphAgent(BaseAgent):
    """
    Builds and maintains a NetworkX knowledge graph of geopolitical
    entities, relationships, and events. Becomes an expert over time.

    ENTITIES: Countries, leaders, organizations, ports, trade routes,
              companies, commodities, military assets, agreements
    RELATIONS: trade_with, sanctions, allied_with, conflict_with,
               supplies_to, depends_on, borders, threatens

    LEARNING LOOP:
        1. Every pipeline run → NERWorker extracts entities
        2. Intelligence analysis → new relations discovered
        3. KnowledgeGraphAgent merges into graph
        4. Graph enriches future RAG retrieval (GraphRAGWorker)
        5. Over time: system "knows" India-China trade patterns,
           monsoon-port correlations, sanction cascades

    v10 FIX: Write-buffer queue (single-writer, FIFO, dedup)
        Workers enqueue KnowledgeUpdateRequest objects
        KG processes batches of 50 in single thread
        Queue max depth: 500, backpressure if full

    FA v1 G5 FIX — Dedup Key Definition:
        Dedup key = (entity_source, entity_target, relation_type)
        Within each batch of 50:
            - If same dedup key appears multiple times → keep latest timestamp
            - If same dedup key exists in graph with same confidence → skip
            - If same dedup key exists with DIFFERENT confidence → update if new > old
        Cross-batch dedup: 1-hour sliding window via SQLite dedup_log table

    v10 FIX: Entity verification against known databases
        Countries: ISO 3166 list
        Companies: SEC EDGAR + India MCA
        Ports: UN/LOCODE
        Unknown entities: flagged for admin review

    v10 FIX: KG canary check before merge
        Snapshot 10 random queries before merge
        Re-run after merge → divergence check → rollback if broken

    BACKUP: Snapshot to Google Drive every 6 hours (RPO = 6hr)
    """
```

### Pillar 2: Operational Self-Improvement (PerformanceLearnerAgent)

```python
class PerformanceLearnerAgent(BaseAgent):
    """
    Learns from operational history to optimise the swarm.

    TRACKS:
        - Tier routing decisions and resulting quality scores
        - Pipeline latency per stage
        - Cost per task type (INR)
        - Worker success/failure rates
        - Source reliability over time

    LEARNS:
        - Which tasks can be downgraded from Tier-3 to Tier-2
        - Which sources consistently provide quality data
        - Optimal pipeline scheduling interval (4-8 hours)
        - Which workers need more retries vs which are reliable

    v10 FIX: A/B testing before committing routing changes
        80% traffic on current route, 20% on proposed route
        Compare quality after 3 pipeline runs
        Only commit if proposed quality >= 95% of current

    OUTPUT: Monthly PerformanceReport + routing recommendations
    """
```

### Pillar 3: Predictive Intelligence (ConflictPredictor + PredictionAgent)

```python
class ConflictPredictor:
    """XGBoost model with Platt scaling. Predicts conflict probability."""
    # Features: historical patterns, current tensions, economic indicators
    # Output: conflict_probability (0-1) + calibrated confidence

class PredictionAgent(BaseAgent):
    """
    Generates market-ready predictions with accuracy tracking.

    CATEGORIES:
        1. Geopolitical risk (Suez disruption, LAC tension, etc.)
        2. Supply chain stress (port utilisation, monsoon impact)
        3. Trade flow changes (bilateral trade forecasts)
        4. Commodity price impact (crude import cost in ₹ crore)

    ACCURACY TRACKING:
        Every prediction logged with target date.
        After date passes → actual outcome compared.
        Monthly scorecard: "78% accuracy last month"
        Calibration curve: are 70% predictions right 70% of the time?
    """
```

---

## 6.2 Cyber Threat Intelligence — Dual Mission

### Mission 1: Defend the Swarm (CyberDefenseAgent)

```
MONITORS:
    Prompt injection attempts (InputGuardAgent pre-filter)
    API key exposure in logs/outputs
    Anomalous source patterns (source gaming)
    Internal message tampering (event signing v10)
    Dependency vulnerabilities (DepUpdateAgent)

RESPONSE:
    Injection detected → quarantine input + alert admin
    Key exposure → immediate rotation (SecurityAgent)
    Source gaming → escalating penalty + cluster ban
    Dependency CVE → auto-PR for security patch
```

### Mission 2: Track External Cyber Threats (CyberThreatWorker)

```python
class CyberThreatWorker(BaseWorker):
    """
    Monitors cyber threats impacting global supply chains.
    Tracks ransomware, GPS jamming, state-sponsored APTs.

    THREAT TAXONOMY:
        RANSOMWARE:     Ports, shipping companies, logistics platforms
        GPS_JAMMING:    Shipping lane disruption (Red Sea, South China Sea)
        STATE_APT:      State-sponsored attacks on trade infrastructure
        DDoS:           Exchange/trading platform outages
        DATA_BREACH:    Trade data exposure, corporate espionage
        SUPPLY_CHAIN_ATTACK: Compromised software in logistics stack
        CABLE_CUT:      Submarine cable damage (internet/comms)
        SCADA:          Attack on port/energy infrastructure control systems

    LOOPHOLE ANALYSIS:
        Identifies logic gaps in supply chain cybersecurity:
        - Unpatched port management systems
        - Weak authentication on logistics APIs
        - Insider threat vectors in shipping companies
        - Satellite communication interception risks
        - Air-gapped system bridge vulnerabilities

    SOURCES: CISA, CERT-In, NVD, Shodan, GreyNoise, AlienVault OTX

    OUTPUT: CyberThreatScore (Pydantic schema)
        threat_type: str
        affected_sector: str
        severity: 0.0-1.0
        geographic_scope: list[str]
        india_impact: str
        mitigation_status: str
        mitre_attack_id: str
    """

### FA v1: G6 FIX — Channel Fingerprint Baseline Timing

```
ChannelFingerprintWorker baseline creation protocol:

    INITIAL BASELINE (new channel onboarding):
        1. Collect first 100 messages from channel
        2. Compute fingerprint dimensions:
           - Avg message length, posting frequency, language distribution
           - Topic embedding centroid (mean of all message embeddings)
           - Author/account age distribution
        3. Store as ChannelFingerprint with baseline_hash
        4. Mark channel as BASELINE_COMPLETE

    ONGOING MONITORING:
        - Every 24 hours: compute new fingerprint from last 100 messages
        - KL divergence against baseline
        - If KL > 0.30 → flag for review (manageable drift)
        - If KL > 0.60 → suspend channel ingestion (major drift)
        - Admin can: recalibrate baseline, or permanently suspend

    EDGE CASES:
        - Channel with <100 messages: wait until threshold met, use PROVISIONAL status
        - Channel goes silent >7 days: alert admin, don't auto-suspend
```

---

## 6.3 Learning Feedback Loops

```
LOOP 1: Source Quality
    Ingest → FactCheck → quarantine → SourceFeedback → score ↓
    Next ingest: low-score sources get lower weight

LOOP 2: Routing Optimisation
    Route Tier-3 → cost ₹X → quality Y
    PerformanceLearner: "Tier-2 gives quality 0.95Y at 0.3X"
    A/B test → confirm → downgrade (save INR)

LOOP 3: Knowledge Accumulation
    Pipeline output → KnowledgeGraph learns entities/relations
    Next RAG query → GraphRAGWorker uses richer graph
    Intelligence quality improves over time

LOOP 4: Prediction Accuracy
    Prediction generated → target date set
    Date passes → actual outcome compared
    Accuracy feeds back to PredictionAgent model
    Content strategy adjusted (stop posting low-accuracy categories)
```

## CROSS-CHECK ✅
```
✓ KnowledgeGraphAgent has write-buffer queue (GAP 1)
✓ Entity verification against ISO/MCA/LOCODE (LOOPHOLE 7)
✓ KG canary check before merge (GAP 12)
✓ PerformanceLearner has A/B testing (GAP 9)
✓ CyberThreatWorker has full taxonomy (8 types)
✓ CyberDefenseAgent has prompt injection scan
✓ All 4 learning feedback loops documented
✓ KG backup RPO = 6 hours (BLIND SPOT 2)
✓ [FA v1] KG dedup key = (entity_source, entity_target, relation_type) (G5)
✓ [FA v1] Channel fingerprint baseline protocol defined (G6)
```

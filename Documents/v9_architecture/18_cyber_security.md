# Chapter 18: Cyber Attack Tracking, Threat Intelligence & Security Hardening

## Design Philosophy

> **GeoSupply monitors global supply chains. That makes it a target AND a sensor.**
> It must protect itself AND track cyber threats that impact supply chains.

---

## Two Missions of Cyber Security in v9

```
MISSION 1 — DEFENSIVE: Protect the GeoSupply swarm itself
    → Secure API keys, prevent prompt injection, harden pipelines

MISSION 2 — INTELLIGENCE: Track cyber attacks affecting supply chains
    → GPS jamming, port system hacks, shipping ransomware, state cyber ops
    → Feed cyber threat intel into the supply chain risk model
```

---

## Mission 1: Defensive Security — Protecting the Swarm

### Threat Model — Attack Surfaces

```
ATTACK SURFACE              THREAT                           MITIGATION
─────────────────────────────────────────────────────────────────────────
LLM Prompt Injection        Malicious articles craft         Input sanitization +
                            prompts that manipulate          prompt boundary enforcement +
                            NER/Sentiment/Claim workers      STATIC decoder constrains output

API Key Exfiltration        Leaked keys in logs or code     SecurityAgent.get_key() ONLY +
                                                             never os.getenv() in modules +
                                                             key rotation every 30 days

Data Poisoning              Adversary feeds fake articles    FactCheckAgent 7-step pipeline +
                            to bias intelligence briefs      SourceFeedbackSubAgent penalties +
                                                             source credibility scoring

Supply Chain Attack         Compromised Python package       Pin all dependencies +
                            in requirements.txt              pip audit weekly +
                                                             GitHub Dependabot alerts

Denial of Service           Flood ingestion pipeline         Rate limiting per source +
                            with garbage data                circuit breaker auto-open +
                                                             queue depth monitoring (200 cap)

Model Manipulation          Adversarial inputs designed      STATIC decoder prevents
                            to cause specific outputs        unconstrained generation +
                                                             confidence scoring rejects low-score

Insider Threat              Unauthorized config change       Override audit trail +
                                                             all admin actions logged +
                                                             HALLUCINATION_FLOOR locked

ChromaDB Tampering          Direct vector store              Single-writer authority (RAGManager) +
                            modification                     write-buffer queue +
                                                             hash verification on read

Session Hijacking           Stolen session_id used to        JWT tokens with 8hr expiry +
                            inject fake agent messages       message contract validation +
                                                             agent signature verification
```

### CyberDefenseAgent (NEW in v9)

```python
class CyberDefenseAgent(BaseAgent):
    """
    Singleton infrastructure agent for defensive security.
    Always-on. Monitors all system interactions for threats.

    DETECTION CAPABILITIES:
        1. Prompt Injection Detection
        2. Anomalous Input Patterns
        3. API Key Usage Anomalies
        4. Data Poisoning Indicators
        5. Dependency Vulnerability Scanning
        6. Unauthorized Access Attempts
        7. Message Contract Violations (potential injection)
    """
    name = "CyberDefenseAgent"
    domain = "infrastructure"

    @staticmethod
    def scan_input_for_injection(text: str) -> dict:
        """
        Detect prompt injection attempts in incoming articles/data.

        PATTERNS DETECTED:
            - "Ignore previous instructions"
            - System prompt extraction attempts
            - Role-play injection ("You are now a...")
            - Encoded/obfuscated injection payloads
            - Unicode homoglyph attacks
            - Markdown/HTML injection in data fields
        """
        injection_patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"you\s+are\s+now\s+a",
            r"system\s*prompt",
            r"<script>",
            r"{{.*}}",  # Template injection
            r"\\x[0-9a-f]{2}",  # Hex-encoded payloads
        ]
        # Returns: {is_suspicious: bool, patterns_matched: list, risk_score: float}
        ...

    @staticmethod
    def validate_agent_message(message: dict, expected_agent: str) -> bool:
        """
        Verify message authenticity — prevent spoofed agent messages.
        Checks: agent name matches, session_id valid, timestamp recent.
        """
        ...

    def monitor_api_usage(self) -> list[dict]:
        """
        Detect anomalous API key usage patterns.
        Alerts: unexpected IP, unusual hour, excessive rate, unknown endpoint.
        """
        ...
```

---

## Mission 2: Cyber Threat Intelligence — Supply Chain Impact

### CyberThreatWorker (NEW in v9)

```python
class CyberThreatWorker(BaseWorker):
    """
    Tracks cyber attacks that impact global supply chains.
    Feeds threat intelligence into the risk model.

    DATA SOURCES:
        - CISA (US Cybersecurity & Infrastructure Security Agency)
        - CERT-In (Indian Computer Emergency Response Team)
        - MITRE ATT&CK supply chain attack patterns
        - Public CVE databases
        - Dark web monitoring feeds (via API)
        - GPS jamming detection (existing AIS data)
        - Maritime cyber incident reports
        - Industrial control system (ICS) advisories

    CYBER ATTACK TYPES TRACKED:
        (see taxonomy below)
    """
    name = "CyberThreatWorker"
    tier = 1
    use_static = True
    capabilities = {"CYBER_THREAT_TRACK", "CYBER_ASSESS"}
```

### Cyber Attack Taxonomy

```
CATEGORY 1 — SUPPLY CHAIN CYBER ATTACKS
├── Ransomware on Logistics
│   ├── Port management system attacks (Maersk/NotPetya type)
│   ├── Warehouse management system encryption
│   ├── Freight booking platform attacks
│   └── Last-mile delivery system disruptions
├── GPS/Navigation Jamming & Spoofing
│   ├── Maritime GPS jamming (Black Sea, Persian Gulf patterns)
│   ├── Aviation GPS spoofing near conflict zones
│   ├── Container tracking system manipulation
│   └── AIS (Automatic Identification System) spoofing
├── Trade & Financial System Attacks
│   ├── SWIFT/banking system intrusions
│   ├── Customs/trade documentation forgery
│   ├── Letter of credit manipulation
│   └── Cryptocurrency-based sanctions evasion
└── Critical Infrastructure
    ├── Power grid attacks affecting ports/warehouses
    ├── Water system attacks near industrial zones
    ├── Telecom disruption affecting supply chain comms
    └── Internet cable sabotage (submarine cables)

CATEGORY 2 — STATE-SPONSORED CYBER OPERATIONS
├── China-linked
│   ├── APT41 — supply chain software attacks
│   ├── APT31 — trade secret theft
│   ├── Volt Typhoon — critical infrastructure pre-positioning
│   └── Salt Typhoon — telecom surveillance
├── Russia-linked
│   ├── Sandworm — destructive infrastructure attacks
│   ├── Fancy Bear — geopolitical espionage
│   └── Turla — diplomatic intelligence gathering
├── North Korea-linked
│   ├── Lazarus — financial theft (crypto, banking)
│   └── Supply chain attacks via compromised software
├── Iran-linked
│   ├── Maritime targeting (shipping, port systems)
│   └── Industrial control system attacks
└── India-relevant
    ├── Sidewinder (India-origin, regional targeting)
    ├── Pakistan-linked espionage groups
    └── Cross-border hacktivist campaigns

CATEGORY 3 — LOGIC GAPS, LOOPHOLES & OVERSIGHT
├── Business Logic Vulnerabilities
│   ├── Trade finance logic flaws (duplicate invoicing)
│   ├── Customs declaration manipulation
│   ├── Certificate of origin forgery gaps
│   ├── Sanctions screening bypass patterns
│   └── Dual-use goods classification exploitation
├── Oversight Gaps
│   ├── Unmonitored data transfer points between systems
│   ├── Legacy system integration vulnerabilities
│   ├── Third-party vendor access without audit
│   ├── Shadow IT in logistics companies
│   └── Inadequate logging in critical transaction paths
├── Protocol & Standard Weaknesses
│   ├── EDIFACT/EDI message manipulation
│   ├── Container weight declaration gaps (SOLAS VGM)
│   ├── Bill of lading fraud vectors
│   ├── AIS protocol weaknesses (unencrypted broadcasts)
│   └── ISPS Code compliance gaps at ports
└── Systemic Blind Spots
    ├── Multi-hop supply chains obscuring origin
    ├── Free trade zone opacity
    ├── Ship-to-ship transfer monitoring gaps
    ├── Transshipment hub regulatory arbitrage
    └── Beneficial ownership concealment in shipping
```

### Cyber Risk Scoring

```python
class CyberThreatScore(BaseModel):
    """Pydantic schema for cyber threat assessment."""
    threat_id: str
    threat_type: str          # From taxonomy above
    category: str             # "supply_chain" | "state_sponsored" | "logic_gap"
    severity: str             # CRITICAL | HIGH | MEDIUM | LOW
    confidence: float         # 0.0 - 1.0
    affected_sectors: list[str]
    affected_countries: list[str]
    affected_supply_routes: list[str]
    attack_vector: str        # MITRE ATT&CK mapping
    mitigations: list[str]
    source: str               # Which threat feed reported this
    first_seen: datetime
    last_updated: datetime
    supply_chain_impact: float  # 0.0 (none) - 1.0 (catastrophic)

    # Integration with existing risk model
    geo_risk_modifier: float   # How much this changes GeoRiskScore
    chokepoint_impact: dict    # Which chokepoints affected and how much
```

### Integration with Supply Chain Risk Model

```
CYBER THREAT → SUPPLY CHAIN IMPACT PIPELINE:

1. CyberThreatWorker detects threat
   → CyberThreatScore created

2. Score fed to KnowledgeGraphAgent
   → Threat linked to affected entities (countries, ports, routes)
   → Graph edges updated with cyber risk weight

3. Score fed to ConflictPredictor (XGBoost)
   → Cyber threat features added to prediction model
   → GeoRiskScore.cyber_risk_modifier applied

4. Score fed to StressWorker
   → Supply chain stress test includes cyber scenarios
   → "What if Port X management system encrypted by ransomware?"

5. Score fed to Dashboard
   → New Streamlit page: Cyber Threat Map
   → Overlay cyber threats on existing supply chain map
   → Real-time GPS jamming indicators from AIS data

6. Score fed to IntelBrief
   → BriefSynthSubAgent includes cyber dimension
   → "Note: Active GPS jamming detected in Persian Gulf (confidence 0.87)"
```

---

## Security Hardening Checklist (v9)

```
PREVENTION:
    [x] All API keys via SecurityAgent.get_key() — never hardcoded
    [x] STATIC decoder prevents unconstrained LLM output
    [x] Input sanitization on all ingested text
    [x] Prompt injection detection before NLP processing
    [x] Single-writer authority for ChromaDB (no tampering)
    [x] Rate limiting on all ingestion sources
    [ ] NEW: pip audit in CI/CD pipeline
    [ ] NEW: SBOM (Software Bill of Materials) generated per release
    [ ] NEW: Container image vulnerability scanning

DETECTION:
    [x] FactCheckAgent catches fabricated claims
    [x] SourceFeedbackSubAgent penalises bad sources
    [x] AuditorAgent stratified sampling catches drift
    [ ] NEW: CyberDefenseAgent — prompt injection detection
    [ ] NEW: CyberDefenseAgent — API usage anomaly detection  
    [ ] NEW: CyberDefenseAgent — message contract violation alerts
    [ ] NEW: CyberThreatWorker — external threat tracking

RESPONSE:
    [x] Circuit breaker auto-opens on API failures
    [x] DEGRADED_MODE for graceful failure
    [x] SelfHealingEngine auto-recovery
    [ ] NEW: EMERGENCY HALT via CLI/Portal
    [ ] NEW: Automated key rotation on compromise detection
    [ ] NEW: Source quarantine on data poisoning detection
    [ ] NEW: Incident response runbook (documented)

AUDIT:
    [x] All events logged to Supabase
    [x] Override audit trail (every manual action logged)
    [x] Weekly AuditorAgent reports
    [ ] NEW: Monthly security audit report (automated)
    [ ] NEW: Quarterly penetration test checklist
    [ ] NEW: Annual threat model review
```

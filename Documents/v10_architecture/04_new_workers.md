# Chapter 4: 8 New Workers in v10

## Worker Inventory Update

v9: 32 workers → **v10: 40 workers (+8 new)**

---

### 1. ChannelFingerprintWorker

```python
class ChannelFingerprintWorker(BaseWorker):
    """
    Monitors Telegram/RSS channel behavioural patterns.
    Detects channel takeover or compromise.

    FIXES: v9 LOOPHOLE 1 (Telegram channel poisoning)

    FINGERPRINT DIMENSIONS:
        - Posting frequency (avg posts/day over 30 days)
        - Language distribution (% Hindi, English, etc.)
        - Topic distribution (embedding clusters)
        - Active hours (when posts typically appear)
        - Median post length
        - Admin change events
        - URL domain distribution in posts

    DRIFT DETECTION:
        Compare current week's fingerprint to 30-day baseline.
        If KL divergence > 0.30 on any dimension → ALERT
        If >3 dimensions drift simultaneously → CHANNEL_COMPROMISED flag
        Admin must re-verify channel before ingestion resumes.
    """
    name = "ChannelFingerprintWorker"
    tier = 0
    use_static = False
    capabilities = {"CHANNEL_FINGERPRINT", "CHANNEL_VERIFY"}

    async def process(self, channel_data: dict) -> dict:
        current_print = self._compute_fingerprint(channel_data)
        baseline = self._get_baseline(channel_data["channel_id"])
        drift = self._compute_kl_divergence(current_print, baseline)

        if drift > 0.30:
            await EventBus().publish(Event(
                topic="channel_compromised",
                source=self.name,
                payload={"channel_id": channel_data["channel_id"], "drift": drift}
            ))
            return {"status": "alert", "drift": drift, "action": "suspend_channel"}

        return {"status": "healthy", "drift": drift}
```

---

### 2. InputSanitiserWorker

```python
class InputSanitiserWorker(BaseWorker):
    """
    Pre-processing guard for ALL ingested text content.

    FIXES: v9 LOOPHOLE 2 (STATIC decoder prompt length bypass)
    ADDS:  Prompt injection detection layer

    PIPELINE:
        1. Token count check (hard limit: 2048 for Tier-1 inputs)
        2. If exceeds: truncate + summarise via Tier-2 model
        3. Prompt injection pattern scan (regex + embedding)
        4. Unicode normalisation (prevent homoglyph attacks)
        5. HTML/Markdown stripping (prevent injection via formatting)
        6. URL extraction + safety check (no malicious links)
        7. Language detection (ensure expected language)

    FLAGS INPUT AS:
        CLEAN      — passed all checks
        TRUNCATED  — was too long, summarised
        SUSPICIOUS — injection patterns detected → quarantine
        REJECTED   — multiple red flags → discard + alert
    """
    name = "InputSanitiserWorker"
    tier = 0
    use_static = False
    capabilities = {"SANITISE_INPUT", "CHECK_INJECTION"}

    MAX_TIER1_TOKENS = 2048
    WARN_TIER1_TOKENS = 1500

    async def process(self, text: str, target_tier: int = 1) -> dict:
        result = {"original_length": len(text), "flags": []}

        # 1. Token count
        token_count = self._count_tokens(text)
        if token_count > self.MAX_TIER1_TOKENS and target_tier == 1:
            text = await self._truncate_and_summarise(text)
            result["flags"].append("TRUNCATED")
            result["truncated_from"] = token_count

        # 2. Injection scan
        injection_result = CyberDefenseAgent.scan_input_for_injection(text)
        if injection_result["is_suspicious"]:
            result["flags"].append("SUSPICIOUS")
            result["injection_patterns"] = injection_result["patterns_matched"]
            if injection_result["risk_score"] > 0.80:
                result["flags"].append("REJECTED")
                return {"status": "rejected", **result}

        # 3. Unicode normalisation
        text = unicodedata.normalize("NFKC", text)

        # 4. HTML strip
        text = self._strip_html_markdown(text)

        result["status"] = "clean" if "SUSPICIOUS" not in result["flags"] else "quarantine"
        result["sanitised_text"] = text
        return result
```

---

### 3. CostProjectionWorker

```python
class CostProjectionWorker(BaseWorker):
    """
    Forward-looking INR cost estimation.

    FIXES: v9 BLIND SPOT 5 (no cost projection)

    CALCULATES:
        - Current cost rate (INR/hr over last 7 days)
        - Projected daily cost (based on trend)
        - Projected monthly cost
        - Alerts if projected > 80% of budget cap (₹400/₹500)
        - Suggests cost reduction actions
    """
    name = "CostProjectionWorker"
    tier = 0
    use_static = False
    capabilities = {"COST_PROJECT", "COST_OPTIMISE"}
```

---

### 4. TwitterAPIWorker

```python
class TwitterAPIWorker(BaseWorker):
    """
    Twitter/X API v2 operations for MarketingAgent.
    Handles posting, reading engagement, deleting tweets.

    API: Twitter/X API v2 (Essential tier — free)
    Rate limits: 1,500 tweets/month, 10,000 reads/month
    Auth: OAuth 2.0 via SecurityAgent.get_key("twitter_api")
    """
    name = "TwitterAPIWorker"
    tier = 0
    use_static = False
    capabilities = {"TWEET_POST", "TWEET_DELETE", "TWEET_READ_ENGAGEMENT"}
```

---

### 5. NewsletterWorker

```python
class NewsletterWorker(BaseWorker):
    """
    Email newsletter delivery via SendGrid/Resend.
    Manages subscriber list, templates, and delivery tracking.

    API: SendGrid Free Tier (100 emails/day) or Resend (3,000/month)
    Cost: ₹0 (free tier)
    """
    name = "NewsletterWorker"
    tier = 0
    use_static = False
    capabilities = {"NEWSLETTER_SEND", "SUBSCRIBER_MANAGE"}
```

---

### 6. SBOMWorker

```python
class SBOMWorker(BaseWorker):
    """
    Software Bill of Materials generator.
    Creates CycloneDX SBOM from requirements.txt + lock files.

    SCHEDULE: Every release + weekly
    FORMAT: CycloneDX JSON (industry standard)
    CHECKS: Compares SBOM against known vulnerability databases
    """
    name = "SBOMWorker"
    tier = 0
    use_static = False
    capabilities = {"SBOM_GENERATE", "SBOM_AUDIT"}
```

---

### 7. BackupWorker

```python
class BackupWorker(BaseWorker):
    """
    Automated backup to Google Drive.

    FIXES: v9 BLIND SPOT 4 (no disaster recovery plan)

    BACKUP TARGETS:
        ChromaDB:        daily    → Google Drive geosupply_backups/chromadb/
        SQLite:          daily    → Google Drive geosupply_backups/sqlite/
        KnowledgeGraph:  every 6hr→ Google Drive geosupply_backups/kg/
        Config:          weekly   → Google Drive geosupply_backups/config/

    RPO: 6 hours (Knowledge Graph) / 24 hours (everything else)
    RTO: 4 hours (full restore from backup)
    RETENTION: 30 days of daily backups, 12 months of weekly
    """
    name = "BackupWorker"
    tier = 0
    use_static = False
    capabilities = {"BACKUP_RUN", "BACKUP_RESTORE", "BACKUP_VERIFY"}
```

---

### 8. LoopholeDetectionWorker

```python
class LoopholeDetectionWorker(BaseWorker):
    """
    Low-level check execution for LoopholeHunterAgent.
    Runs individual checks from the 24-check registry.

    CHECKS:
        - Query agent states
        - Validate schema compliance
        - Measure latency
        - Verify circuit breaker states
        - Check queue depths
        - Verify backup freshness
        - Test input sanitisation
    """
    name = "LoopholeDetectionWorker"
    tier = 0
    use_static = False
    capabilities = {"LOOPHOLE_CHECK", "SYSTEM_PROBE"}
```

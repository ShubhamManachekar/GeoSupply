---
name: marketing-automation
description: Marketing automation for GeoSupply's Layer 3/5 marketing agents — TwitterPublisher, ContentGenAgent, PredictionAgent, AnalyticsAgent. Covers geopolitical content strategy, AI SEO/GEO, Twitter v2 API, and INR budget-aware campaign management.
---

# Marketing Automation — GeoSupply Edition

> Upstream source: alirezarezvani/claude-skills · marketing-skill
> Adapted for: GeoSupply TwitterPublisher, ContentGenAgent, GeoRiskScore reports, ₹500/month budget

## GeoSupply Marketing Stack

```
ContentGenAgent      ← Generates intel briefs, summaries, reports
TwitterPublisher     ← Posts geo-risk alerts to Twitter/X v2 API
PredictionAgent      ← Forecasts supply chain disruption probabilities
AnalyticsAgent       ← Tracks engagement, reach, conversion metrics
NLAgent              ← Natural language interface for end-users
```

**Marketing budget**: Part of ₹500/month total cap — marketing spend must compete with LLM costs.

---

## 1. Content Strategy for Geopolitical Intel

### Content Types & Formats

| Type | Format | Twitter Thread? | Cost (INR) |
|------|--------|----------------|-----------|
| GeoRisk Alert | 280 chars + risk score | No | ₹0.05 |
| Supply Chain Brief | 3-tweet thread | Yes (3) | ₹0.15 |
| Weekly India Report | Long-form + PDF | No | ₹2.00 |
| Conflict Prediction | Chart + explanation | Yes (2) | ₹0.10 |
| Sanctions Update | Single tweet | No | ₹0.03 |

### Brand Voice for GeoSupply
```
Tone: Authoritative, neutral, data-driven
Style: Precise, factual, never alarmist
Audience: Supply chain managers, policy analysts, logistics teams
Geography: India-centric, global context
Language: English primary; Hindi summaries for India-specific reports
Avoid: Speculation without confidence score, partisan framing
Always include: Source attribution, confidence score, event date
```

---

## 2. Twitter/X v2 Integration

### TweetOutput Schema (Schema #18)
```python
class TweetOutput(BaseModel):
    schema_version: int = 1
    tweet_id: str | None = None        # Set after posting
    content: str                        # Max 280 chars
    thread_tweets: list[str] = []      # For threads
    geo_risk_ref: str | None = None    # GeoRiskScore.event_id
    confidence_score: float            # Must be >= HALLUCINATION_FLOOR
    source_attribution: str
    posted_at: datetime | None = None
    engagement_metrics: dict = {}
```

### TwitterPublisher Worker Pattern
```python
class TwitterPublisherWorker(BaseWorker):
    name = "twitter_publisher"
    tier = LLMTier.CPU_ONLY   # No LLM — direct API call
    capabilities = ["publish_tweet", "publish_thread", "fetch_metrics"]

    @breaker  # Required for all external API calls
    async def _post_tweet(self, content: str) -> str:
        """Post tweet via Twitter v2 API. Returns tweet_id."""
        key = self.security_agent.get_key("twitter_bearer_token")
        # ... httpx call to api.twitter.com/2/tweets
```

### Rate Limit Management
```python
TWITTER_RATE_LIMITS = {
    "tweets_per_15min":  300,   # v2 free tier
    "tweets_per_day":    2400,
    "reads_per_15min":   15,
}
# Use @rate_limiter decorator to auto-throttle
```

---

## 3. AI SEO / GEO / LLMO Strategy

GeoSupply content should be optimized for **AI-generated answers** (not traditional search):

```markdown
## AI Answer Optimization Rules
1. Every report starts with a 1-sentence bottom line answer
2. Include structured data: dates, percentages, country codes, commodity names
3. Use entity-rich language: "India's eastern port of Vishakhapatnam" not "a port"
4. Every claim cites source + credibility score
5. Include explicit confidence: "High confidence (0.87): ..." or "Medium (0.72): ..."
6. Use FAQ format in weekly reports — AI models retrieve FAQ pairs well
7. Include ISO country codes, UNSC resolution numbers, trade codes where relevant
```

---

## 4. Content Generation Prompts (ContentGenAgent)

### GeoRisk Alert Template
```python
GEORISK_ALERT_TEMPLATE = """
Generate a factual 280-character geopolitical risk alert.
Risk: {risk_type} | Region: {region} | Score: {risk_score}/10
Key facts: {key_facts}
Sources: {sources} (credibility: {avg_credibility:.2f})
Confidence: {confidence:.2f}

Rules:
- No speculation beyond provided facts
- Include risk score explicitly
- Cite primary source
- Neutral tone, no alarmism
- End with relevant hashtags: #SupplyChain #GeoRisk #{region}
"""
```

### Weekly India Supply Chain Report
```python
INDIA_REPORT_TEMPLATE = """
Write a structured weekly supply chain intelligence report for India.
Format: Bottom Line → Regional Analysis → Sector Risks → Forecasts → Sources
Data: {aggregated_intel}
Confidence floor: 0.70 (exclude any claim below this)
Length: 600-800 words
Include: Monsoon impact, port status, sanctions alerts, conflict zones
Language: English, with key stats in Hindi parenthetical where appropriate
"""
```

---

## 5. Prediction & Analytics

### PredictionRecord Schema (Schema #19)
```python
class PredictionRecord(BaseModel):
    schema_version: int = 1
    prediction_id: str
    event_type: str              # "supply_disruption", "conflict_escalation"
    region: str
    probability: float           # 0.0–1.0
    confidence: float            # Must be >= HALLUCINATION_FLOOR (0.70)
    horizon_days: int            # Prediction window
    model_version: str           # XGBoost model version
    features_used: list[str]
    predicted_at: datetime
```

### Campaign Analytics Targets
```python
ANALYTICS_TARGETS = {
    "twitter_impressions_weekly": 5_000,
    "engagement_rate": 0.03,        # 3% minimum
    "follower_growth_monthly": 100,
    "report_downloads_monthly": 50,
    "india_audience_pct": 0.60,     # 60% India-based audience
}
```

---

## 6. INR Budget Allocation for Marketing

```python
# Monthly marketing spend targets (within ₹500 total cap)
MARKETING_BUDGET_INR = {
    "content_generation": 30.0,    # ContentGenAgent LLM calls
    "twitter_api":         0.0,    # Free tier
    "report_synthesis":   20.0,    # BriefSynthSubAgent for reports
    "email_platform":      0.0,    # SendGrid free tier (100/day)
    "total_cap":          50.0,    # Max 10% of ₹500 total
}
```

---

## 7. Content Quality Checklist

Before publishing any content:
- [ ] Confidence score ≥ 0.70 (HALLUCINATION_FLOOR)
- [ ] Source attribution included
- [ ] No hardcoded API keys in publishing code
- [ ] Tweet content ≤ 280 characters (or thread properly split)
- [ ] TweetOutput schema validated by Pydantic
- [ ] Cost tracked in meta.cost_inr
- [ ] @breaker applied to Twitter API call
- [ ] Rate limit check before posting

---

## Related Skills
- `supply-chain-analyst` — Intel that feeds ContentGenAgent
- `india-intel` — India-specific content sourcing
- `budget-controller` — Marketing spend stays within ₹500 cap
- `portal-designer` — Analytics dashboard for marketing metrics

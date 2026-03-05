# Chapter 20: Marketing & Revenue Agent — Twitter, Predictions, Monetisation

## Design Philosophy

> **GeoSupply generates intelligence. Intelligence has value. The MarketingAgent turns that value into revenue and reach.**

---

## Marketing Agent Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│               MARKETING & REVENUE AGENT LAYER (NEW v9)          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                  MarketingSupervisor                    │     │
│  │  Content calendar, approval queue, revenue tracking     │     │
│  └────────────────────────┬───────────────────────────────┘     │
│                           │                                      │
│  ┌───────────┐  ┌────────┴────────┐  ┌───────────────────┐     │
│  │ Content   │  │ Twitter/X       │  │ Revenue           │     │
│  │ Generator │  │ Publisher       │  │ Tracker           │     │
│  │ Agent     │  │ Agent           │  │ Agent             │     │
│  └─────┬─────┘  └────────┬────────┘  └─────────┬─────────┘     │
│        │                  │                      │               │
│  ┌─────┴─────┐  ┌────────┴────────┐  ┌─────────┴─────────┐     │
│  │ Prediction│  │ Newsletter      │  │ Analytics         │     │
│  │ Agent     │  │ Agent           │  │ Agent             │     │
│  └───────────┘  └─────────────────┘  └───────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## ContentGeneratorAgent

```python
class ContentGeneratorAgent(BaseAgent):
    """
    Generates publishable content from GeoSupply intelligence.

    CONTENT TYPES:
        1. PREDICTION TWEETS
           "🚨 GeoSupply AI predicts 73% chance of Suez Canal
            disruption in next 14 days. INR impact: +2.3% on
            crude imports. #SupplyChain #Geopolitics"

        2. INSIGHT THREADS
           5-7 tweet thread summarising weekly intelligence:
           - Top 3 geopolitical risks this week
           - Supply chain stress index changes
           - India-specific trade flow updates

        3. BREAKING NEWS ALERTS
           When pipeline detects high-significance event:
           "⚡ BREAKING: LAC tension spike detected. India-China
            bilateral trade at 30-day low. Monitoring..."

        4. DATA VISUALISATIONS
           Auto-generated charts/maps from dashboard data:
           - Country risk heatmaps
           - Supply chain stress timelines
           - Monsoon vs port delay correlation plots

        5. WEEKLY DIGEST
           Longer-form summary for newsletter/blog:
           - 10 key intelligence findings
           - Prediction accuracy scorecard
           - Next week outlook

    QUALITY CONTROLS:
        - FactCheckAgent verifies ALL claims before publish
        - No classified/NDA data in public content
        - Confidence floor: only publish predictions >0.75
        - Human approval queue for sensitive geopolitical content
        - All costs tracked in INR
    """
    name = "ContentGeneratorAgent"
    domain = "marketing"

    CONTENT_TEMPLATES = {
        "prediction_tweet": {
            "max_chars": 280,
            "must_include": ["confidence_%", "timeframe", "impact"],
            "hashtags": ["#SupplyChain", "#Geopolitics", "#India"],
            "fact_check": True,
            "approval_required": False,  # Auto-publish if confidence >0.75
        },
        "insight_thread": {
            "max_tweets": 7,
            "must_include": ["data_source", "confidence"],
            "frequency": "weekly",
            "fact_check": True,
            "approval_required": True,  # Human reviews thread
        },
        "breaking_alert": {
            "max_chars": 280,
            "urgency": "high",
            "fact_check": True,
            "approval_required": True,  # ALWAYS human-approved
        },
    }

    async def generate_prediction_tweet(self, prediction: dict) -> str:
        """Generate a tweet from a pipeline prediction."""
        if prediction['confidence'] < 0.75:
            return None  # Don't publish low-confidence predictions

        tweet = await moe_gate.call(
            task_type="CONTENT_GENERATE",
            prompt=f"""Generate a concise tweet (max 280 chars) about:
            Event: {prediction['event']}
            Probability: {prediction['confidence']*100:.0f}%
            Timeframe: {prediction['timeframe']}
            Impact: {prediction['impact']}
            Include relevant hashtags. Be factual, not sensational.
            All monetary values in INR.""",
            schema=TweetOutput
        )

        # FactCheck before publishing
        fact_result = await FactCheckAgent().verify([{"claim": tweet.text}])
        if fact_result['status'] != 'passed':
            return None  # Don't publish unverified content

        return tweet.text
```

---

## TwitterPublisherAgent

```python
class TwitterPublisherAgent(BaseAgent):
    """
    Manages the @GeoSupplyAI Twitter/X account.

    PUBLISHING STRATEGY:
        DAILY (autonomous, confidence >0.75):
            - 2-3 prediction tweets (morning IST, evening IST)
            - 1 data visualisation
            - Retweet relevant geopolitical news

        WEEKLY (human-approved):
            - 1 insight thread (Monday morning IST)
            - 1 prediction accuracy scorecard
            - 1 India supply chain update

        BREAKING (human-approved, immediate):
            - High-significance events only
            - Pushed to approval queue
            - Admin approves via CLI or portal

    ENGAGEMENT TRACKING:
        Track per tweet: impressions, likes, retweets, replies
        Feed back to ContentGeneratorAgent:
            - Which content types perform best
            - Which hashtags drive engagement
            - Best posting times (IST-optimised)

    API:
        Twitter/X API v2 (Essential tier — free)
        Rate limits: 1,500 tweets/month (free tier)
        Read: 10,000 tweets/month
        SecurityAgent manages API keys
    """
    name = "TwitterPublisherAgent"
    domain = "marketing"

    POSTING_SCHEDULE = {
        "prediction_tweet": {"times": ["09:00 IST", "18:00 IST"], "auto": True},
        "data_viz":         {"times": ["12:00 IST"], "auto": True},
        "insight_thread":   {"times": ["09:00 IST Monday"], "auto": False},
        "breaking":         {"times": ["immediate"], "auto": False},
    }

    async def publish(self, content: str, content_type: str) -> dict:
        """Publish content to Twitter/X."""
        template = ContentGeneratorAgent.CONTENT_TEMPLATES[content_type]

        if template['approval_required']:
            # Queue for human approval
            await self._queue_for_approval(content, content_type)
            return {"status": "queued_for_approval"}

        # Auto-publish
        result = await self._post_to_twitter(content)
        LoggingAgent().log("twitter_publish", content_type=content_type,
                          tweet_id=result.tweet_id, cost_inr=0)
        return {"status": "published", "tweet_id": result.tweet_id}
```

---

## PredictionAgent — Publishable Forecasts

```python
class PredictionAgent(BaseAgent):
    """
    Generates market-ready predictions from GeoSupply intelligence.

    PREDICTION CATEGORIES:
        1. GEOPOLITICAL RISK
           "73% chance of Suez disruption in 14 days"
           Source: ConflictPredictor + KnowledgeGraph

        2. SUPPLY CHAIN STRESS
           "Indian port utilisation to hit 95% in monsoon season"
           Source: MonsoonWorker + StressWorker + IMD data

        3. TRADE FLOW CHANGES
           "India-China bilateral trade down 12% if LAC tension > 7.0"
           Source: GeoRiskScore + TradeMatrix + KnowledgeGraph

        4. COMMODITY PRICE IMPACT
           "Crude import cost for India: +₹2,340 crore if Persian Gulf disrupted"
           Source: StressWorker + RBI forex data

    ACCURACY TRACKING:
        Every prediction logged with:
            - Prediction text + confidence
            - Target date (when prediction should resolve)
            - Actual outcome (filled in when target date passes)
            - Accuracy score (was prediction correct?)

        Monthly accuracy scorecard:
            - Overall accuracy %
            - Accuracy by category
            - Calibration curve (are 70% predictions right 70% of the time?)

        Published monthly: "Our predictions were 78% accurate last month"
    """
    name = "PredictionAgent"
    domain = "marketing"
```

---

## Revenue Model — Monetisation Strategy

```
TIER 1 — FREE (Twitter/X public posts)
    ├── 2-3 daily prediction tweets
    ├── Weekly insight threads
    ├── Breaking news alerts
    ├── Monthly accuracy scorecard
    └── PURPOSE: build audience, establish credibility

TIER 2 — NEWSLETTER (Free, email-gated)
    ├── Weekly intelligence digest
    ├── Deeper analysis than Twitter
    ├── India-specific supply chain insights
    ├── Prediction performance tracking
    └── PURPOSE: build email list, direct relationship

TIER 3 — PREMIUM API (Future — INR-denominated pricing)
    ├── Real-time intelligence API
    ├── Custom query endpoint
    ├── GeoRiskScore API for specific countries
    ├── Supply chain stress index API
    ├── Pricing: ₹500/month for 1,000 queries
    └── PURPOSE: direct revenue from B2B customers

TIER 4 — CONSULTING (Future — Human-augmented)
    ├── Custom intelligence reports
    ├── Supply chain risk assessment
    ├── Geopolitical briefings for corporates
    ├── India market entry intelligence
    └── PURPOSE: high-value revenue, portfolio showcase

REVENUE TRACKING:
    RevenueTrackerAgent tracks:
        - Twitter follower growth
        - Newsletter subscriber count
        - API subscription MRR (monthly recurring revenue) in INR
        - Content engagement metrics
        - Prediction accuracy impact on growth
    All revenue metrics in INR — never USD.
```

---

## Content Approval Workflow

```
FULLY AUTONOMOUS (no human needed):
    ✅ Prediction tweets (confidence >0.75, FactChecked)
    ✅ Data visualisations
    ✅ Engagement responses (likes, retweets)
    ✅ Scheduled posts from content calendar

HUMAN APPROVAL REQUIRED:
    ❌ Insight threads (geopoliticial sensitivity)
    ❌ Breaking news alerts (reputational risk)
    ❌ Content mentioning specific countries/leaders
    ❌ Content with military/defense implications
    ❌ Any content with confidence 0.70-0.75 (borderline)

ADMIN COMMAND:
    geosupply marketing queue         → view pending approvals
    geosupply marketing approve <id>  → approve for publish
    geosupply marketing reject <id>   → reject with reason
    geosupply marketing stats         → engagement metrics
    geosupply marketing revenue       → revenue dashboard
```

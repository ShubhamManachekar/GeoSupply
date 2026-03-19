---
name: financial-analyst
description: INR-denominated financial analysis for GeoSupply — cost tracking, budget variance, LLM spend projections, ROI analysis, and SaaS metrics. All figures in INR. Never USD.
---

# Financial Analyst — GeoSupply INR Edition

> Upstream source: alirezarezvani/claude-skills · finance
> Adapted for: GeoSupply ₹500/month budget cap, INR cost tracking, LLM spend modelling

## GeoSupply Financial Architecture

```
BudgetManagerAgent  ← Real-time INR spend tracking per agent/worker
CostProjection      ← Schema #24: forward-looking spend estimates
CostWorker (v10)    ← Aggregates costs from all tiers
AnalyticsAgent      ← Revenue and ROI tracking
```

**Golden Rule**: ALL costs in INR. Never return, display, or store USD values. BANNED in code.

---

## 1. Cost Model by LLM Tier

```python
# Approximate costs (INR) — update when model pricing changes
COST_PER_1K_TOKENS_INR = {
    LLMTier.CPU_ONLY:    0.000,   # No LLM — pure compute
    LLMTier.SMALL_3B:    0.000,   # Local Ollama — zero API cost
    LLMTier.MEDIUM_14B:  0.004,   # Local Ollama qwen2.5:14b — ~₹0.004/1K
    LLMTier.LARGE_20B:   0.082,   # GPT-OSS:20b via Groq — ~₹0.082/1K tokens
}

# Embedding costs
EMBEDDING_COST_INR = {
    "local_sentence_transformers": 0.000,
    "text-embedding-ada-002":      0.083,  # ₹0.083/1K tokens (~$0.001)
}

# External API costs
API_COST_INR = {
    "newsapi":    0.0,    # Free tier
    "acled":      0.0,    # Free for research
    "telegram":   0.0,    # Free
    "aisstream":  0.0,    # Free tier
    "shodan":     415.0,  # ~$5/month → ₹415
    "groq_llm":   83.0,   # Estimated ₹83/month at current usage
}
```

---

## 2. Monthly Budget Variance Analysis

```python
# Budget caps from config.py
BUDGET_CAP_INR          = 500.0    # Monthly hard cap
ALERT_WARN_DAILY_INR    = 250.0    # Warn at ₹250/day
ALERT_CRITICAL_DAILY_INR = 270.0   # Critical at ₹270/day

# Budget allocation recommendation
BUDGET_ALLOCATION = {
    "tier3_llm_calls":      300.0,   # 60% → Groq GPT-OSS:20b
    "external_data_apis":   150.0,   # 30% → Shodan + premium feeds
    "marketing_content":     50.0,   # 10% → ContentGen LLM calls
    "reserve":                0.0,   # No reserve needed (₹500 cap is hard)
}
```

### Variance Report Format
```markdown
## GeoSupply Monthly Budget Report — {month}

| Category | Budget (₹) | Actual (₹) | Variance | Status |
|----------|-----------|-----------|---------|--------|
| Tier-3 LLM | 300 | {actual} | {var} | 🟢/🟡/🔴 |
| External APIs | 150 | {actual} | {var} | 🟢/🟡/🔴 |
| Marketing | 50 | {actual} | {var} | 🟢/🟡/🔴 |
| **TOTAL** | **500** | **{total}** | **{total_var}** | **{status}** |

### Alert Thresholds Hit This Month
- Warn (₹250/day): {warn_count} times
- Critical (₹270/day): {critical_count} times

### Top Cost Drivers
1. {driver_1}: ₹{cost_1} ({pct_1}% of budget)
2. {driver_2}: ₹{cost_2} ({pct_2}% of budget)
```

---

## 3. LLM Cost Projection Model

```python
# CostProjection schema (Schema #24)
class CostProjection(BaseModel):
    schema_version: int = 1
    projection_id: str
    period_days: int
    tier_breakdown: dict[str, float]   # {"LARGE_20B": 245.0, "MEDIUM_14B": 12.0}
    total_projected_inr: float
    budget_remaining_inr: float
    burn_rate_inr_per_day: float
    days_until_exhaustion: float | None
    confidence: float
    generated_at: datetime

# Usage in BudgetManagerAgent:
async def project_spend(self) -> CostProjection:
    daily_rate = self._total_spent_inr / self._days_elapsed
    remaining = BUDGET_CAP_INR - self._total_spent_inr
    days_left = remaining / daily_rate if daily_rate > 0 else None
    return CostProjection(
        burn_rate_inr_per_day=daily_rate,
        days_until_exhaustion=days_left,
        total_projected_inr=daily_rate * 30,
        ...
    )
```

---

## 4. ROI Analysis Framework

### GeoSupply Revenue Streams (Planned)
```python
REVENUE_STREAMS = {
    "api_subscriptions": {
        "tier": "basic",
        "price_inr_monthly": 2990,
        "features": ["risk_scores", "alerts"],
    },
    "premium_reports": {
        "price_inr_per_report": 499,
        "reports_per_month_target": 20,
    },
    "enterprise_api": {
        "price_inr_monthly": 29900,
        "custom_dashboards": True,
    },
}

# Break-even analysis
MONTHLY_COSTS_INR = 500  # Infrastructure cap
BREAK_EVEN_SUBSCRIBERS = ceil(500 / 2990 * 100)  # ~1 basic subscriber!
```

### SaaS Metrics to Track
```python
SAAS_METRICS = {
    "MRR":          "Monthly Recurring Revenue (₹)",
    "ARR":          "Annual Run Rate (₹)",
    "CAC":          "Customer Acquisition Cost (₹)",
    "LTV":          "Customer Lifetime Value (₹)",
    "churn_rate":   "Monthly churn %",
    "NPS":          "Net Promoter Score",
    "API_calls":    "Daily API calls (usage metric)",
}
```

---

## 5. Cost Tracking Code Pattern

```python
# Every worker/agent process() must track cost:
async def process(self, input_data: dict) -> dict:
    start_tokens = 0
    result = await self._call_llm(prompt)
    tokens_used = result.usage.total_tokens
    cost_inr = (tokens_used / 1000) * COST_PER_1K_TOKENS_INR[self.tier]

    # Always report in meta
    return {
        "result": result.content,
        "meta": {
            "cost_inr": cost_inr,        # REQUIRED
            "tokens_used": tokens_used,
            "tier": self.tier.value,
            "trace_id": self.trace_id,
        }
    }
```

---

## 6. Budget Alerts Implementation

```python
class BudgetManagerAgent(BaseAgent):
    async def check_and_alert(self, spend_inr: float) -> None:
        daily_total = await self._get_daily_total()
        if daily_total >= COST_ALERT_CRITICAL_DAILY_INR:  # ₹270
            await self.event_bus.publish("budget.critical", ...)
            await self._block_tier3_calls()  # Hard stop on Tier-3
        elif daily_total >= COST_ALERT_WARN_DAILY_INR:     # ₹250
            await self.event_bus.publish("budget.warn", ...)
            # Tier-3 allowed but logged with HIGH priority
```

---

## Related Skills
- `budget-controller` — Real-time budget enforcement patterns
- `portal-designer` — Cost visualization dashboard
- `marketing-automation` — Marketing spend within overall budget
- `swarm-orchestrator` — SwarmMaster budget gate for task routing

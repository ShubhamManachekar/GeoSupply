---
name: india-intel
description: India-specific intelligence gathering for GeoSupply — government APIs (ULIP, data.gov.in), monsoon impact modelling, regional political risk, port status, internal conflict zones, and multilingual NLP for Indian languages.
---

# India Intelligence — IndiaIntelWorker & MonsoonWorker

> Custom GeoSupply skill — India-centric supply chain intelligence

## Why India-First?

GeoSupply is **India-centric by design**. 60% of supply chain risks affecting the platform's target customers originate from within India:
- Monsoon disruptions → agricultural supply + logistics
- Internal political events → state-level policy changes
- Port congestion (JNPT, Mundra, Chennai) → import/export delays
- Regulatory changes → customs, GST, export restrictions
- Regional conflicts → Northeast, J&K, border states

---

## 1. India Government APIs (ULIP + data.gov.in)

```python
# Key APIs (all accessible via IndiaAPIWorker)
INDIA_APIS = {
    "ulip": {
        "base_url": "https://www.ulip.dpiit.gov.in/ulip",
        "auth": "api_key",  # Via SecurityAgent.get_key("ulip_api_key")
        "endpoints": {
            "port_status":      "/v1.0.0/get_port_status",
            "freight_rates":    "/v1.0.0/get_freight_rates",
            "customs_data":     "/v1.0.0/get_customs_data",
            "vehicle_tracking": "/v1.0.0/get_vehicle_tracking",
        },
        "rate_limit": "100 req/hour",
        "cost": "Free (government API)",
    },
    "data_gov_in": {
        "base_url": "https://api.data.gov.in",
        "auth": "api_key",
        "datasets": {
            "rainfall":         "rainfall-data-district-level",
            "agri_prices":      "current-daily-price-commodity",
            "port_traffic":     "major-port-traffic",
            "road_accidents":   "road-accident-data",
        },
    },
    "india_wris": {
        "base_url": "https://indiawris.gov.in/wris",
        "purpose": "Water resource + reservoir levels (monsoon proxy)",
    },
}
```

---

## 2. MonsoonWorker — Monsoon Impact Model

```python
class MonsoonWorker(BaseWorker):
    """
    Monsoon impact assessment for Indian agricultural supply chains.
    Uses IMD (India Meteorological Department) data + district-level rainfall.
    Tier: CPU_ONLY (statistical model, no LLM)
    """
    name = "monsoon"
    tier = LLMTier.CPU_ONLY
    capabilities = ["monsoon_risk_score", "crop_impact_forecast", "logistics_disruption_index"]

    MONSOON_SEASON = (6, 9)   # June–September (months)
    DEFICIT_THRESHOLD = -20   # % below normal → supply disruption risk
    EXCESS_THRESHOLD  = +25   # % above normal → flood/logistics risk

    async def process(self, input_data: dict) -> dict:
        """
        Input: {"district": "Nashik", "commodity": "onion", "date": "2026-06"}
        Output: {"monsoon_risk": 0.72, "impact_type": "deficit", "affected_crops": [...]}
        """
        rainfall = await self._fetch_rainfall_data(input_data["district"])
        deviation = self._calculate_deviation(rainfall)

        if deviation < self.DEFICIT_THRESHOLD:
            risk_score = abs(deviation) / 100   # Normalize to 0–1
            impact_type = "deficit"
        elif deviation > self.EXCESS_THRESHOLD:
            risk_score = deviation / 100
            impact_type = "excess"
        else:
            risk_score = 0.10   # Baseline risk
            impact_type = "normal"

        return {
            "result": {
                "monsoon_risk": risk_score,
                "impact_type": impact_type,
                "district": input_data["district"],
                "deviation_pct": deviation,
            },
            "meta": {"cost_inr": 0.0, "source": "imd_api"}
        }
```

---

## 3. IndiaIntelWorker — India-Specific Event Intelligence

```python
class IndiaIntelWorker(BaseWorker):
    """
    India-specific geopolitical and regulatory intelligence aggregator.
    Sources: PIB (Press Information Bureau), Lok Sabha alerts, state news agencies.
    Tier: SMALL_3B (event extraction from structured govt. text)
    """
    name = "india_intel"
    tier = LLMTier.SMALL_3B
    capabilities = ["regulatory_alert", "port_status", "state_risk_score", "election_risk"]

    INDIA_SOURCES = [
        "https://pib.gov.in/rss/rss.aspx",           # Press Information Bureau RSS
        "https://commerce.gov.in/press-releases/",   # Commerce Ministry
        "https://pmindia.gov.in/en/news-updates/",   # PMO news
    ]

    INDIA_RISK_REGIONS = {
        "J&K":        {"base_risk": 0.65, "factors": ["border_tension", "political"]},
        "Manipur":    {"base_risk": 0.55, "factors": ["ethnic_conflict"]},
        "Naxal_belt": {"base_risk": 0.45, "factors": ["LWE", "mining_disruption"]},
        "Northeast":  {"base_risk": 0.35, "factors": ["political", "border"]},
        "Punjab":     {"base_risk": 0.20, "factors": ["political", "agri_protests"]},
    }
```

---

## 4. Multilingual NLP for India

```python
# Language detection and routing
INDIA_LANGUAGES = {
    "hi": "Hindi",      # 500M speakers — critical for north India intel
    "bn": "Bengali",    # West Bengal, Bangladesh border
    "te": "Telugu",     # Andhra Pradesh, Telangana supply hubs
    "ta": "Tamil",      # Chennai port, Tamil Nadu manufacturing
    "mr": "Marathi",    # Mumbai, Pune industrial belt
    "gu": "Gujarati",   # GIFT City, Surat, Ahmedabad
    "kn": "Kannada",    # Bengaluru tech + manufacturing
    "ur": "Urdu",       # J&K, border region sources
}

# TranslationWorker routing for India languages
INDIA_NLP_PIPELINE = [
    "language_detection",   # LanguageWorker (CPU_ONLY)
    "translation_to_en",    # TranslationWorker (Tier-2: multilingual-e5)
    "sentiment",            # SentimentWorker (Tier-1 STATIC)
    "ner",                  # NERWorker (Tier-1 STATIC) — extract locations, orgs
    "claim",                # ClaimWorker (Tier-1 STATIC) — extract factual claims
]

# Special NER entity types for India
INDIA_NER_TYPES = [
    "INDIAN_STATE",     # Maharashtra, Gujarat, etc.
    "INDIAN_DISTRICT",  # District-level granularity
    "INDIAN_PORT",      # JNPT, Mundra, Chennai, Vizag, Kolkata
    "INDIAN_MINISTRY",  # Commerce, Finance, External Affairs
    "INDIAN_ACT",       # GST, FEMA, SEBI regulations
    "COMMODITY_CODE",   # HSN codes for customs data
]
```

---

## 5. India Supply Chain Risk Scoring

```python
# Regional risk score components
INDIA_RISK_COMPONENTS = {
    "monsoon_deviation":    0.25,   # Rainfall vs normal
    "port_congestion":      0.20,   # JNPT/Mundra/Chennai dwell time
    "political_events":     0.20,   # Elections, protests, bandhs
    "regulatory_changes":   0.15,   # New export/import restrictions
    "internal_conflict":    0.10,   # Naxal, ethnic, communal incidents
    "infrastructure":       0.10,   # Road/rail/power disruptions
}

# Key thresholds
INDIA_RISK_THRESHOLDS = {
    "LOW":      (0.0, 0.30),
    "MEDIUM":   (0.30, 0.55),
    "HIGH":     (0.55, 0.75),
    "CRITICAL": (0.75, 1.0),
}
```

---

## 6. Data Sources Reference

| Source | Data Type | Update Frequency | API? | Cost |
|--------|-----------|-----------------|------|------|
| IMD (imd.gov.in) | Rainfall, weather | Daily | No (scrape) | Free |
| ULIP | Port, freight, logistics | Real-time | Yes | Free |
| data.gov.in | 300+ govt datasets | Variable | Yes | Free |
| PIB | Government press releases | Real-time | RSS | Free |
| ACLED | Conflict events | Weekly | Yes | Free |
| PRS Legislative | Bills, debates, acts | Real-time | No (scrape) | Free |
| NSE/BSE | Market signals | Real-time | Yes | Free tier |
| Rajya Sabha | Parliamentary alerts | Session-based | RSS | Free |

---

## 7. India-Specific Schemas

```python
# Extend GeoRiskScore for India granularity
class IndiaRiskScore(BaseModel):
    schema_version: int = 1
    state: str
    district: str | None = None    # Sub-state granularity
    overall_risk: float            # 0.0–1.0
    monsoon_risk: float
    political_risk: float
    logistics_risk: float
    regulatory_risk: float
    top_risk_factors: list[str]
    port_status: dict | None       # Nearest major port
    next_election_days: int | None # Days to next state election
    assessed_at: datetime
```

---

## Related Skills
- `supply-chain-analyst` — India risk feeds into supplier scoring
- `rag-architect` — India intel stored in ChromaDB india_specific collection
- `knowledge-graph` — India entities stored as KG nodes
- `marketing-automation` — India weekly report publishing

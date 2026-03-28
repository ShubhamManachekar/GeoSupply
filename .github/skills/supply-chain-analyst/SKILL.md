---
name: supply-chain-analyst
description: Supply chain stress analysis, supplier scoring, sanctions screening, and disruption risk modelling for GeoSupply. Covers SupplierScore, SanctionsOutput, StressWorker, XGBoost conflict model, and Platt-scaled risk scores.
---

# Supply Chain Analyst — GeoSupply Risk Engine

> Custom GeoSupply skill — Layer 5 supply chain workers + ML risk models

## Supply Chain Intelligence Stack

```
Layer 5 Workers:
  StressWorker       ← Overall supply chain stress index
  SupplierWorker     ← Per-supplier risk scoring (Tier-1 STATIC)
  SanctionsWorker    ← OFAC/UN/EU sanctions screening (Tier-1 STATIC)

Layer 3 Agents:
  RouteManagerAgent  ← Alternative route suggestions
  TimelineGeneratorAgent ← Event timeline for disruption analysis

ML Layer (isolated from LLMs):
  ConflictWorker     ← XGBoost conflict prediction
  RetrainWorker      ← Model drift detection + retraining trigger
  DriftWorker        ← Feature drift monitoring
```

---

## 1. SupplierScore Schema (Schema #13)

```python
class SupplierScore(BaseModel):
    schema_version: int = 1
    supplier_id: str
    supplier_name: str
    country: str          # ISO-3 country code
    region: str           # Sub-national region
    overall_score: float  # 0.0–1.0 (1.0 = highest risk)
    sanctions_hit: bool
    geo_risk: float       # From GeoRiskScore
    logistics_risk: float # Port/route accessibility
    financial_risk: float # Estimated payment/insolvency risk
    political_risk: float # Country/region political instability
    monsoon_risk: float   # India-specific (0.0 if non-India)
    confidence: float     # Must be >= HALLUCINATION_FLOOR
    last_assessed: datetime
    next_review_date: datetime
    risk_factors: list[str]
    recommended_action: Literal["MONITOR", "DUAL_SOURCE", "REPLACE", "BLOCK"]
```

---

## 2. SupplierWorker Implementation Pattern

```python
class SupplierWorker(BaseWorker):
    """
    Supplier risk scorer — Tier-1 STATIC decoder.
    Aggregates geo risk, sanctions, logistics, and financial signals.
    Cost: ₹0.001 per supplier assessment (Tier-1 local LLM).
    """
    name = "supplier"
    tier = LLMTier.SMALL_3B
    use_static = True   # MANDATORY for Tier-1 schema-strict workers
    capabilities = ["score_supplier", "bulk_assess", "flag_high_risk"]

    RISK_WEIGHTS = {
        "sanctions_hit":    1.00,   # Instant BLOCK if True
        "geo_risk":         0.30,
        "logistics_risk":   0.25,
        "political_risk":   0.25,
        "financial_risk":   0.15,
        "monsoon_risk":     0.05,   # India suppliers only
    }

    async def process(self, input_data: dict) -> dict:
        supplier = input_data["supplier"]

        # 1. Sanctions check first (instant BLOCK)
        sanctions = await self._check_sanctions(supplier)
        if sanctions.hit:
            return self._build_result(
                supplier, sanctions_hit=True,
                recommended_action="BLOCK",
                ...
            )

        # 2. Aggregate risk scores from upstream workers
        geo = input_data.get("geo_risk_score", 0.30)
        logistics = await self._assess_logistics(supplier)
        political = input_data.get("political_risk", 0.25)
        financial = await self._assess_financial(supplier)
        monsoon = input_data.get("monsoon_risk", 0.0)

        # 3. Weighted score
        score = (
            geo      * self.RISK_WEIGHTS["geo_risk"] +
            logistics* self.RISK_WEIGHTS["logistics_risk"] +
            political* self.RISK_WEIGHTS["political_risk"] +
            financial* self.RISK_WEIGHTS["financial_risk"] +
            monsoon  * self.RISK_WEIGHTS["monsoon_risk"]
        )

        action = self._recommended_action(score, sanctions.hit)
        return {"result": SupplierScore(...).model_dump(), "meta": {"cost_inr": 0.001}}
```

---

## 3. SanctionsWorker — OFAC/UN/EU Screening

```python
class SanctionsWorker(BaseWorker):
    """
    Real-time sanctions screening against OFAC SDN, UN Consolidated, EU lists.
    Tier-1 STATIC — schema-strict, zero hallucination risk.
    """
    name = "sanctions"
    tier = LLMTier.SMALL_3B
    use_static = True

    SANCTIONS_LISTS = {
        "ofac_sdn":     "https://sanctionslistservice.ofac.treas.gov/api/PublishedLists/download?format=CSV&type=SDN",
        "un_consolidated": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        "eu_consolidated": "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content",
    }

    # Cache sanctions lists (refresh every 6 hours)
    CACHE_TTL_SECONDS = 21600

    # Matching thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    FUZZY_MATCH_THRESHOLD = 0.85    # Flag for human review
    AUTO_BLOCK_THRESHOLD = 0.95

    async def process(self, input_data: dict) -> dict:
        """
        Input: {"entity_name": "...", "entity_type": "PERSON|ORG|VESSEL"}
        Output: SanctionsOutput schema
        """
        entity = input_data["entity_name"]
        entity_type = input_data.get("entity_type", "ORG")

        results = []
        for list_name, list_data in self._cached_lists.items():
            match = self._fuzzy_match(entity, list_data, entity_type)
            if match["score"] >= self.FUZZY_MATCH_THRESHOLD:
                results.append({
                    "list": list_name,
                    "matched_entity": match["name"],
                    "score": match["score"],
                    "designation": match.get("designation"),
                })

        hit = any(r["score"] >= self.AUTO_BLOCK_THRESHOLD for r in results)
        return {
            "result": SanctionsOutput(
                entity_name=entity,
                sanctions_hit=hit,
                matches=results,
                confidence=max((r["score"] for r in results), default=0.0),
                screened_at=datetime.now(timezone.utc),
            ).model_dump(),
            "meta": {"cost_inr": 0.0}   # CPU_ONLY matching, no LLM
        }
```

---

## 4. XGBoost Conflict Prediction (ConflictWorker)

```python
class ConflictWorker(BaseWorker):
    """
    XGBoost-based conflict risk prediction.
    ISOLATED from LLMs per architecture rule #6.
    Uses Platt scaling for calibrated probability output.
    """
    name = "conflict"
    tier = LLMTier.CPU_ONLY   # Pure ML, no LLM

    # Features used by XGBoost model
    FEATURE_SET = [
        "gdp_per_capita",           # Economic indicator
        "political_stability_index",# World Bank WGI
        "conflict_history_12m",     # ACLED event count
        "ethnic_fractionalization",  # Fearon & Laitin index
        "rainfall_deviation_pct",   # Monsoon proxy (India)
        "election_days_ahead",      # Electoral cycle
        "border_tension_score",     # LoC, LAC incidents
        "inflation_rate",           # Economic stress
    ]

    async def process(self, input_data: dict) -> dict:
        features = self._extract_features(input_data)
        raw_prob = self._model.predict_proba([features])[0][1]
        calibrated_prob = self._platt_scaler.predict_proba([[raw_prob]])[0][1]

        return {
            "result": {
                "conflict_probability": calibrated_prob,
                "horizon_days": input_data.get("horizon_days", 90),
                "region": input_data["region"],
                "feature_importances": dict(zip(
                    self.FEATURE_SET,
                    self._model.feature_importances_
                )),
            },
            "meta": {"cost_inr": 0.0, "model_version": self._model_version}
        }
```

---

## 5. Supply Chain Stress Index

```python
# StressWorker aggregates all signals into a unified stress index
STRESS_INDEX_COMPONENTS = {
    "conflict_probability":   0.25,   # ConflictWorker output
    "supplier_avg_risk":      0.20,   # Average SupplierScore
    "sanctions_exposure":     0.20,   # Count of sanctioned suppliers
    "logistics_bottleneck":   0.15,   # Port dwell times, AIS congestion
    "monsoon_impact":         0.10,   # MonsoonWorker output
    "market_volatility":      0.10,   # Commodity price swings
}

# Alert thresholds
STRESS_THRESHOLDS = {
    "GREEN":   (0.0,  0.30),   # Normal operations
    "AMBER":   (0.30, 0.55),   # Activate contingency planning
    "RED":     (0.55, 0.75),   # Dual-source critical suppliers
    "CRIMSON": (0.75, 1.0),    # Activate disaster recovery plan
}
```

---

## 6. Route Manager Integration

```python
# RouteManagerAgent provides alternative routing when stress is HIGH/CRITICAL
ALTERNATIVE_ROUTES = {
    "JNPT_blocked": [
        {"port": "Mundra", "delay_days": 3, "cost_premium_pct": 8},
        {"port": "Hazira", "delay_days": 5, "cost_premium_pct": 12},
    ],
    "Suez_disrupted": [
        {"route": "Cape_of_Good_Hope", "delay_days": 14, "cost_premium_pct": 35},
        {"route": "Trans_Siberian_rail", "delay_days": 21, "cost_premium_pct": 20},
    ],
    "China_sanctions": [
        {"supplier_country": "Vietnam", "lead_time_days": 30},
        {"supplier_country": "India_domestic", "lead_time_days": 10},
    ],
}
```

---

## Related Skills
- `india-intel` — India-specific risk inputs (monsoon, political)
- `knowledge-graph` — Supplier entities stored in KG
- `rag-architect` — Sanctions list retrieval via ChromaDB
- `financial-analyst` — Cost impact of supply disruptions
- `marketing-automation` — Publishing supply chain risk alerts

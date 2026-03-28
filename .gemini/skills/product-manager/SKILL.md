---
name: product-manager
description: Product strategy, roadmap, user stories, and OKRs for GeoSupply AI platform. Covers portal UX, API product design, customer personas, and RICE prioritization for the supply chain intelligence product.
---

# Product Manager — GeoSupply AI Platform

> Upstream source: alirezarezvani/claude-skills · product-team
> Adapted for: GeoSupply portal, API product, India supply chain market, ₹500/month infrastructure

## Product Vision

**GeoSupply AI**: The most cost-efficient geopolitical supply chain intelligence platform for India-exposed businesses, powered by a transparent multi-agent swarm with real-time risk scoring.

**Unique Value**: Enterprise-grade intel at ₹2,990/month (vs ₹50,000+ for Bloomberg/Refinitiv).

---

## 1. Customer Personas

### Persona 1: The Supply Chain Manager (Primary)
```
Name: Priya Sharma
Role: Head of Procurement, mid-sized Indian manufacturer
Pain: "I find out about port closures 3 days too late"
Goal: Real-time alerts for supply disruptions affecting my 12 suppliers
Willingness to pay: ₹2,990/month
Tech savvy: Medium — uses dashboards, not APIs
Key metric: Time-to-awareness for supply disruptions (target: <2 hours)
```

### Persona 2: The Policy Analyst
```
Name: Rahul Menon
Role: Senior Analyst, policy think-tank
Pain: "Aggregating geopolitical signals across 50 sources takes days"
Goal: Automated weekly briefings with source attribution
Willingness to pay: ₹499/report or ₹9,990/month
Tech savvy: High — comfortable with APIs
Key metric: Source coverage breadth, confidence score visibility
```

### Persona 3: The Risk Manager
```
Name: Aditya Kumar
Role: Chief Risk Officer, logistics company
Pain: "My current tool doesn't cover India's internal political risk"
Goal: India-specific risk scores with Tier-2/3 city granularity
Willingness to pay: ₹29,900/month (enterprise)
Tech savvy: Low — needs Streamlit portal, not API
Key metric: Risk score accuracy (backtesting vs actual events)
```

---

## 2. Product Roadmap (RICE Prioritized)

```markdown
## Q1 2026 (Now) — Foundation
| Feature | Reach | Impact | Confidence | Effort | RICE Score |
|---------|-------|--------|-----------|--------|-----------|
| Core worker pipeline (news + NLP) | 3 | 9 | 80% | 3 | 720 |
| Risk score API endpoint | 2 | 8 | 70% | 4 | 280 |
| Basic Streamlit portal | 2 | 7 | 60% | 3 | 280 |

## Q2 2026 — Intelligence Layer
| Feature | RICE Score | Status |
|---------|-----------|--------|
| GraphRAG knowledge base | 640 | Planned |
| India-specific intel workers | 580 | Planned |
| Twitter alert publishing | 320 | Planned |
| Weekly India report PDF | 280 | Planned |

## Q3 2026 — Monetization
| Feature | RICE Score | Status |
|---------|-----------|--------|
| Subscription billing (Razorpay) | 720 | Planned |
| API key management | 560 | Planned |
| Enterprise dashboard | 480 | Planned |
| White-label reports | 240 | Planned |
```

---

## 3. OKR Framework

```markdown
## Q1 2026 OKRs

**Objective 1: Ship production-ready intelligence pipeline**
- KR1: 80%+ test coverage on all implemented workers
- KR2: Pipeline processes 1000 articles/day without manual intervention
- KR3: Zero critical security findings in LoopholeHunter audit

**Objective 2: Establish product-market fit signal**
- KR1: 5 beta users actively using portal weekly
- KR2: NPS >= 40 from beta users
- KR3: 1 paid customer at any price point

**Objective 3: Stay within infrastructure budget**
- KR1: Monthly LLM spend <= ₹500
- KR2: Zero API key exposures in security audit
- KR3: P95 pipeline latency < 12 minutes
```

---

## 4. User Stories (Portal)

### Admin Portal (Layer 0)
```
As an admin, I want to see real-time agent health status
  so that I can identify bottlenecks before they cause SLA breaches.
  Acceptance: Dashboard shows IDLE/BUSY/ERROR state for all 8 agents.
  Cost: HealthCheckAgent already implemented — just surface via Streamlit.

As an admin, I want to override any agent's output manually
  so that I can correct errors in real-time.
  Acceptance: Override logged to OverrideRecord schema, HMAC signed.
  Security: Requires portal:admin JWT scope.

As an admin, I want to see daily INR spend breakdown
  so that I can prevent budget overruns.
  Acceptance: Chart shows spend by tier (Tier-1/2/3/external APIs).
```

### End User Portal
```
As a supply chain manager, I want to receive risk alerts filtered by my supplier regions
  so that I only see relevant intelligence.
  Acceptance: Alert UI shows region filter, risk score, confidence, source.

As a policy analyst, I want to export weekly briefs as PDF
  so that I can share them with my team without portal access.
  Acceptance: PDF includes source attribution, confidence scores, event timeline.
```

---

## 5. API Product Design

### Core Endpoints (Target)
```yaml
GET  /v1/risk-score/{region}
  → GeoRiskScore schema
  → Auth: Bearer JWT (portal:read scope)
  → Rate limit: 100/hour (free), 1000/hour (paid)

GET  /v1/events?region={r}&from={date}&to={date}
  → list[GeoEventRecord]
  → Supports filtering by event_type, confidence_floor

POST /v1/alerts/subscribe
  → Subscribe to webhook for region risk alerts
  → Payload: {webhook_url, regions[], risk_threshold, confidence_floor}

GET  /v1/supply-chain/stress/{supplier_id}
  → SupplierScore schema
  → Includes sanctions check, geopolitical exposure score
```

### API Versioning Policy
```
/v1/ — Current stable (maintain for 12 months after /v2/ launch)
/v2/ — Next version (breaking changes go here, never in /v1/)
Deprecation: 90-day notice before removing any endpoint
```

---

## 6. Product Quality Gates

Before any feature ships to beta:
- [ ] User story has clear acceptance criteria
- [ ] Corresponding Pydantic schema exists and is validated
- [ ] Feature has ≥ 85% test coverage
- [ ] INR cost tracked per API call
- [ ] Security audit passed (no new LoopholeFinding)
- [ ] P95 latency measured and within SLA (12 min for pipeline)
- [ ] Rate limiting applied to all endpoints
- [ ] Admin portal reflects new feature in health dashboard

---

## Related Skills
- `portal-designer` — Streamlit implementation for user stories
- `financial-analyst` — Pricing, ROI, SaaS metrics
- `marketing-automation` — Go-to-market and content strategy
- `c-level-advisor` — Strategic decisions on product direction

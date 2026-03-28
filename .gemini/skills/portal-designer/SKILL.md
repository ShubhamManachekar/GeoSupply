---
name: portal-designer
description: Streamlit portal design and implementation for GeoSupply — admin dashboard, supply chain risk maps, cost visualization, agent health monitoring, override management, and end-user intelligence portal.
---

# Portal Designer — GeoSupply Streamlit Dashboard

> Custom GeoSupply skill — Layer 0 admin portal + end-user intelligence portal

## Portal Architecture

```
GeoSupply Portal (Streamlit)
  ├── Admin Portal (Layer 0)
  │   ├── Agent Health Monitor
  │   ├── Budget Dashboard
  │   ├── Override Manager
  │   ├── Audit Log Viewer
  │   └── System Controls
  └── Intelligence Portal (End Users)
      ├── Risk Score Dashboard
      ├── Supply Chain Map (India)
      ├── Supplier Risk Table
      ├── Weekly Report Viewer
      └── Alert Feed
```

**Auth**: JWT tokens (`portal:read` for users, `portal:admin` for admin)
**Framework**: Streamlit >= 1.30.0
**Location**: `src/geosupply/portal/`

---

## 1. App Structure

```python
# src/geosupply/portal/app.py — main entry point

import streamlit as st
from geosupply.portal.pages import (
    admin_health, admin_budget, admin_overrides,
    intel_risk_map, intel_suppliers, intel_alerts
)
from geosupply.portal.auth import verify_jwt_token

st.set_page_config(
    page_title="GeoSupply AI",
    page_icon="🌏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auth gate
token = st.session_state.get("jwt_token")
if not token or not verify_jwt_token(token):
    _show_login_page()
    st.stop()

# Role-based routing
scopes = st.session_state.get("jwt_scopes", [])
if "portal:admin" in scopes:
    _render_admin_sidebar()
else:
    _render_user_sidebar()
```

---

## 2. Admin Portal Pages

### Agent Health Monitor (`admin_health.py`)
```python
def render_health_page(health_agent):
    st.title("🤖 Agent Health Monitor")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Agents", "8/8", delta="0")
    with col2:
        st.metric("Pipeline SLA", "8.3 min", delta="-1.2 min", delta_color="normal")
    with col3:
        st.metric("Tasks/Hour", "142", delta="+12")
    with col4:
        st.metric("Error Rate", "0.7%", delta="-0.2%", delta_color="inverse")

    # Agent state table
    health_data = asyncio.run(health_agent.execute("check_all", {}))
    df = pd.DataFrame([
        {
            "Agent": name,
            "State": info["state"],
            "Last Seen": info["last_seen"],
            "Tasks Done": info["tasks_done"],
            "Cost (₹)": f"₹{info['cost_inr']:.2f}",
        }
        for name, info in health_data["result"]["agents"].items()
    ])

    def color_state(val):
        colors = {"IDLE": "green", "BUSY": "blue", "ERROR": "red", "RECOVERY": "orange"}
        return f"color: {colors.get(val, 'black')}"

    st.dataframe(df.style.applymap(color_state, subset=["State"]), use_container_width=True)
```

### Budget Dashboard (`admin_budget.py`)
```python
def render_budget_page(budget_agent):
    st.title("💰 Budget Dashboard")

    status = asyncio.run(budget_agent.execute("get_status", {}))["result"]
    projection = asyncio.run(budget_agent.execute("get_projection", {}))["result"]

    # Gauge: monthly burn
    monthly_pct = (status["monthly_spend_inr"] / 500) * 100
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Monthly Spend",
            f"₹{status['monthly_spend_inr']:.2f}",
            delta=f"₹{500 - status['monthly_spend_inr']:.2f} remaining",
        )
        st.progress(monthly_pct / 100, text=f"{monthly_pct:.1f}% of ₹500 cap")

    with col2:
        if projection["days_until_exhaustion"]:
            st.metric("Days Until Cap", f"{projection['days_until_exhaustion']:.0f} days")
        st.metric("Burn Rate", f"₹{projection['burn_rate_inr_per_day']:.2f}/day")

    # Tier breakdown bar chart
    tier_data = status["spend_by_tier"]
    if tier_data:
        st.bar_chart(tier_data)

    # Alert banner
    if status["tier3_blocked"]:
        st.error("🚨 Tier-3 calls BLOCKED — daily critical threshold exceeded")
    elif status["daily_spend_inr"] >= 250:
        st.warning("⚠️ Daily spend warning threshold reached")
```

---

## 3. Intelligence Portal Pages

### Risk Score Dashboard (`intel_risk_map.py`)
```python
def render_risk_map():
    st.title("🌏 India Supply Chain Risk Map")

    # Region filter
    selected_regions = st.multiselect(
        "Filter Regions",
        options=list(INDIA_RISK_REGIONS.keys()),
        default=list(INDIA_RISK_REGIONS.keys()),
    )

    # Risk score cards
    cols = st.columns(3)
    for i, region in enumerate(selected_regions[:6]):
        with cols[i % 3]:
            score = _get_region_risk_score(region)
            color = "🟢" if score < 0.3 else "🟡" if score < 0.55 else "🔴"
            st.metric(
                f"{color} {region}",
                f"{score:.0%} risk",
                help=f"Composite risk score for {region}",
            )

    # India map (plotly choropleth)
    st.plotly_chart(_build_india_choropleth(selected_regions), use_container_width=True)
```

### Supplier Risk Table (`intel_suppliers.py`)
```python
def render_supplier_table():
    st.title("🏭 Supplier Risk Assessment")

    # Search + filter
    search = st.text_input("Search supplier name")
    action_filter = st.selectbox("Filter by recommendation", ["ALL", "MONITOR", "DUAL_SOURCE", "REPLACE", "BLOCK"])

    suppliers = _get_supplier_scores(search=search, action=action_filter)

    # Color-coded table
    df = pd.DataFrame(suppliers)
    action_colors = {
        "MONITOR":    "background-color: #d4edda",
        "DUAL_SOURCE":"background-color: #fff3cd",
        "REPLACE":    "background-color: #f8d7da",
        "BLOCK":      "background-color: #842029; color: white",
    }

    def highlight_action(row):
        return [action_colors.get(row["recommended_action"], "")] * len(row)

    st.dataframe(
        df.style.apply(highlight_action, axis=1),
        use_container_width=True,
        height=400,
    )

    # Export
    if st.button("Export to CSV"):
        st.download_button("Download CSV", df.to_csv(index=False), "suppliers.csv")
```

---

## 4. Override Manager (`admin_overrides.py`)

```python
def render_overrides_page(override_agent):
    st.title("⚙️ Manual Overrides")
    st.warning("All overrides are logged, HMAC-signed, and reviewed by LoopholeHunter.")

    # Recent override history
    st.subheader("Recent Overrides")
    overrides = asyncio.run(override_agent.execute("list_recent", {"limit": 20}))["result"]
    st.dataframe(pd.DataFrame(overrides), use_container_width=True)

    # New override (admin:portal scope required)
    st.subheader("Submit Override")
    with st.form("override_form"):
        action = st.selectbox("Override Action", [
            "force_approve_spend",
            "retrigger_worker",
            "clear_circuit_breaker",
            "escalate_task_priority",
        ])
        reason = st.text_area("Reason (required)", max_chars=500)
        submitted = st.form_submit_button("Submit Override")
        if submitted:
            if not reason.strip():
                st.error("Reason is required for all overrides")
            else:
                result = asyncio.run(override_agent.execute("submit", {
                    "action": action, "reason": reason,
                    "admin_jwt": st.session_state["jwt_token"],
                }))
                st.success(f"Override submitted: {result['override_id']}")
```

---

## 5. Streamlit Worker (`StreamlitWorker`)

```python
class StreamlitWorker(BaseWorker):
    """
    Prepares aggregated dashboard data for Streamlit portal.
    Tier: CPU_ONLY — just data aggregation, no LLM.
    """
    name = "streamlit"
    tier = LLMTier.CPU_ONLY

    async def process(self, input_data: dict) -> dict:
        view = input_data.get("view", "risk_overview")
        data_funcs = {
            "risk_overview":   self._aggregate_risk_data,
            "supplier_table":  self._aggregate_supplier_data,
            "budget_status":   self._aggregate_budget_data,
            "agent_health":    self._aggregate_health_data,
            "alert_feed":      self._aggregate_alert_data,
        }
        if view not in data_funcs:
            return self._error("VALIDATION", f"Unknown view: {view}", input_data)

        result = await data_funcs[view](input_data)
        return {"result": result, "meta": {"cost_inr": 0.0}}
```

---

## 6. Portal File Structure

```
src/geosupply/portal/
  ├── __init__.py
  ├── app.py              # Main Streamlit app
  ├── auth.py             # JWT verification, session management
  ├── pages/
  │   ├── admin_health.py
  │   ├── admin_budget.py
  │   ├── admin_overrides.py
  │   ├── admin_audit_log.py
  │   ├── intel_risk_map.py
  │   ├── intel_suppliers.py
  │   ├── intel_alerts.py
  │   └── intel_reports.py
  ├── components/
  │   ├── risk_gauge.py   # Reusable risk score gauge
  │   ├── india_map.py    # Plotly India choropleth
  │   └── cost_chart.py   # Budget visualization components
  └── data/
      └── india_geojson.json   # India states GeoJSON for maps
```

---

## 7. Portal Launch

```bash
# Run portal (development)
PYTHONPATH=src streamlit run src/geosupply/portal/app.py \
  --server.port 8501 \
  --server.address 0.0.0.0
```

---

## Related Skills
- `budget-controller` — Budget data displayed in admin portal
- `product-manager` — User stories driving portal features
- `india-intel` — India risk map data source
- `supply-chain-analyst` — Supplier table data source

#!/usr/bin/env python3
"""
GeoSupply AI — Streamlit Admin Dashboard

Multi-page admin control panel with:
  • Overview     — Live swarm health, budget gauge, quick actions
  • Logs         — Filterable, paginated log viewer with cost chart
  • Supervisors  — Enable/disable supervisors, reset circuit breakers
  • Workers      — Runtime config overrides per worker, tier view
  • Budget       — Per-agent cost breakdown, daily burn chart
  • API Explorer — Browse & test all API routes from the browser

Start:
    geosupply-dashboard
    streamlit run src/geosupply/dashboard/admin_dashboard.py

Env vars (inherits from shell or .env):
    GEOSUPPLY_API_URL   — default http://localhost:8000
    ADMIN_API_KEY       — default "dev-key"
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────
_API = os.getenv("GEOSUPPLY_API_URL", "http://localhost:8000").rstrip("/")
_KEY = os.getenv("ADMIN_API_KEY", "@Shitguy27")

st.set_page_config(
    page_title="GeoSupply Admin",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── API helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3)
def _get(path: str, **params) -> dict | None:
    try:
        import httpx
        r = httpx.get(
            f"{_API}{path}",
            headers={"X-Admin-Key": _KEY},
            params=params,
            timeout=10.0,
        )
        if r.status_code == 200:
            return r.json()
        return {"_error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as exc:
        return {"_error": str(exc)}


def _post(path: str, body: dict | None = None) -> dict | None:
    try:
        import httpx
        r = httpx.post(
            f"{_API}{path}",
            headers={"X-Admin-Key": _KEY, "Content-Type": "application/json"},
            json=body or {},
            timeout=10.0,
        )
        _get.clear()  # bust cache after mutations
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


def _patch(path: str, body: dict) -> dict | None:
    try:
        import httpx
        r = httpx.patch(
            f"{_API}{path}",
            headers={"X-Admin-Key": _KEY, "Content-Type": "application/json"},
            json=body,
            timeout=10.0,
        )
        _get.clear()
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


def _delete(path: str) -> dict | None:
    try:
        import httpx
        r = httpx.delete(
            f"{_API}{path}",
            headers={"X-Admin-Key": _KEY},
            timeout=10.0,
        )
        _get.clear()
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


def _api_error(data: dict | None) -> str | None:
    if data is None:
        return "No response from API"
    return data.get("_error")


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=60)
    st.title("GeoSupply Admin")
    st.caption(f"API: `{_API}`")

    page = st.radio(
        "Navigate",
        ["🏠 Overview", "📋 Logs", "🔧 Supervisors", "⚙️ Workers",
         "💰 Budget", "🗺️ API Explorer"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Settings")
    api_url = st.text_input("API URL", value=_API)
    admin_key = st.text_input("Admin Key", value=_KEY, type="password")
    if api_url != _API or admin_key != _KEY:
        os.environ["GEOSUPPLY_API_URL"] = api_url
        os.environ["ADMIN_API_KEY"] = admin_key
        _API = api_url.rstrip("/")
        _KEY = admin_key
        _get.clear()

    if st.button("🔄 Refresh All", use_container_width=True):
        _get.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Overview
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Overview":
    st.title("🏠 Swarm Overview")
    status = _get("/admin/status")
    err = _api_error(status)

    if err:
        st.error(f"Cannot reach API — {err}")
        st.info(f"Make sure the GeoSupply API is running: `uvicorn geosupply.api.main:app --port 8000`")
        st.stop()

    swarm = status.get("swarm", {})
    env = status.get("env", {})
    budget = status.get("budget", {})
    sqlite = status.get("sqlite", {})

    # ── Top metrics ────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Supervisors", swarm.get("supervisor_count", 0))
    c2.metric("Workers", swarm.get("worker_count", 0))
    c3.metric("Agents", swarm.get("agent_count", 0))
    c4.metric("Log Entries", sqlite.get("log_count", 0))
    cap = 500.0
    reserved = budget.get("reserved_inr", 0.0) or 0.0
    c5.metric("Budget Used", f"₹{reserved:.2f}", f"of ₹{cap:.0f}")

    # ── Service status pills ───────────────────────────────────────────────────
    st.subheader("Service Status")
    cols = st.columns(6)
    services = [
        ("API", True),
        ("SQLite", sqlite.get("ok", False)),
        ("Anthropic", env.get("anthropic_api", False)),
        ("Neo4j", env.get("neo4j", False)),
        ("Supabase", env.get("supabase", False)),
        ("Admin Key", env.get("admin_key_set", False)),
    ]
    for col, (label, ok) in zip(cols, services):
        color = "green" if ok else "red"
        icon = "✅" if ok else "❌"
        col.markdown(f":{color}[{icon} **{label}**]")

    # ── Budget progress ────────────────────────────────────────────────────────
    st.subheader("Budget")
    pct = min(1.0, reserved / cap) if cap else 0.0
    bar_color = "green" if pct < 0.6 else "orange" if pct < 0.85 else "red"
    st.progress(pct, text=f"₹{reserved:.2f} / ₹{cap:.2f} ({pct*100:.1f}%)")

    # ── Supervisor state grid ──────────────────────────────────────────────────
    st.subheader("Supervisor State")
    supers_data = status.get("supervisors", {})
    if supers_data:
        import pandas as pd
        rows = []
        for name, s in supers_data.items():
            rows.append({
                "Supervisor": name,
                "Enabled": "✅" if s["enabled"] else "🔴",
                "Breaker": "🔴 OPEN" if s["breaker_open"] else "🟢 CLOSED",
                "Failures": s["breaker_failures"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Quick actions ──────────────────────────────────────────────────────────
    st.subheader("Quick Actions")
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("🔄 Reset All Circuit Breakers", use_container_width=True):
            for name in supers_data:
                _post(f"/admin/supervisors/{name}/circuit-breaker/reset")
            st.success("All circuit breakers reset")
            st.rerun()
    with q2:
        if st.button("🧹 Reset Daily Budget Counter", use_container_width=True):
            result = _post("/admin/budget/reset")
            if result and not result.get("_error"):
                st.success("Budget counter reset")
    with q3:
        if st.button("📊 Run Audit Check", use_container_width=True):
            r = _get("/audit/run?categories=breakage,logic")
            if r:
                st.success(f"Audit: {r.get('passed', 0)} passed, {r.get('failed', 0)} failed")

    st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} — auto-refreshes every 10s")
    time.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Logs
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Logs":
    st.title("📋 Swarm Logs")

    # Filters
    f1, f2, f3, f4, f5 = st.columns([2, 2, 1, 1, 1])
    with f1:
        agent_filter = st.text_input("Agent name filter", placeholder="e.g. VerifierWorker")
    with f2:
        level_filter = st.selectbox("Level", ["", "INFO", "WARNING", "ERROR", "DEBUG"])
    with f3:
        since_filter = st.selectbox("Time window", [0, 5, 15, 30, 60, 360, 1440],
                                    format_func=lambda x: "All" if x == 0 else f"Last {x}m")
    with f4:
        limit = st.selectbox("Show", [50, 100, 250, 500, 1000])
    with f5:
        order = st.selectbox("Order", ["desc", "asc"])

    params: dict[str, Any] = {"limit": limit, "order": order}
    if agent_filter:
        params["agent_name"] = agent_filter
    if level_filter:
        params["level"] = level_filter
    if since_filter:
        params["since_minutes"] = since_filter

    data = _get("/admin/logs", **params)
    err = _api_error(data)
    if err:
        st.error(err)
    else:
        entries = data.get("entries", [])
        total = data.get("total", 0)
        st.caption(f"Showing {len(entries)} of {total} total log entries")

        if entries:
            import pandas as pd

            df = pd.DataFrame(entries)
            df["timestamp"] = df["timestamp"].str[:19].str.replace("T", " ")
            df["cost_inr"] = df["cost_inr"].round(6)

            # Cost chart
            if "cost_inr" in df.columns and df["cost_inr"].sum() > 0:
                cost_by_agent = (
                    df.groupby("agent")["cost_inr"].sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                st.subheader("Cost by Agent (visible window)")
                st.bar_chart(cost_by_agent)

            st.subheader("Log Entries")
            st.dataframe(
                df[["timestamp", "agent", "level", "message", "cost_inr", "trace_id"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "cost_inr": st.column_config.NumberColumn("Cost ₹", format="₹%.6f"),
                    "message": st.column_config.TextColumn("Message", width="large"),
                },
            )
        else:
            st.info("No log entries match the current filters.")

    # Manual refresh
    if st.button("🔄 Refresh Logs"):
        _get.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Supervisors
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔧 Supervisors":
    st.title("🔧 Supervisor Control")

    data = _get("/admin/supervisors")
    err = _api_error(data)
    if err:
        st.error(err)
        st.stop()

    supervisors = data.get("supervisors", [])
    st.caption(f"{len(supervisors)} supervisors registered")

    for sup in supervisors:
        name = sup["name"]
        enabled = sup["enabled"]
        breaker_open = sup["breaker_open"]
        failures = sup["breaker_failures"]
        agents = sup.get("agents", [])

        status_icon = "✅" if enabled else "🔴"
        breaker_icon = "🔴 OPEN" if breaker_open else "🟢 CLOSED"

        with st.expander(f"{status_icon} **{name}** — {sup['agent_count']} agents | Breaker: {breaker_icon} | Failures: {failures}"):
            c1, c2, c3 = st.columns([1, 1, 3])
            with c1:
                toggle_label = "Disable" if enabled else "Enable"
                if st.button(f"{'🔴 ' if enabled else '🟢 '}{toggle_label}", key=f"toggle_{name}"):
                    result = _post(f"/admin/supervisors/{name}/toggle")
                    if result and not result.get("_error"):
                        action = result.get("action", "toggled")
                        st.success(f"{name} {action}")
                        _get.clear()
                        st.rerun()
            with c2:
                if st.button("🔄 Reset Breaker", key=f"reset_{name}", disabled=not breaker_open and failures == 0):
                    result = _post(f"/admin/supervisors/{name}/circuit-breaker/reset")
                    if result and not result.get("_error"):
                        st.success(f"Breaker reset (was {result.get('previous_failures', 0)} failures)")
                        _get.clear()
                        st.rerun()
            with c3:
                if agents:
                    st.caption("Agents: " + ", ".join(agents))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Workers
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "⚙️ Workers":
    st.title("⚙️ Worker Configuration")

    data = _get("/admin/workers")
    err = _api_error(data)
    if err:
        st.error(err)
        st.stop()

    workers = data.get("workers", [])

    # Summary by tier
    from collections import Counter
    tier_counts = Counter(w["tier"] for w in workers)
    t_cols = st.columns(4)
    for i, (tier, label) in enumerate([(0, "CPU"), (1, "3B"), (2, "14B"), (3, "20B")]):
        t_cols[i].metric(f"Tier-{tier} ({label})", tier_counts.get(tier, 0))

    # Routing table
    with st.expander("📍 Routing Table"):
        rt_data = _get("/admin/routing-table")
        if rt_data and not rt_data.get("_error"):
            import pandas as pd
            st.dataframe(
                pd.DataFrame(rt_data.get("routing_table", [])),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.subheader("Worker Details & Overrides")

    tier_filter = st.selectbox("Filter by tier", ["All", "Tier-0 CPU", "Tier-1 3B", "Tier-2 14B", "Tier-3 20B"])
    tier_map = {"All": None, "Tier-0 CPU": 0, "Tier-1 3B": 1, "Tier-2 14B": 2, "Tier-3 20B": 3}
    tier_selected = tier_map[tier_filter]

    for worker in workers:
        if tier_selected is not None and worker["tier"] != tier_selected:
            continue

        name = worker["name"]
        tier = worker["tier"]
        tier_labels = {0: "CPU", 1: "3B", 2: "14B", 3: "20B"}
        tier_colors = {0: "gray", 1: "blue", 2: "orange", 3: "violet"}
        override_active = worker.get("overrides_active", False)
        caps = ", ".join(worker["capabilities"][:4])

        with st.expander(
            f"{'⚡ ' if override_active else ''}**{name}** "
            f"[Tier-{tier} {tier_labels.get(tier, '')}] {caps}"
        ):
            c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
            new_retries = c1.number_input("Max Retries", value=worker["max_retries"],
                                          min_value=0, max_value=10, key=f"ret_{name}")
            new_timeout = c2.number_input("Timeout (s)", value=worker["timeout_seconds"],
                                          min_value=5, max_value=300, key=f"to_{name}")
            new_tier = c3.selectbox("Tier Override", [0, 1, 2, 3],
                                    index=worker["tier"], key=f"tier_{name}",
                                    format_func=lambda x: f"Tier-{x}")

            with c4:
                st.write("")
                st.write("")
                if st.button("Apply", key=f"apply_{name}"):
                    patch: dict[str, Any] = {}
                    if new_retries != worker["max_retries"]:
                        patch["max_retries"] = new_retries
                    if new_timeout != worker["timeout_seconds"]:
                        patch["timeout_seconds"] = new_timeout
                    if new_tier != worker["tier_original"]:
                        patch["tier_override"] = new_tier
                    if patch:
                        result = _patch(f"/admin/workers/{name}", patch)
                        if result and not result.get("_error"):
                            st.success(f"Applied: {result.get('applied', {})}")
                            st.rerun()
                    else:
                        st.info("No changes to apply")

            if override_active:
                if st.button("🗑 Clear Overrides", key=f"clear_{name}"):
                    _delete(f"/admin/workers/{name}/overrides")
                    st.success("Overrides cleared")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Budget
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "💰 Budget":
    st.title("💰 Budget & Cost Tracking")

    data = _get("/admin/budget")
    err = _api_error(data)
    if err:
        st.error(err)
        st.stop()

    summary = data.get("summary", {})
    cap = data.get("cap_inr", 500.0)
    reserved = summary.get("reserved_inr", 0.0) or 0.0
    remaining = summary.get("remaining_inr", cap) or cap
    pct = min(1.0, reserved / cap) if cap else 0.0

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Budget Cap", f"₹{cap:.2f}")
    m2.metric("Spent", f"₹{reserved:.4f}")
    m3.metric("Remaining", f"₹{remaining:.4f}")
    m4.metric("Utilisation", f"{pct*100:.1f}%")

    color = "green" if pct < 0.6 else "orange" if pct < 0.85 else "red"
    st.progress(pct)

    # Daily series chart
    daily = data.get("daily_series", [])
    if daily:
        import pandas as pd
        st.subheader("Daily Spend (INR)")
        df_daily = pd.DataFrame(daily).set_index("date").sort_index()
        st.bar_chart(df_daily["cost_inr"])

    # Per-agent table
    per_agent = data.get("per_agent", [])
    if per_agent:
        st.subheader("Cost by Agent")
        import pandas as pd
        df_agent = pd.DataFrame(per_agent)
        df_agent["total_cost_inr"] = df_agent["total_cost_inr"].round(6)
        st.dataframe(
            df_agent,
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_cost_inr": st.column_config.NumberColumn("Total Cost ₹", format="₹%.6f"),
                "call_count": st.column_config.NumberColumn("Calls"),
            },
        )

        # Agent cost bar chart
        st.subheader("Agent Cost Distribution")
        df_chart = df_agent.set_index("agent")["total_cost_inr"].head(15)
        st.bar_chart(df_chart)

    st.divider()
    st.subheader("Actions")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("🔄 Reset Daily Counter", type="secondary"):
            result = _post("/admin/budget/reset")
            if result and not result.get("_error"):
                st.success("Daily budget counter reset")
                st.rerun()
    with a2:
        with st.expander("⚠️ Override Budget Cap (Elevated)"):
            new_cap = st.number_input("New cap (₹)", min_value=10.0, max_value=50000.0, value=cap, step=100.0)
            reason = st.text_input("Reason for override")
            elevated_key = st.text_input("Elevated Key", type="password")
            if st.button("Apply Override"):
                try:
                    import httpx
                    r = httpx.post(
                        f"{_API}/admin/budget/override",
                        headers={"X-Admin-Key": elevated_key},
                        json={"new_cap_inr": new_cap, "reason": reason},
                        timeout=10.0,
                    )
                    if r.status_code == 200:
                        st.success(f"Budget cap updated to ₹{new_cap:.2f}")
                    else:
                        st.error(f"{r.status_code}: {r.text}")
                except Exception as exc:
                    st.error(str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: API Explorer
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🗺️ API Explorer":
    st.title("🗺️ API Explorer")
    st.caption(f"Base URL: `{_API}` — Click a route to test it")

    data = _get("/admin/api-directory")
    err = _api_error(data)
    if err:
        st.error(err)
        st.stop()

    routes = data.get("routes", [])

    # Filters
    f1, f2 = st.columns([2, 2])
    with f1:
        tag_options = sorted({tag for r in routes for tag in r.get("tags", [])})
        tag_filter = st.selectbox("Filter by tag", ["(all)"] + tag_options)
    with f2:
        method_filter = st.selectbox("Method", ["(all)", "GET", "POST", "PATCH", "DELETE"])

    filtered = [
        r for r in routes
        if (tag_filter == "(all)" or tag_filter in r.get("tags", []))
        and (method_filter == "(all)" or method_filter in r.get("methods", []))
    ]

    st.caption(f"Showing {len(filtered)} of {len(routes)} routes")

    # Group by tag
    from collections import defaultdict
    by_tag: dict[str, list] = defaultdict(list)
    for r in filtered:
        tags = r.get("tags", ["untagged"])
        by_tag[tags[0] if tags else "untagged"].append(r)

    method_colors = {
        "GET": "green", "POST": "blue", "PATCH": "orange", "DELETE": "red"
    }

    for tag, tag_routes in sorted(by_tag.items()):
        with st.expander(f"**{tag.upper()}** ({len(tag_routes)} routes)", expanded=tag in ["health", "admin"]):
            for route in tag_routes:
                methods = route.get("methods", ["GET"])
                path = route["path"]
                summary = route.get("summary", "")
                deprecated = route.get("deprecated", False)

                for method in methods:
                    color = method_colors.get(method, "gray")
                    badge = f":{color}[**{method}**]"
                    dep_label = " ~~deprecated~~" if deprecated else ""
                    with st.container():
                        rc1, rc2 = st.columns([4, 1])
                        with rc1:
                            st.markdown(f"{badge} `{path}`{dep_label}")
                            if summary:
                                st.caption(summary)
                        with rc2:
                            test_key = f"test_{method}_{path}"
                            if st.button("▶ Try", key=test_key):
                                st.session_state[f"active_route"] = {"method": method, "path": path}

            # ── Test panel ─────────────────────────────────────────────────────
            active = st.session_state.get("active_route")
            if active and any(
                r["path"] == active["path"] for r in tag_routes
            ):
                st.divider()
                st.markdown(f"**Testing:** `{active['method']} {active['path']}`")
                method = active["method"]
                path = active["path"]

                # Fill path params
                import re
                path_params = re.findall(r"\{(\w+)\}", path)
                filled_path = path
                for param in path_params:
                    val = st.text_input(f"Path param: `{{{param}}}`", key=f"pp_{param}_{path}")
                    filled_path = filled_path.replace(f"{{{param}}}", val)

                # Body for POST/PATCH
                body_str = ""
                if method in ("POST", "PATCH"):
                    body_str = st.text_area("Request body (JSON)", value="{}", height=100,
                                            key=f"body_{method}_{path}")

                # Query params
                qp_str = st.text_input("Query params (key=val&key2=val2)", value="",
                                       key=f"qp_{method}_{path}")

                if st.button("Send Request", key=f"send_{method}_{path}"):
                    import httpx
                    qparams: dict = {}
                    if qp_str:
                        for pair in qp_str.split("&"):
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                qparams[k.strip()] = v.strip()

                    try:
                        body = json.loads(body_str) if body_str and method in ("POST", "PATCH") else None
                        with httpx.Client(timeout=15.0) as client:
                            r = client.request(
                                method,
                                f"{_API}{filled_path}",
                                headers={"X-Admin-Key": _KEY, "Content-Type": "application/json"},
                                params=qparams,
                                json=body,
                            )
                        badge_color = "green" if r.status_code < 300 else "red"
                        st.markdown(f":{badge_color}[**{r.status_code} {r.reason_phrase}**]")
                        try:
                            st.json(r.json())
                        except Exception:
                            st.code(r.text)
                    except Exception as exc:
                        st.error(str(exc))


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """Console entrypoint — launches Streamlit programmatically."""
    import sys
    import subprocess
    dashboard_path = __file__
    sys.exit(subprocess.call(
        ["streamlit", "run", dashboard_path, "--server.headless", "true"],
        env={**os.environ},
    ))

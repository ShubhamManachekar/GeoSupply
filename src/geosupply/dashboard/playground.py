"""
GeoSupply AI — Live Execution Playground

A Streamlit app that lets you fire tasks at the swarm and watch execution
unfold in real-time — layer by layer, agent by agent, worker by worker.

Start:
    geosupply-playground
    streamlit run src/geosupply/dashboard/playground.py

Layout:
    ┌──────────────┬────────────────────────────┬─────────────────┐
    │   SIDEBAR    │      LIVE EVENT FEED        │  SWARM TOPOLOGY │
    │  Task form   │   (auto-polling SSE proxy)  │  Node/edge tree │
    │  Quick tasks │   Color-coded by layer      │  Agent states   │
    │  Active runs │   Cost & timing per step    │  Worker grid    │
    └──────────────┴────────────────────────────┴─────────────────┘
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

import streamlit as st

_API = os.getenv("GEOSUPPLY_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="GeoSupply Playground",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Layer styling ─────────────────────────────────────────────────────────────
LAYER_COLOR = {
    "swarm":      "#6C63FF",   # purple
    "supervisor": "#F7971E",   # orange
    "agent":      "#00B4DB",   # cyan
    "worker":     "#56AB2F",   # green
    "subagent":   "#E91E63",   # pink
    "bus":        "#888888",   # grey (heartbeat)
}
LAYER_ICON = {
    "swarm":      "🌐",
    "supervisor": "🏗️",
    "agent":      "🤖",
    "worker":     "⚙️",
    "subagent":   "🔬",
    "bus":        "💓",
}
STATUS_ICON = {
    "running": "🔄",
    "ok":      "✅",
    "error":   "❌",
    "skipped": "⏭️",
    "blocked": "🚫",
}
EVENT_TYPE_BADGE = {
    "start":        "▶",
    "complete":     "✓",
    "error":        "✗",
    "route":        "→",
    "routed":       "✓→",
    "dag_start":    "⏵",
    "dag_complete": "⏹",
    "state_change": "⚡",
    "heartbeat":    "♡",
    "submitted":    "📨",
    "brief_queued": "📋",
    "nlp_queued":   "🔤",
    "nlp_complete": "🔤✓",
}


# ── API helpers ───────────────────────────────────────────────────────────────

def _api_get(path: str, **params) -> dict | None:
    try:
        import httpx
        r = httpx.get(f"{_API}{path}", params=params, timeout=8.0)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _api_post(path: str, **params) -> dict | None:
    try:
        import httpx
        r = httpx.post(f"{_API}{path}", params=params, timeout=8.0)
        return r.json() if r.status_code in (200, 201, 202) else None
    except Exception:
        return None


def _api_post_json(path: str, body: dict, **params) -> dict | None:
    try:
        import httpx
        r = httpx.post(f"{_API}{path}", json=body, params=params, timeout=8.0)
        return r.json() if r.status_code in (200, 201, 202) else None
    except Exception:
        return None


# ── Session state init ────────────────────────────────────────────────────────
if "active_traces" not in st.session_state:
    st.session_state.active_traces: dict[str, dict] = {}  # trace_id → {events, last_seq, info}
if "selected_trace" not in st.session_state:
    st.session_state.selected_trace: str = ""
if "topology" not in st.session_state:
    st.session_state.topology = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚡ Playground")
    st.caption(f"API: `{_API}`")

    # ── API connectivity check ─────────────────────────────────────────────────
    health = _api_get("/health")
    if health and health.get("status") == "ok":
        st.success("API connected")
    else:
        st.error("Cannot reach API — start with `geosupply-api`")

    st.divider()
    st.subheader("🚀 Fire a Task")

    task_mode = st.radio("Mode", ["Quick NLP", "Any Task Type", "Full Supply Brief"],
                         label_visibility="collapsed")

    if task_mode == "Quick NLP":
        text_input = st.text_area("Text to analyse", height=100,
                                  placeholder="Paste a news article, tweet, or report…")
        if st.button("▶ Run NLP Pipeline", use_container_width=True, type="primary"):
            if text_input.strip():
                result = _api_post("/playground/run/nlp", text=text_input.strip())
                if result:
                    tid = result["trace_id"]
                    st.session_state.active_traces[tid] = {
                        "events": [], "last_seq": 0,
                        "info": f"NLP: {text_input[:40]}…",
                        "started_at": datetime.now().strftime("%H:%M:%S"),
                    }
                    st.session_state.selected_trace = tid
                    st.success(f"Trace `{tid}` started")
                    st.rerun()
            else:
                st.warning("Enter some text first")

    elif task_mode == "Any Task Type":
        topo = _api_get("/playground/routing-table")
        task_types = [r["task_type"] for r in (topo or {}).get("routing_table", [])]
        selected_type = st.selectbox("Task type", task_types or ["NLP_SENTIMENT"])
        payload_str = st.text_area("Payload (JSON)", value='{"text": "India wheat export ban"}',
                                   height=80)
        if st.button("▶ Run Task", use_container_width=True, type="primary"):
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                payload = {}
                st.warning("Invalid JSON payload — using empty dict")
            result = _api_post_json(
                "/playground/run",
                body=payload,
                task_type=selected_type,
            )
            if result:
                tid = result["trace_id"]
                st.session_state.active_traces[tid] = {
                    "events": [], "last_seq": 0,
                    "info": f"{selected_type}",
                    "started_at": datetime.now().strftime("%H:%M:%S"),
                }
                st.session_state.selected_trace = tid
                st.success(f"Trace `{tid}` started")
                st.rerun()

    elif task_mode == "Full Supply Brief":
        topic = st.text_input("Topic", placeholder="India wheat export ban 2025")
        cred = st.slider("Source credibility", 0.0, 1.0, 0.8, 0.05)
        if st.button("▶ Run Supply Brief DAG", use_container_width=True, type="primary"):
            if topic.strip():
                result = _api_post("/playground/run/supply-brief",
                                   topic=topic.strip(), source_credibility=cred)
                if result:
                    tid = result["trace_id"]
                    st.session_state.active_traces[tid] = {
                        "events": [], "last_seq": 0,
                        "info": f"Brief: {topic[:40]}",
                        "started_at": datetime.now().strftime("%H:%M:%S"),
                    }
                    st.session_state.selected_trace = tid
                    st.success(f"Trace `{tid}` started — {len(st.session_state.active_traces)} active")
                    st.rerun()
            else:
                st.warning("Enter a topic")

    st.divider()
    st.subheader("📂 Active Traces")
    if st.session_state.active_traces:
        for tid, info in list(st.session_state.active_traces.items()):
            event_count = len(info["events"])
            is_selected = tid == st.session_state.selected_trace
            label = f"{'▶ ' if is_selected else '  '}`{tid}` {info['info'][:20]} ({event_count} events)"
            if st.button(label, key=f"sel_{tid}", use_container_width=True):
                st.session_state.selected_trace = tid
                st.rerun()
        if st.button("🗑 Clear All Traces", use_container_width=True):
            st.session_state.active_traces.clear()
            st.session_state.selected_trace = ""
            st.rerun()
    else:
        st.caption("No active traces — fire a task above")

    st.divider()
    auto_refresh = st.toggle("Auto-refresh (1s)", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto_refresh


# ── Main area ─────────────────────────────────────────────────────────────────

col_feed, col_topo = st.columns([6, 4])

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT: Live Event Feed
# ═══════════════════════════════════════════════════════════════════════════════

with col_feed:
    st.subheader("⚡ Live Execution Trace")

    if not st.session_state.selected_trace:
        st.info("Fire a task from the sidebar to see real-time execution here.")
    else:
        trace_id = st.session_state.selected_trace
        trace_info = st.session_state.active_traces.get(trace_id, {})

        # Poll for new events
        last_seq = trace_info.get("last_seq", 0)
        new_data = _api_get("/playground/events", trace_id=trace_id, since_seq=last_seq, limit=200)
        if new_data and new_data.get("events"):
            trace_info["events"].extend(new_data["events"])
            trace_info["last_seq"] = new_data.get("next_seq", last_seq)

        events = trace_info.get("events", [])

        # ── Summary bar ───────────────────────────────────────────────────────
        if events:
            total_cost = sum(e.get("cost_inr", 0.0) for e in events)
            error_count = sum(1 for e in events if e.get("status") == "error")
            layer_counts: dict[str, int] = {}
            for e in events:
                layer_counts[e.get("layer", "?")] = layer_counts.get(e.get("layer", "?"), 0) + 1

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Events", len(events))
            m2.metric("Errors", error_count, delta_color="inverse" if error_count else "off")
            m3.metric("Cost ₹", f"₹{total_cost:.4f}")
            for i, (layer, count) in enumerate(list(layer_counts.items())[:2]):
                [m4, m5][i].metric(f"{LAYER_ICON.get(layer, '?')} {layer}", count)

        # ── Layer filter ──────────────────────────────────────────────────────
        layer_options = ["all"] + sorted({e.get("layer", "?") for e in events})
        filter_layer = st.selectbox("Filter layer", layer_options, label_visibility="collapsed")

        # ── Event timeline ────────────────────────────────────────────────────
        feed_container = st.container(height=520, border=True)
        with feed_container:
            if not events:
                st.caption("Waiting for events…")
            else:
                display_events = [
                    e for e in reversed(events)
                    if filter_layer == "all" or e.get("layer") == filter_layer
                ][:150]

                for event in display_events:
                    layer = event.get("layer", "?")
                    etype = event.get("event_type", "")
                    name = event.get("name", "")
                    status = event.get("status", "ok")
                    duration = event.get("duration_ms", 0.0)
                    cost = event.get("cost_inr", 0.0)
                    ts = (event.get("timestamp") or "")[-12:-4]  # HH:MM:SS.mmm
                    inp = event.get("input_summary", "")
                    out = event.get("output_summary", "")
                    err = event.get("error_msg", "")
                    seq = event.get("seq", 0)

                    color = LAYER_COLOR.get(layer, "#aaa")
                    icon = LAYER_ICON.get(layer, "?")
                    badge = EVENT_TYPE_BADGE.get(etype, etype[:3])
                    status_i = STATUS_ICON.get(status, "?")

                    if layer == "bus":  # heartbeat — very compact
                        st.markdown(f"<span style='color:#666;font-size:11px'>♡ keepalive</span>",
                                    unsafe_allow_html=True)
                        continue

                    dur_str = f" `{duration:.0f}ms`" if duration > 0 else ""
                    cost_str = f" `₹{cost:.4f}`" if cost > 0 else ""
                    err_str = f"\n  > ❌ `{err[:100]}`" if err else ""
                    inp_str = f"\n  > 📥 `{inp[:80]}`" if inp and status == "running" else ""
                    out_str = f"\n  > 📤 `{out[:80]}`" if out and status == "ok" else ""

                    st.markdown(
                        f"<div style='border-left:3px solid {color};padding:4px 8px;margin:2px 0;"
                        f"background:#1a1a2e;border-radius:0 4px 4px 0'>"
                        f"<span style='color:#888;font-size:10px'>#{seq} {ts}</span> "
                        f"<span style='color:{color}'>{icon} {badge}</span> "
                        f"<b style='color:#ddd'>{name}</b> "
                        f"<span style='color:#aaa;font-size:11px'>[{layer}]</span> "
                        f"{status_i}{dur_str}{cost_str}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if inp_str or out_str or err_str:
                        st.markdown(
                            f"<div style='margin:-2px 0 2px 16px;color:#888;font-size:11px'>"
                            f"{inp_str.strip()}{out_str.strip()}{err_str.strip()}</div>",
                            unsafe_allow_html=True,
                        )

        # ── Trace summary table ────────────────────────────────────────────────
        if events:
            with st.expander("📊 Per-component timing & cost table"):
                import pandas as pd
                completed = [e for e in events if e.get("event_type") == "complete"]
                if completed:
                    df = pd.DataFrame([{
                        "Layer": e.get("layer"),
                        "Name": e.get("name"),
                        "Duration (ms)": round(e.get("duration_ms", 0), 1),
                        "Cost ₹": round(e.get("cost_inr", 0), 6),
                        "Output": (e.get("output_summary") or "")[:60],
                    } for e in completed])
                    df = df.sort_values("Duration (ms)", ascending=False)
                    st.dataframe(df, use_container_width=True, hide_index=True,
                                 column_config={
                                     "Cost ₹": st.column_config.NumberColumn(format="₹%.6f"),
                                     "Duration (ms)": st.column_config.NumberColumn(format="%.1f ms"),
                                 })

                    # Timeline bar chart
                    if len(df) > 1:
                        st.subheader("Execution Timeline")
                        chart_df = df.set_index("Name")["Duration (ms)"].head(15)
                        st.bar_chart(chart_df)
                else:
                    st.caption("No completed events yet…")


# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT: Swarm Topology
# ═══════════════════════════════════════════════════════════════════════════════

with col_topo:
    st.subheader("🌐 Swarm Topology")

    # Load topology (cache in session)
    if st.session_state.topology is None or st.button("🔄 Reload Topology", use_container_width=True):
        st.session_state.topology = _api_get("/playground/topology")

    topo = st.session_state.topology
    if topo:
        stats = topo.get("stats", {})
        s1, s2, s3 = st.columns(3)
        s1.metric("Supervisors", stats.get("supervisor_count", 0))
        s2.metric("Agents", stats.get("agent_count", 0))
        s3.metric("Workers", stats.get("worker_count", 0))

        # ── Topology tree rendered as markdown ─────────────────────────────────
        nodes = topo.get("nodes", [])
        edges = topo.get("edges", [])

        # Build adjacency
        children: dict[str, list[str]] = {}
        for edge in edges:
            frm = edge["from"]
            children.setdefault(frm, []).append(edge["to"])

        node_map = {n["id"]: n for n in nodes}

        def _render_node(node_id: str, depth: int = 0) -> str:
            node = node_map.get(node_id, {})
            layer = node.get("layer", "")
            icon = LAYER_ICON.get(layer, "•")
            indent = "  " * depth
            label = node_id.replace("Supervisor", " Sup").replace("Agent", " Agt")
            kids = children.get(node_id, [])
            color_char = {"swarm": "🟣", "supervisor": "🟠", "agent": "🔵"}.get(layer, "🟢")
            line = f"{indent}{color_char} **{label}**\n"
            for kid in kids:
                line += _render_node(kid, depth + 1)
            return line

        with st.container(height=300, border=True):
            tree_md = _render_node("SwarmMaster")
            st.markdown(tree_md)

        # ── Worker capability grid ─────────────────────────────────────────────
        st.subheader("⚙️ Workers")
        workers = topo.get("workers", [])
        if workers:
            tier_filter = st.selectbox("Tier", ["All", "0-CPU", "1-3B", "2-14B", "3-20B"],
                                       label_visibility="collapsed")
            tier_map_2 = {"All": None, "0-CPU": 0, "1-3B": 1, "2-14B": 2, "3-20B": 3}
            tier_sel = tier_map_2[tier_filter]

            tier_colors = {0: "#888", 1: "#4fc3f7", 2: "#ff9800", 3: "#ab47bc"}
            tier_labels = {0: "CPU", 1: "3B", 2: "14B", 3: "20B"}

            for w in workers:
                if tier_sel is not None and w["tier"] != tier_sel:
                    continue
                tier = w["tier"]
                color = tier_colors.get(tier, "#aaa")
                label = tier_labels.get(tier, "?")
                caps = " · ".join(w["capabilities"][:3])
                if len(w["capabilities"]) > 3:
                    caps += f" +{len(w['capabilities'])-3}"
                st.markdown(
                    f"<div style='border-left:3px solid {color};padding:3px 8px;margin:2px 0;"
                    f"background:#1a1a2e;border-radius:0 3px 3px 0'>"
                    f"<span style='color:{color};font-size:10px'>T{tier} {label}</span> "
                    f"<b style='color:#ddd;font-size:13px'>{w['name']}</b>"
                    f"<br><span style='color:#777;font-size:10px'>{caps}</span></div>",
                    unsafe_allow_html=True,
                )
    else:
        st.warning("Could not load topology — is the API running?")

    # ── Active trace live stats ────────────────────────────────────────────────
    if st.session_state.selected_trace:
        trace_id = st.session_state.selected_trace
        trace_info = st.session_state.active_traces.get(trace_id, {})
        events = trace_info.get("events", [])

        st.divider()
        st.subheader("📡 Active Trace")
        st.caption(f"Trace ID: `{trace_id}`")
        st.caption(f"Info: {trace_info.get('info', '')} | Started: {trace_info.get('started_at', '')}")

        if events:
            # Which components have fired
            seen: dict[str, str] = {}  # name → last status
            for e in events:
                name = e.get("name", "")
                status = e.get("status", "ok")
                if name and name != "TraceBus":
                    seen[name] = status

            st.markdown("**Component activity:**")
            for name, status in list(seen.items())[:20]:
                icon = STATUS_ICON.get(status, "?")
                st.markdown(
                    f"<span style='font-size:12px'>{icon} `{name}`</span>",
                    unsafe_allow_html=True,
                )

        if st.button("🗑 Clear this trace", key="clear_trace"):
            _api_get(f"/playground/trace/{trace_id}")  # DELETE isn't easy via httpx get, use admin API
            st.session_state.active_traces.pop(trace_id, None)
            st.session_state.selected_trace = ""
            st.rerun()


# ── Auto-refresh ──────────────────────────────────────────────────────────────
if st.session_state.auto_refresh and st.session_state.selected_trace:
    time.sleep(1.0)
    st.rerun()


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """Console entrypoint — launches Streamlit programmatically."""
    import sys
    import subprocess
    sys.exit(subprocess.call(
        ["streamlit", "run", __file__, "--server.headless", "true",
         "--server.port", os.getenv("PLAYGROUND_PORT", "8502")],
        env={**os.environ},
    ))

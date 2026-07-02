/* GeoSupply OSINT — data layer: WebSocket live link + REST fallback + focus mode */
"use strict";

(() => {
  const API_BASE = ""; // same origin — FastAPI serves both API and frontend
  const POLL_MS = 90000;
  const WS_RETRY_MS = 5000;

  let ws = null;
  let wsAlive = false;
  let countries = [];   // focus registry from /osint/focus/countries

  // ── link status chip ──────────────────────────────────────────
  function setLink(state) {
    const led = document.getElementById("link-led");
    const txt = document.getElementById("link-text");
    if (state === "live") { led.className = "led led-green"; txt.textContent = "LIVE"; }
    else if (state === "poll") { led.className = "led led-amber"; txt.textContent = "POLLING"; }
    else { led.className = "led led-red"; txt.textContent = "OFFLINE"; }
  }

  function applySnapshot(snap) {
    if (!snap) return;
    Panels.renderAll(snap);
    OsintMap.setData(snap);
  }

  // ── REST ──────────────────────────────────────────────────────
  async function fetchSnapshot(refresh = false) {
    try {
      const resp = await fetch(`${API_BASE}/osint/snapshot${refresh ? "?refresh=true" : ""}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      applySnapshot(await resp.json());
      if (!wsAlive) setLink("poll");
      return true;
    } catch (err) {
      console.warn("snapshot fetch failed:", err);
      if (!wsAlive) setLink("down");
      return false;
    }
  }

  async function fetchJson(path) {
    const resp = await fetch(API_BASE + path);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  // ── focus mode ────────────────────────────────────────────────
  async function loadFocusRegistry() {
    try {
      countries = await fetchJson("/osint/focus/countries");
      const sel = document.getElementById("focus-select");
      for (const c of countries) {
        const opt = document.createElement("option");
        opt.value = c.iso2;
        opt.textContent = c.name.toUpperCase();
        sel.appendChild(opt);
      }
    } catch (err) { console.warn("focus registry failed:", err); }
  }

  function applyFocus(iso2) {
    const sel = document.getElementById("focus-select");
    if (!iso2) {
      sel.value = "";
      Panels.setFocus(null);
      OsintMap.resetView();
      return;
    }
    const c = countries.find((x) => x.iso2 === iso2);
    if (!c) return;
    sel.value = iso2;
    Panels.setFocus({ iso2: c.iso2, name: c.name });
    OsintMap.focusTo(c.lat, c.lon, c.zoom);
  }

  // ── freemium plan badge + feature locks ───────────────────────
  async function loadPlan() {
    try {
      const info = await fetchJson("/osint/plan");
      const chip = document.getElementById("plan-text");
      chip.textContent = "PLAN " + info.plan;
      chip.className = "plan-" + info.plan.toLowerCase();
      if ((info.locked || []).includes("advanced_intel")) {
        const input = document.getElementById("ask-input");
        input.disabled = true;
        input.placeholder = "🔒 ASK INTEL requires the PRO plan (₹499/month)";
        const tag = document.querySelector("#panel-ask .panel-tag");
        if (tag) tag.textContent = "🔒 PRO";
      }
    } catch (err) { console.warn("plan fetch failed:", err); }
  }

  // ── live streams ──────────────────────────────────────────────
  async function loadStreams() {
    try {
      Panels.renderStreams(await fetchJson("/osint/streams"));
    } catch (err) { console.warn("streams failed:", err); }
  }

  // ── ask intel ─────────────────────────────────────────────────
  async function ask(query) {
    const box = document.getElementById("ask-answer");
    box.innerHTML = '<div class="empty">Planning → retrieving → synthesising…</div>';
    try {
      Panels.renderAnswer(await fetchJson(`/osint/ask?q=${encodeURIComponent(query)}`));
    } catch (err) {
      box.innerHTML = '<div class="empty">Intel query failed — is the backend up?</div>';
    }
  }

  // ── WebSocket live link ───────────────────────────────────────
  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    try {
      ws = new WebSocket(`${proto}://${location.host}/osint/ws`);
    } catch (err) {
      console.warn("WS create failed:", err);
      scheduleReconnect();
      return;
    }
    ws.onopen = () => { wsAlive = true; setLink("live"); };
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "snapshot") applySnapshot(msg.data);
      } catch (err) { console.warn("WS parse error:", err); }
    };
    ws.onclose = () => { wsAlive = false; setLink("poll"); scheduleReconnect(); };
    ws.onerror = () => { try { ws.close(); } catch (_) { /* already closing */ } };
  }

  function scheduleReconnect() {
    setTimeout(connectWs, WS_RETRY_MS);
  }

  // ── clocks ────────────────────────────────────────────────────
  function tickClocks() {
    document.getElementById("clock-utc").textContent = Util.clock(0);
    document.getElementById("clock-ist").textContent = Util.clock(330); // IST = UTC+5:30
  }

  // ── boot ──────────────────────────────────────────────────────
  function boot() {
    OsintMap.init();
    tickClocks();
    setInterval(tickClocks, 1000);

    document.getElementById("btn-refresh").addEventListener("click", () => fetchSnapshot(true));
    document.getElementById("focus-select").addEventListener("change", (e) => applyFocus(e.target.value));
    document.getElementById("btn-india").addEventListener("click", () => applyFocus("IN"));
    document.addEventListener("focus-country", (e) => applyFocus(e.detail.iso2));
    document.getElementById("ask-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = document.getElementById("ask-input").value.trim();
      if (q.length >= 2) ask(q);
    });

    // cold start: force a refresh so panels populate immediately,
    // then keep a polling safety net under the WebSocket.
    fetchSnapshot(true);
    loadPlan();
    loadFocusRegistry();
    loadStreams();
    connectWs();
    setInterval(() => { if (!wsAlive) fetchSnapshot(false); }, POLL_MS);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();

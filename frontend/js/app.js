/* GeoSupply OSINT — data layer: WebSocket live link + REST fallback */
"use strict";

(() => {
  const API_BASE = ""; // same origin — FastAPI serves both API and frontend
  const POLL_MS = 90000;
  const WS_RETRY_MS = 5000;

  let ws = null;
  let wsAlive = false;
  let pollTimer = null;

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
      const snap = await resp.json();
      applySnapshot(snap);
      if (!wsAlive) setLink("poll");
      return true;
    } catch (err) {
      console.warn("snapshot fetch failed:", err);
      if (!wsAlive) setLink("down");
      return false;
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

    // cold start: force a refresh so panels populate immediately,
    // then keep a polling safety net under the WebSocket.
    fetchSnapshot(true);
    connectWs();
    pollTimer = setInterval(() => { if (!wsAlive) fetchSnapshot(false); }, POLL_MS);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();

/* GeoSupply OSINT — panel renderers (pure DOM, no framework) */
"use strict";

const Panels = (() => {
  let feedMinPriority = 0;
  let lastSnap = null;

  // ── Situation brief (+ convergence alert strip) ───────────────
  function renderBrief(snap) {
    const body = document.getElementById("brief-body");
    const hl = snap.highlights || [];
    const alerts = snap.alerts || [];
    if (!hl.length && !alerts.length) {
      body.innerHTML = '<div class="empty">No highlights yet</div>'; return;
    }
    const alertHtml = alerts.slice(0, 3).map((a) =>
      `<div class="conv-alert sev-a${a.severity}">
        <span class="conv-title">⚠ ${Util.esc(a.title)}</span>
        <span class="conv-detail">${Util.esc(a.detail)}</span>
        <span class="conv-signals">${a.signals.map((s) => `<i>${Util.esc(s)}</i>`).join("")}</span>
      </div>`
    ).join("");
    const hlHtml = hl.filter((h) => h.kind !== "convergence").map((h) =>
      `<div class="brief-item"><span class="sevband sev${h.severity}"></span>` +
      `<span class="brief-text">${Util.esc(h.text)}</span></div>`
    ).join("");
    body.innerHTML = alertHtml + hlHtml;
    document.getElementById("brief-ts").textContent =
      "UPDATED " + Util.age(snap.generated_at).toUpperCase() + " AGO";
  }

  // ── Live wire ─────────────────────────────────────────────────
  function renderFeed(snap) {
    const body = document.getElementById("feed-body");
    const items = (snap.news || []).filter((n) => n.priority >= feedMinPriority);
    if (!items.length) { body.innerHTML = '<div class="empty">No wire items at this filter</div>'; return; }
    body.innerHTML = items.slice(0, 60).map((n) => {
      const open = n.url ? ` data-url="${Util.esc(n.url)}"` : "";
      return `<div class="feed-item"${open}>
        <div class="feed-meta">
          <span class="prio prio-${n.priority}">${Util.prioLabel(n.priority)}</span>
          <span>${Util.esc(n.source)}</span>
          ${n.region ? `<span>${Util.esc(n.region)}</span>` : ""}
          <span>${Util.age(n.published)} ago</span>
        </div>
        <div class="feed-title">${Util.esc(n.title)}</div>
        ${n.entities && n.entities.length
          ? `<div class="feed-tags">${n.entities.map((e) => `<span class="tag">${Util.esc(e)}</span>`).join("")}</div>` : ""}
      </div>`;
    }).join("");
    body.querySelectorAll(".feed-item[data-url]").forEach((el) => {
      el.addEventListener("click", () => window.open(el.dataset.url, "_blank", "noopener"));
    });
  }

  // ── Ticker ────────────────────────────────────────────────────
  function renderTicker(snap) {
    const track = document.getElementById("ticker-track");
    const hot = (snap.news || []).filter((n) => n.priority >= 2).slice(0, 18);
    if (!hot.length) { track.innerHTML = '<span class="tick-item">— monitoring global wire —</span>'; return; }
    track.innerHTML = hot.map((n) =>
      `<span class="tick-item ${n.priority === 3 ? "tick-flash" : ""}">` +
      `<b>${Util.prioLabel(n.priority)}</b> ${Util.esc(n.title)} <i>· ${Util.esc(n.source)}</i></span>`
    ).join("");
  }

  // ── Global risk ───────────────────────────────────────────────
  function renderRisk(snap) {
    const body = document.getElementById("risk-body");
    const risks = (snap.country_risk || []).slice(0, 12);
    if (!risks.length) { body.innerHTML = '<div class="empty">No risk signals yet</div>'; return; }
    body.innerHTML = risks.map((r) => {
      const ciLeft = r.ci_low ?? r.score;
      const ciWidth = Math.max(0, (r.ci_high ?? r.score) - ciLeft);
      const lowConf = r.data_density === "SPARSE" && ciWidth > 30;
      return `<div class="risk-row">
        <span class="risk-iso">${Util.esc(r.iso2)}</span>
        <span class="risk-name">${Util.trendArrow(r.trend)} ${Util.esc(r.name)}</span>
        <span class="risk-bar-wrap">
          <span class="risk-ci" style="left:${ciLeft}%;width:${ciWidth}%"></span>
          <span class="risk-bar" style="width:${r.score}%"></span>
        </span>
        <span class="risk-score">${Math.round(r.score)}</span>
        <span class="risk-drivers">
          ${lowConf ? '<span class="lowconf">LOW CONFIDENCE</span> ' : ""}
          ${r.drivers && r.drivers.length ? `▸ ${r.drivers.map(Util.esc).join(" · ")} · ` : ""}
          ${r.mentions} signals · ${Util.esc(r.data_density || "")} density · CI ${Math.round(ciLeft)}–${Math.round(r.ci_high ?? r.score)}
        </span>
      </div>`;
    }).join("");
  }

  // ── Chokepoints ───────────────────────────────────────────────
  function renderChokepoints(snap) {
    const body = document.getElementById("choke-body");
    const cps = snap.chokepoints || [];
    if (!cps.length) { body.innerHTML = '<div class="empty">No chokepoint data</div>'; return; }
    body.innerHTML = cps.map((c) => {
      const pct = Math.round(c.stress_index * 100);
      const color = Util.stressColor(c.level);
      return `<div class="choke-row">
        <div class="choke-top">
          <span class="choke-name">${Util.trendArrow(c.trend)} ${Util.esc(c.name)}</span>
          <span class="choke-level lvl-${c.level}">${c.level}</span>
        </div>
        <div class="choke-bar-wrap"><div class="choke-bar" style="width:${pct}%;background:${color}"></div></div>
        <div class="choke-sub">${pct}% stress · ${c.recent_events} nearby events · ~${c.daily_transits} transits/day</div>
      </div>`;
    }).join("");
  }

  // ── Markets ───────────────────────────────────────────────────
  function renderMarkets(snap) {
    const body = document.getElementById("markets-body");
    const mkts = snap.markets || [];
    if (!mkts.length) { body.innerHTML = '<div class="empty">No market data</div>'; return; }
    body.innerHTML = mkts.map((m) => {
      const chg = m.change_pct === null || m.change_pct === undefined ? "" :
        `<span class="mkt-chg ${m.change_pct >= 0 ? "up" : "down"}">` +
        `${m.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(m.change_pct).toFixed(2)}%</span>`;
      return `<div class="mkt-row">
        <span><span class="mkt-sym">${Util.esc(m.symbol)}</span><span class="mkt-name">${Util.esc(m.name)}</span></span>
        <span><span class="mkt-val">${Util.fmt(m.value)}</span>${chg}</span>
      </div>`;
    }).join("");
  }

  // ── India ports ───────────────────────────────────────────────
  function renderIndia(snap) {
    const body = document.getElementById("india-body");
    const ports = snap.india_ports || [];
    if (!ports.length) { body.innerHTML = '<div class="empty">No port data</div>'; return; }
    body.innerHTML = ports.map((p) => {
      const monsoon = p.monsoon_risk && p.monsoon_risk !== "LOW"
        ? `<span class="monsoon mn-${p.monsoon_risk}" title="${p.rain_3d_mm ?? "?"}mm rain forecast / 3 days">☔ ${p.monsoon_risk}</span>`
        : "";
      return `<div class="port-row">
        <span><span class="port-name">${Util.esc(p.name)}</span><span class="port-state">${Util.esc(p.state)}</span></span>
        <span>${monsoon}<span class="port-status st-${p.status}" title="${Util.esc(p.note || "")}">${p.status}</span></span>
      </div>`;
    }).join("");
  }

  // ── System / sources ──────────────────────────────────────────
  function renderSystem(snap) {
    const body = document.getElementById("system-body");
    const srcs = snap.health || [];
    if (!srcs.length) { body.innerHTML = '<div class="empty">No source telemetry</div>'; return; }
    body.innerHTML = srcs.map((s) => {
      const led = s.ok ? "led-green" : (s.breaker_state === "OPEN" ? "led-red" : "led-amber");
      const meta = s.ok
        ? `${s.items} items · ${s.latency_ms ?? "—"}ms`
        : (s.error || s.breaker_state).slice(0, 40);
      return `<div class="src-row">
        <span class="led ${led}"></span>
        <span class="src-name">${Util.esc(s.name)}</span>
        <span class="src-meta">${Util.esc(meta)}</span>
      </div>`;
    }).join("");

    const okCount = srcs.filter((s) => s.ok).length;
    document.getElementById("src-text").textContent = `SOURCES ${okCount}/${srcs.length}`;
    const srcLed = document.getElementById("src-led");
    srcLed.className = "led " + (okCount === srcs.length ? "led-green" : okCount > 0 ? "led-amber" : "led-red");
  }

  function renderAll(snap) {
    lastSnap = snap;
    renderBrief(snap);
    renderFeed(snap);
    renderTicker(snap);
    renderRisk(snap);
    renderChokepoints(snap);
    renderMarkets(snap);
    renderIndia(snap);
    renderSystem(snap);
  }

  // feed priority filter buttons
  document.getElementById("feed-filters").addEventListener("click", (evt) => {
    const btn = evt.target.closest(".filt");
    if (!btn) return;
    feedMinPriority = Number(btn.dataset.min);
    document.querySelectorAll(".filt").forEach((b) => b.classList.toggle("active", b === btn));
    if (lastSnap) renderFeed(lastSnap);
  });

  return { renderAll };
})();

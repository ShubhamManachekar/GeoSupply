/* GeoSupply OSINT — panel renderers (pure DOM, no framework) */
"use strict";

const Panels = (() => {
  let feedMinPriority = 0;
  let lastSnap = null;
  let focus = null;   // {iso2, name} or null = GLOBAL

  // ── focus mode ────────────────────────────────────────────────
  function setFocus(f) {
    focus = f;
    if (lastSnap) renderAll(lastSnap);
  }

  function inFocus(item) {
    if (!focus) return true;
    const ents = item.entities || [];
    if (ents.includes(focus.name)) return true;
    if (focus.iso2 === "IN" && item.region === "INDIA") return true;
    return false;
  }

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
    let items = (snap.news || []).filter((n) => n.priority >= feedMinPriority);
    if (focus) items = items.filter(inFocus);
    if (!items.length) {
      body.innerHTML = `<div class="empty">No wire items${focus ? " for " + Util.esc(focus.name) : ""} at this filter</div>`;
      return;
    }
    body.innerHTML = items.slice(0, 60).map((n) => {
      const safe = Util.safeHttpUrl(n.url);
      const open = safe ? ` data-url="${Util.esc(safe)}"` : "";
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
      el.addEventListener("click", () => Util.openSafe(el.dataset.url));
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

  // ── Global risk (CI + trend + projection) ─────────────────────
  function renderRisk(snap) {
    const body = document.getElementById("risk-body");
    const risks = (snap.country_risk || []).slice(0, 12);
    if (!risks.length) { body.innerHTML = '<div class="empty">No risk signals yet</div>'; return; }
    body.innerHTML = risks.map((r) => {
      const ciLeft = r.ci_low ?? r.score;
      const ciWidth = Math.max(0, (r.ci_high ?? r.score) - ciLeft);
      const lowConf = r.data_density === "SPARSE" && ciWidth > 30;
      const focused = focus && focus.iso2 === r.iso2 ? " risk-focused" : "";
      const proj = r.projected_score !== null && r.projected_score !== undefined
        ? ` · proj ${Math.round(r.projected_score)}` : "";
      return `<div class="risk-row${focused}" data-iso2="${r.iso2}" data-name="${Util.esc(r.name)}">
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
          ${r.mentions} signals · ${Util.esc(r.data_density || "")} · CI ${Math.round(ciLeft)}–${Math.round(r.ci_high ?? r.score)}${proj}
        </span>
      </div>`;
    }).join("");
    body.querySelectorAll(".risk-row").forEach((el) => {
      el.addEventListener("click", () => {
        const evt = new CustomEvent("focus-country", {
          detail: { iso2: el.dataset.iso2, name: el.dataset.name } });
        document.dispatchEvent(evt);
      });
    });
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

  // ── Intel graph ───────────────────────────────────────────────
  function renderGraph(snap) {
    const body = document.getElementById("graph-body");
    let edges = snap.graph_edges || [];
    if (focus) {
      const filtered = edges.filter((e) => e.source === focus.name || e.target === focus.name);
      if (filtered.length) edges = filtered;
    }
    document.getElementById("graph-tag").textContent =
      focus ? `LINKS · ${focus.name.toUpperCase()}` : "CO-REPORTED";
    if (!edges.length) { body.innerHTML = '<div class="empty">Graph is learning from the wire…</div>'; return; }
    const maxW = Math.max(...edges.map((e) => e.weight), 1);
    body.innerHTML = edges.slice(0, 10).map((e) =>
      `<div class="kg-row" title="${Util.esc((e.contexts || [])[0] || "")}">
        <span class="kg-pair">${Util.esc(e.source)} <i>⟷</i> ${Util.esc(e.target)}</span>
        <span class="kg-bar-wrap"><span class="kg-bar" style="width:${Math.round(100 * e.weight / maxW)}%"></span></span>
        <span class="kg-w">${e.weight.toFixed(1)}</span>
      </div>`
    ).join("");
  }

  // ── Live streams ──────────────────────────────────────────────
  function renderStreams(streams) {
    const body = document.getElementById("streams-body");
    if (!streams || !streams.length) {
      body.innerHTML = '<div class="empty">No streams configured</div>'; return;
    }
    body.innerHTML = streams.map((s) =>
      `<div class="stream-row" data-url="${Util.esc(s.embed_url)}" data-name="${Util.esc(s.name)}">
        <span class="stream-kind sk-${s.kind}">${s.kind === "cam" ? "CAM" : "LIVE"}</span>
        <span class="stream-name">${Util.esc(s.name)}</span>
        <span class="stream-region">${Util.esc(s.region)}</span>
        <span class="stream-play">▶</span>
      </div>`
    ).join("");
    body.querySelectorAll(".stream-row").forEach((el) => {
      el.addEventListener("click", () => openStream(el.dataset.name, el.dataset.url));
    });
  }

  function openStream(name, url) {
    // The stream registry is server-controlled, but defence-in-depth: only
    // allow youtube.com/youtube-nocookie.com embed URLs to reach the iframe.
    const safe = Util.safeHttpUrl(url);
    if (!safe) return;
    try {
      const host = new URL(safe).host;
      if (!/(^|\.)youtube(-nocookie)?\.com$/.test(host)) return;
    } catch (_err) { return; }
    document.getElementById("stream-title").textContent = name;
    const frame = document.getElementById("stream-frame");
    frame.setAttribute("title", `${name} live stream`);
    frame.src = safe + (safe.includes("?") ? "&" : "?") + "autoplay=1";
    document.getElementById("stream-modal").classList.remove("hidden");
  }

  function closeStream() {
    document.getElementById("stream-frame").src = "";
    document.getElementById("stream-modal").classList.add("hidden");
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

  // ── Source trust (bias handler) ───────────────────────────────
  function renderBias(snap) {
    const body = document.getElementById("bias-body");
    const rows = snap.source_bias || [];
    if (!rows.length) { body.innerHTML = '<div class="empty">Learning source behaviour…</div>'; return; }
    body.innerHTML = rows.slice(0, 12).map((b) => {
      const pct = Math.round(b.credibility * 100);
      const color = b.credibility >= 0.6 ? "var(--green)" :
        b.credibility >= 0.35 ? "var(--amber)" : "var(--red-hot)";
      const flags = (b.bias_flags || []).map((f) => `<span class="bflag">${Util.esc(f)}</span>`).join("");
      return `<div class="bias-row" title="sensationalism ${(b.sensationalism * 100).toFixed(0)}% · corroboration ${(b.corroboration_rate * 100).toFixed(0)}% · ${b.items} items">
        <span class="bias-src">${Util.esc(b.source)}</span>
        <span class="kg-bar-wrap"><span class="kg-bar" style="width:${pct}%;background:${color}"></span></span>
        <span class="kg-w">${pct}</span>
        ${flags ? `<span class="bias-flags">${flags}</span>` : ""}
      </div>`;
    }).join("");
  }

  // ── System / sources / learning ───────────────────────────────
  function renderSystem(snap) {
    const body = document.getElementById("system-body");
    const srcs = snap.health || [];
    if (!srcs.length) { body.innerHTML = '<div class="empty">No source telemetry</div>'; return; }
    const learn = snap.learning || {};
    const learnHtml = `<div class="learn-row">
      cycle ${learn.cycles ?? 0} · tick ${Math.round(learn.refresh_interval_s ?? 120)}s${learn.surge_mode ? ' · <b class="surge">SURGE</b>' : ""}
      · KG ${learn.kg_nodes ?? 0}n/${learn.kg_edges ?? 0}e
      · proj MAE ${learn.projection_mae ?? "—"} (${learn.projection_samples ?? 0})
      · ${learn.penalised_sources ?? 0} sources penalised
    </div>`;
    body.innerHTML = learnHtml + srcs.map((s) => {
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

  // ── Ask intel ─────────────────────────────────────────────────
  //
  // Each citation gets thumbs ↑/↓ buttons; a click POSTs to
  // /osint/ask/feedback which reweights the RAG retriever per source
  // (self-reinforcement loop).
  let lastAsk = null;

  async function sendFeedback(query, source, kind, vote, btn) {
    try {
      const resp = await fetch("/osint/ask/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, items: [{ source, kind, vote }] }),
      });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const ack = await resp.json();
      if (btn) {
        btn.parentElement.querySelectorAll(".vote").forEach((b) => b.classList.remove("voted"));
        btn.classList.add("voted");
        btn.parentElement.setAttribute("data-trained", String(ack.trained_sources || 0));
      }
    } catch (err) {
      console.warn("feedback failed:", err);
    }
  }

  function renderAnswer(ans) {
    const box = document.getElementById("ask-answer");
    if (!ans) { box.innerHTML = ""; lastAsk = null; return; }
    lastAsk = ans;
    const cites = (ans.citations || []).slice(0, 5).map((c, idx) => {
      const safe = Util.safeHttpUrl(c.url);
      const link = safe
        ? ` <a class="pop-link" href="${Util.esc(safe)}" target="_blank" rel="noopener noreferrer">↗</a>`
        : "";
      const voteBtns = c.source
        ? `<span class="cite-votes" data-idx="${idx}">
             <button type="button" class="vote up" title="Helpful" aria-label="Helpful">👍</button>
             <button type="button" class="vote down" title="Not helpful" aria-label="Not helpful">👎</button>
           </span>`
        : "";
      return `<div class="cite" data-source="${Util.esc(c.source)}" data-kind="${Util.esc(c.kind)}">
        <span class="cite-kind">${Util.esc(c.kind)}</span> ${Util.esc(c.text)}
        <i>${Util.esc(c.source)}</i>${link}${voteBtns}
      </div>`;
    }).join("");
    box.innerHTML = `
      <div class="ask-conf">confidence ${(ans.confidence * 100).toFixed(0)}%
        ${ans.entities && ans.entities.length ? " · " + ans.entities.map(Util.esc).join(", ") : ""}</div>
      <div class="ask-text">${Util.esc(ans.answer)}</div>
      ${cites}`;
    box.querySelectorAll(".vote").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cite = btn.closest(".cite");
        const source = cite && cite.dataset.source;
        const kind = cite && cite.dataset.kind;
        const vote = btn.classList.contains("up") ? 1 : -1;
        if (source) sendFeedback(lastAsk?.query || "", source, kind || "news", vote, btn);
      });
    });
  }

  function renderAll(snap) {
    lastSnap = snap;
    renderBrief(snap);
    renderFeed(snap);
    renderTicker(snap);
    renderRisk(snap);
    renderChokepoints(snap);
    renderGraph(snap);
    renderMarkets(snap);
    renderIndia(snap);
    renderBias(snap);
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

  document.getElementById("stream-close").addEventListener("click", closeStream);
  document.getElementById("stream-modal").addEventListener("click", (evt) => {
    if (evt.target.id === "stream-modal") closeStream();
  });

  return { renderAll, renderStreams, renderAnswer, setFocus };
})();

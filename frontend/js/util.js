/* GeoSupply OSINT — shared helpers */
"use strict";

const Util = {
  esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  },

  /** "3m", "2h", "1d" relative age from ISO timestamp */
  age(iso) {
    if (!iso) return "";
    const ms = Date.now() - new Date(iso).getTime();
    if (!isFinite(ms) || ms < 0) return "now";
    const m = Math.floor(ms / 60000);
    if (m < 1) return "now";
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 48) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  },

  clock(tzOffsetMinutes) {
    const now = new Date(Date.now() + tzOffsetMinutes * 60000);
    return now.toISOString().slice(11, 19);
  },

  fmt(n, digits = 2) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("en-IN", {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
  },

  prioLabel(p) {
    return ["INFO", "NOTICE", "ALERT", "FLASH"][p] || "INFO";
  },

  stressColor(level) {
    return {
      LOW: "#34d399", ELEVATED: "#38bdf8", HIGH: "#fbbf24", CRITICAL: "#ef4444",
    }[level] || "#5f7488";
  },

  trendArrow(trend) {
    if (trend === "RISING") return '<span class="tr tr-up" title="rising">▲</span>';
    if (trend === "FALLING") return '<span class="tr tr-dn" title="falling">▼</span>';
    if (trend === "FLAT") return '<span class="tr tr-fl" title="flat">▬</span>';
    return '<span class="tr tr-new" title="new">●</span>';
  },

  /**
   * Only http(s) URLs are safe to open in a new tab from untrusted feed data.
   * Blocks javascript:, data:, file:, vbscript:, etc. Returns "" for invalid.
   */
  safeHttpUrl(raw) {
    if (!raw || typeof raw !== "string") return "";
    try {
      const u = new URL(raw, window.location.origin);
      return (u.protocol === "http:" || u.protocol === "https:") ? u.href : "";
    } catch (_err) {
      return "";
    }
  },

  /** Open a URL in a new tab only if it passes safeHttpUrl. */
  openSafe(raw) {
    const safe = Util.safeHttpUrl(raw);
    if (safe) window.open(safe, "_blank", "noopener,noreferrer");
  },
};

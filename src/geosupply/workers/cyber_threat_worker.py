"""CyberThreatWorker - Tier-1 STATIC cyber threat classification and MITRE ATT&CK mapping."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import CyberThreatScore, WorkerError

# ── Keyword → (threat_type, affected_sector, mitre_id) ─────────────────────

_THREAT_RULES: list[tuple[re.Pattern[str], str, str, str]] = [
    (re.compile(r"\b(ransomware|encrypt|ransom demand|decryptor)\b", re.I),
     "RANSOMWARE", "logistics", "T1486"),

    (re.compile(r"\b(gps.{0,4}jam|signal.{0,4}spoof|navigation.{0,4}disrupt)", re.I),
     "GPS_JAMMING", "aviation-maritime", "T1498"),

    (re.compile(r"\b(apt|state.?sponsor|advanced.?persistent|nation.?state)\b", re.I),
     "STATE_APT", "critical-infrastructure", "T1566"),

    (re.compile(r"\b(ddos|distributed.?denial|bandwidth.?flood|botnet.?flood)\b", re.I),
     "DDoS", "telecom", "T1498"),

    (re.compile(r"\b(data.?breach|credential.?leak|database.?dump|stolen.?data)\b", re.I),
     "DATA_BREACH", "finance", "T1078"),

    (re.compile(r"\b(supply.?chain.?attack|dependency.?confus|package.?poison)\b", re.I),
     "SUPPLY_CHAIN_ATTACK", "software", "T1195"),

    (re.compile(r"\b(undersea.?cable|submarine.?cable|cable.?cut|fibre.?cut)\b", re.I),
     "CABLE_CUT", "telecom", "T1498"),

    (re.compile(r"\b(scada|ics|industrial.?control|ot.?network|plc.?attack)\b", re.I),
     "SCADA", "energy-utilities", "T1489"),
]

# Geographic scope detection
_GEO_TERMS: dict[str, list[str]] = {
    "india": ["IN"],
    "china": ["CN"],
    "pakistan": ["PK"],
    "russia": ["RU"],
    "iran": ["IR"],
    "north korea": ["KP"],
    "usa": ["US"],
    "europe": ["EU"],
    "south asia": ["IN", "PK", "BD", "LK"],
    "indo-pacific": ["IN", "CN", "JP", "AU"],
}

_INDIA_IMPACT_SECTORS = {
    "logistics", "aviation-maritime", "energy-utilities",
    "finance", "telecom", "critical-infrastructure",
}


def _detect_geo_scope(text: str) -> list[str]:
    text_lower = text.lower()
    found: set[str] = set()
    for term, codes in _GEO_TERMS.items():
        if term in text_lower:
            found.update(codes)
    return sorted(found)


def _severity_from_text(text: str) -> float:
    """Heuristic severity 0–1 based on amplifying words."""
    amplifiers = re.findall(
        r"\b(critical|severe|major|widespread|national|government|military|hospital)\b",
        text,
        re.I,
    )
    base = 0.40
    return min(1.0, base + len(amplifiers) * 0.08)


def _india_impact(sector: str, geo_scope: list[str]) -> str:
    if "IN" in geo_scope and sector in _INDIA_IMPACT_SECTORS:
        return f"HIGH — {sector} sector directly exposed"
    if sector in _INDIA_IMPACT_SECTORS:
        return f"MEDIUM — {sector} sector may be indirectly affected"
    return "LOW — limited India exposure"


class CyberThreatWorker(BaseWorker):
    """
    Classify cyber threat type, map to MITRE ATT&CK, and score India impact.

    Input fields:
        text (str): Incident description or news snippet.
        sanitised_text (str, optional): Pre-sanitised text (preferred).
    """

    name = "CyberThreatWorker"
    tier = 1
    use_static = True
    capabilities = {"CYBER_THREAT_SCORE", "MITRE_MAP"}
    max_retries = 2
    timeout_seconds = 20

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        text = input_data.get("sanitised_text") or input_data.get("text")

        if not isinstance(text, str) or not text.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'text' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # Match threat rules in priority order
        matched_type: str | None = None
        matched_sector = "unknown"
        matched_mitre = ""

        for pattern, threat_type, sector, mitre_id in _THREAT_RULES:
            if pattern.search(text):
                matched_type = threat_type
                matched_sector = sector
                matched_mitre = mitre_id
                break

        if matched_type is None:
            return WorkerError(
                error_type="INPUT_INVALID",
                message="No recognisable cyber threat pattern detected in text",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        geo_scope = _detect_geo_scope(text)
        severity = _severity_from_text(text)
        india_impact = _india_impact(matched_sector, geo_scope)

        output = CyberThreatScore(
            threat_type=matched_type,  # type: ignore[arg-type]
            affected_sector=matched_sector,
            severity=round(severity, 4),
            geographic_scope=geo_scope,
            india_impact=india_impact,
            mitigation_status="unknown",
            mitre_attack_id=matched_mitre,
        )

        return {
            "result": output.model_dump(),
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

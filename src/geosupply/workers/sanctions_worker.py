"""SanctionsWorker - Tier-1 STATIC entity sanctions screening."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import SanctionsOutput, WorkerError

# Sanctions regimes and their pattern markers
# In production these are API-sourced (OFAC, UN, EU, SECO, UK FCDO)
_SANCTIONING_BODIES = ["OFAC", "UN", "EU", "UK_FCDO", "SECO", "India_MEA"]

# Simulated sanctions entity registry (name_pattern → sanctioned_by list)
# Format: (compiled_regex, [sanctioning bodies])
_SANCTIONS_REGISTRY: list[tuple[re.Pattern[str], list[str], str]] = [
    (re.compile(r"\b(iran|iranian|irgc|quds force)\b", re.I),
     ["OFAC", "EU", "UN", "UK_FCDO"], "STATE_SPONSOR"),

    (re.compile(r"\b(north korea|dprk|korean people|lazarus group)\b", re.I),
     ["OFAC", "UN", "EU", "UK_FCDO"], "STATE_SPONSOR"),

    (re.compile(r"\b(russia|rosneft|gazprom|sberbank|vtb bank)\b", re.I),
     ["OFAC", "EU", "UK_FCDO", "SECO"], "SECTORAL"),

    (re.compile(r"\b(myanmar|tatmadaw|min aung hlaing)\b", re.I),
     ["OFAC", "EU", "UK_FCDO"], "HUMAN_RIGHTS"),

    (re.compile(r"\b(wagner group|prigozhin|concord management)\b", re.I),
     ["OFAC", "EU", "UK_FCDO"], "TERRORIST"),

    (re.compile(r"\b(hamas|hezbollah|islamic jihad|al-qaeda|isis|daesh)\b", re.I),
     ["OFAC", "UN", "EU", "UK_FCDO", "India_MEA"], "TERRORIST"),

    (re.compile(r"\b(pakistan.{0,20}isi|lashkar|jaish|hizbul)\b", re.I),
     ["OFAC", "UN", "India_MEA"], "TERRORIST"),

    (re.compile(r"\b(venezuela|maduro|pdvsa)\b", re.I),
     ["OFAC", "EU"], "SECTORAL"),
]

_SANCTION_TYPE_MAP = {
    "STATE_SPONSOR": "Comprehensive sanctions — state sponsor of terrorism",
    "SECTORAL": "Sectoral sanctions — financial/energy/defence",
    "TERRORIST": "Terrorist designation — asset freeze + travel ban",
    "HUMAN_RIGHTS": "Human rights sanctions — targeted individuals/entities",
}


def _screen_entity(entity_name: str) -> tuple[list[str], str]:
    """Return (sanctioned_by, sanction_type) or ([], '') if clean."""
    for pattern, bodies, stype in _SANCTIONS_REGISTRY:
        if pattern.search(entity_name):
            return bodies, _SANCTION_TYPE_MAP.get(stype, stype)
    return [], ""


class SanctionsWorker(BaseWorker):
    """
    Screen an entity name or description against known sanctions lists.

    Input fields:
        entity_name (str): Name of person, organisation, or country to screen.
        context (str, optional): Additional context for pattern matching.
    """

    name = "SanctionsWorker"
    tier = 1
    use_static = True
    capabilities = {"SANCTIONS_CHECK", "ENTITY_SCREEN"}
    max_retries = 2
    timeout_seconds = 20

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        entity_name = input_data.get("entity_name")
        context = input_data.get("context", "")

        if not isinstance(entity_name, str) or not entity_name.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'entity_name' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # Screen both entity name and any additional context
        combined = f"{entity_name} {context}"
        sanctioned_by, sanction_type = _screen_entity(combined)

        output = SanctionsOutput(
            entity_name=entity_name.strip(),
            sanctioned_by=sanctioned_by,
            sanction_type=sanction_type,
        )

        return {
            "result": {
                **output.model_dump(),
                "is_sanctioned": len(sanctioned_by) > 0,
                "screening_bodies": _SANCTIONING_BODIES,
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

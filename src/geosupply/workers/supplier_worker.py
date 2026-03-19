"""SupplierWorker - Tier-1 STATIC supplier risk scoring and dependency mapping."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import SupplierScore, WorkerError

# High-risk supplier origin countries (ISO-3166 alpha-2)
_HIGH_RISK_COUNTRIES = frozenset({
    "CN", "RU", "KP", "IR", "PK", "BY", "VE", "SY",
})

# Critical dependency keywords → dependency category
_DEPENDENCY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(semiconduct\w*|chip\w*|microchip|wafer\w*|fab\w*)\b", re.I), "SEMICONDUCTOR"),
    (re.compile(r"\b(rare earth|lithium|cobalt|nickel|graphite)\b", re.I), "CRITICAL_MINERAL"),
    (re.compile(r"\b(pharma\w*|active pharmaceutical|drug\w*)\b", re.I), "PHARMA"),
    (re.compile(r"\b(solar panel|photovoltaic|wind turbine|battery)\b", re.I), "CLEAN_ENERGY"),
    (re.compile(r"\b(steel|aluminium|aluminum|copper|zinc)\b", re.I), "BASE_METAL"),
    (re.compile(r"\b(logistics|shipping|freight|container)\b", re.I), "LOGISTICS"),
    (re.compile(r"\b(software|cloud|saas|platform)\b", re.I), "DIGITAL"),
]

# Risk multipliers
_CONCENTRATION_PENALTY = 0.15   # per high-risk country in dependency chain
_SINGLE_SOURCE_PENALTY = 0.20   # no alternative supplier
_SANCTION_PENALTY = 0.25        # sanctioned entity flag


def _parse_countries(text: str) -> list[str]:
    """Extract ISO-2 country codes mentioned in the text."""
    # Simple: match known codes in uppercase
    return [c for c in re.findall(r"\b([A-Z]{2})\b", text) if c in _HIGH_RISK_COUNTRIES]


def _identify_dependencies(description: str) -> list[str]:
    deps: list[str] = []
    for pattern, category in _DEPENDENCY_PATTERNS:
        if pattern.search(description):
            deps.append(category)
    return deps


def _compute_risk(
    base: float,
    risky_countries: list[str],
    single_source: bool,
    sanctioned: bool,
) -> float:
    score = base
    score += len(risky_countries) * _CONCENTRATION_PENALTY
    if single_source:
        score += _SINGLE_SOURCE_PENALTY
    if sanctioned:
        score += _SANCTION_PENALTY
    return round(min(1.0, max(0.0, score)), 4)


class SupplierWorker(BaseWorker):
    """
    Score supply-chain supplier risk and map dependency categories.

    Input fields:
        supplier_id (str): Unique supplier identifier or name.
        description (str): Text describing the supplier, goods, or origin.
        origin_country (str, optional): ISO-2 country code of supplier origin.
        single_source (bool, optional): True if no alternative supplier exists.
        sanctioned (bool, optional): True if supplier is on a sanctions list.
    """

    name = "SupplierWorker"
    tier = 1
    use_static = True
    capabilities = {"SUPPLIER_SCORE", "DEPENDENCY"}
    max_retries = 2
    timeout_seconds = 20

    async def process(self, input_data: dict) -> dict:
        trace_id = input_data.get("trace_id", "unknown")
        supplier_id = input_data.get("supplier_id")
        description = input_data.get("description", "")
        origin_country = str(input_data.get("origin_country", "")).upper().strip()
        single_source = bool(input_data.get("single_source", False))
        sanctioned = bool(input_data.get("sanctioned", False))

        if not isinstance(supplier_id, str) or not supplier_id.strip():
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'supplier_id' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # Identify dependencies from description
        dependencies = _identify_dependencies(description)

        # Detect risky countries from description + explicit field
        risky_countries = _parse_countries(description)
        if origin_country in _HIGH_RISK_COUNTRIES:
            risky_countries.append(origin_country)
        risky_countries = list(set(risky_countries))

        # Base risk: higher if critical sector
        critical_sectors = {"SEMICONDUCTOR", "CRITICAL_MINERAL", "PHARMA"}
        base_risk = 0.30 if any(d in critical_sectors for d in dependencies) else 0.15

        risk_score = _compute_risk(base_risk, risky_countries, single_source, sanctioned)

        output = SupplierScore(
            supplier_id=supplier_id.strip(),
            risk_score=risk_score,
            dependencies=dependencies,
        )

        return {
            "result": {
                **output.model_dump(),
                "risky_countries": risky_countries,
                "single_source": single_source,
                "sanctioned": sanctioned,
            },
            "meta": {
                "worker": self.name,
                "tier": self.tier,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

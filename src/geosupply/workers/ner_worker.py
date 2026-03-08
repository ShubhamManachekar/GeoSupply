"""NERWorker - Tier-1 STATIC named-entity extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import NEREntity, NEROutput, WorkerError

_GPE_TERMS = {
    "india": "India",
    "china": "China",
    "russia": "Russia",
    "ukraine": "Ukraine",
    "pakistan": "Pakistan",
    "united states": "United States",
    "usa": "USA",
}

_PERSON_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b")
_ORG_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")
_ORG_SUFFIX_RE = re.compile(
    r"\b(?:[A-Z][\w&.-]*\s+){0,4}(?:Ministry|Bank|University|Corporation|Ltd|Inc|Agency)\b"
)


def _entity_key(entity_type: str, start: int, end: int) -> tuple[str, int, int]:
    return (entity_type, start, end)


class NERWorker(BaseWorker):
    """Extract lightweight named entities for downstream intelligence tasks."""

    name = "NERWorker"
    tier = 1
    use_static = True
    capabilities = {"NER_EXTRACT", "ENTITY_TYPE"}
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

        entities: list[NEREntity] = []
        seen: set[tuple[str, int, int]] = set()

        for term, canonical in _GPE_TERMS.items():
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                key = _entity_key("GPE", match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    NEREntity(
                        text=canonical,
                        entity_type="GPE",
                        span_start=match.start(),
                        span_end=match.end(),
                        confidence=0.9,
                    )
                )

        for pattern, label, confidence in (
            (_ORG_ACRONYM_RE, "ORG", 0.78),
            (_ORG_SUFFIX_RE, "ORG", 0.75),
            (_PERSON_RE, "PERSON", 0.72),
        ):
            for match in pattern.finditer(text):
                key = _entity_key(label, match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    NEREntity(
                        text=match.group(0),
                        entity_type=label,
                        span_start=match.start(),
                        span_end=match.end(),
                        confidence=confidence,
                    )
                )

        entities.sort(key=lambda entity: (entity.span_start, entity.span_end))
        output = NEROutput(entities=entities)

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

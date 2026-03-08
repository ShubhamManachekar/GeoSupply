"""
NewsWorker — Ingests news articles from NewsAPI, GDELT, ACLED
Part of: GeoSupply AI FA v2
Layer: 5 (Worker)
Phase: 2

Capabilities: INGEST_NEWS, RSS_PARSE
Tier: 0 (CPU only, no LLM)
Sources: NewsAPI (100/day), GDELT (unlimited), ACLED (50/day)
Output: Normalised article list [{title, body, source, published_at, url}]
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)

# ── Source Configurations ──────────────────────────────────────
# Each source has its own base URL, parameter mapping, and parser.
# All keys fetched via SecurityAgent at runtime — never hardcoded.

_SOURCE_CONFIGS: dict[str, dict[str, Any]] = {
    "newsapi": {
        "base_url": "https://newsapi.org/api/v2/everything",
        "default_params": {"language": "en", "sortBy": "publishedAt", "pageSize": 50},
        "auth_param": "apiKey",
        "auth_env": "GEOSUPPLY_NEWSAPI_KEY",
    },
    "gdelt": {
        "base_url": "https://api.gdeltproject.org/api/v2/doc/doc",
        "default_params": {"mode": "ArtList", "format": "json", "maxrecords": 50},
        "auth_param": None,  # GDELT requires no auth
        "auth_env": None,
    },
    "acled": {
        "base_url": "https://api.acleddata.com/acled/read",
        "default_params": {"terms": "accept", "limit": 50},
        "auth_param": "key",
        "auth_env": "GEOSUPPLY_ACLED_KEY",
    },
}

VALID_SOURCE_TYPES = frozenset(_SOURCE_CONFIGS.keys())


def _build_request_url(source_type: str, query: str, api_key: str | None = None) -> str:
    """Build the full API request URL for a given source type."""
    config = _SOURCE_CONFIGS[source_type]
    params = dict(config["default_params"])

    # Add query parameter (source-specific param name)
    if source_type == "newsapi":
        params["q"] = query
    elif source_type == "gdelt":
        params["query"] = query
    elif source_type == "acled":
        params["country"] = query  # ACLED uses country filter

    # Add auth if required
    if config["auth_param"] and api_key:
        params[config["auth_param"]] = api_key

    # ACLED also needs email
    if source_type == "acled" and api_key:

        params["email"] = os.environ.get("GEOSUPPLY_ACLED_EMAIL", "")

    return f"{config['base_url']}?{urlencode(params)}"


def _normalise_newsapi(raw_response: dict) -> list[dict]:
    """Parse NewsAPI response into normalised article list."""
    articles = raw_response.get("articles", [])
    return [
        {
            "title": a.get("title", ""),
            "body": a.get("description", "") or a.get("content", ""),
            "source": a.get("source", {}).get("name", "UNKNOWN"),
            "published_at": a.get("publishedAt", ""),
            "url": a.get("url", ""),
            "dedup_hash": hashlib.sha256(
                (a.get("url", "") + a.get("title", "")).encode()
            ).hexdigest()[:16],
        }
        for a in articles
        if a.get("title")  # Skip articles without titles
    ]


def _normalise_gdelt(raw_response: dict) -> list[dict]:
    """Parse GDELT response into normalised article list."""
    articles = raw_response.get("articles", [])
    return [
        {
            "title": a.get("title", ""),
            "body": a.get("seendate", ""),  # GDELT doesn't return body in ArtList
            "source": a.get("domain", "UNKNOWN"),
            "published_at": a.get("seendate", ""),
            "url": a.get("url", ""),
            "dedup_hash": hashlib.sha256(
                (a.get("url", "") + a.get("title", "")).encode()
            ).hexdigest()[:16],
        }
        for a in articles
        if a.get("title")
    ]


def _normalise_acled(raw_response: dict) -> list[dict]:
    """Parse ACLED response into normalised article list."""
    events = raw_response.get("data", [])
    return [
        {
            "title": f"{e.get('event_type', 'Event')}: {e.get('sub_event_type', '')}".strip(),
            "body": e.get("notes", ""),
            "source": f"ACLED/{e.get('source', 'unknown')}",
            "published_at": e.get("event_date", ""),
            "url": "",  # ACLED events don't have URLs
            "dedup_hash": hashlib.sha256(
                (str(e.get("data_id", "")) + e.get("event_date", "")).encode()
            ).hexdigest()[:16],
            "location": e.get("location", ""),
            "country": e.get("country", ""),
            "fatalities": e.get("fatalities", 0),
        }
        for e in events
    ]


_NORMALISERS = {
    "newsapi": _normalise_newsapi,
    "gdelt": _normalise_gdelt,
    "acled": _normalise_acled,
}


class NewsWorker(BaseWorker):
    """
    Ingests news articles from external APIs and normalises them
    into a standard format for downstream processing.

    PIPELINE POSITION: First ingestion point for news/conflict data.

    DATA FLOW:
        NewsAPI/GDELT/ACLED → NewsWorker → EventBus → IngestionSubAgent

    CAPABILITIES: INGEST_NEWS, RSS_PARSE
    TIER: 0 (CPU only, no LLM)
    STATIC: No
    """

    name = "NewsWorker"
    tier = 0
    use_static = False
    capabilities = {"INGEST_NEWS", "RSS_PARSE"}
    max_retries = 3
    timeout_seconds = 30

    async def process(self, input_data: dict) -> dict:
        """
        Fetch and normalise articles from a news source.

        Args:
            input_data: {
                "source_type": "newsapi" | "gdelt" | "acled",
                "query": str,
                "trace_id": str,
                "api_key": str (optional, fetched from env if absent),
            }

        Returns:
            dict with normalised articles and metadata
        """
        trace_id = input_data.get("trace_id", "unknown")
        source_type = input_data.get("source_type", "").lower().strip()
        query = input_data.get("query", "").strip()

        # ── Input Validation ──
        if not source_type:
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing 'source_type' field. Must be one of: newsapi, gdelt, acled",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if source_type not in VALID_SOURCE_TYPES:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Invalid source_type '{source_type}'. Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if not query:
            return WorkerError(
                error_type="INPUT_INVALID",
                message="Missing or empty 'query' field",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # ── Build Request ──
        config = _SOURCE_CONFIGS[source_type]
        api_key = input_data.get("api_key")

        # If no key provided, try env var
        if not api_key and config["auth_env"]:

            api_key = os.environ.get(config["auth_env"], "")

        # Auth required but not available
        if config["auth_param"] and not api_key:
            return WorkerError(
                error_type="API_FAILURE",
                message=f"API key required for {source_type} but not found in env var '{config['auth_env']}'",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        try:
            url = _build_request_url(source_type, query, api_key)

            # ── Fetch ──
            # Use httpx for async HTTP (production) or simulate for testability
            raw_response = await self._fetch_url(url, trace_id)

            # ── Normalise ──
            normaliser = _NORMALISERS[source_type]
            articles = normaliser(raw_response)

            logger.info(
                "%s: fetched %d articles from %s [query=%s, trace=%s]",
                self.name, len(articles), source_type, query[:30], trace_id,
            )

            return {
                "result": {
                    "articles": articles,
                    "source_type": source_type,
                    "query": query,
                    "count": len(articles),
                },
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.0,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        except Exception as exc:
            logger.error(
                "%s: API failure for %s: %s [trace=%s]",
                self.name, source_type, exc, trace_id,
            )
            return WorkerError(
                error_type="API_FAILURE",
                message=f"{source_type} fetch failed: {str(exc)}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

    async def _fetch_url(self, url: str, trace_id: str) -> dict:
        """
        Fetch JSON from URL. Uses httpx in production.
        Separated for testability — tests can subclass and override.
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except ImportError:
            # httpx not installed — return empty for graceful degradation
            logger.warning("%s: httpx not installed, returning empty [trace=%s]", self.name, trace_id)
            return {}
        except Exception as exc:
            raise RuntimeError(f"HTTP request failed: {exc}") from exc

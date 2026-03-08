"""
IndiaAPIWorker — Ingests data from Indian government APIs
Part of: GeoSupply AI FA v2
Layer: 5 (Worker)
Phase: 2

Capabilities: INGEST_INDIA_API, ULIP_QUERY
Tier: 0 (CPU only, no LLM)
Sources: ULIP (5 endpoints), DGFT, IMD, RBI, LDB
Plan B (R20): DGFT/IMD/RBI have no REST APIs — fallback via RSS/scraping
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)

# ── API Configurations ──────────────────────────────────────
_API_CONFIGS: dict[str, dict[str, Any]] = {
    "ulip": {
        "base_url": "https://ulip.dpiit.gov.in/ulip/v1.0.0",
        "endpoints": {
            "vehicle": "/VAHAN/01",
            "driver": "/SARATHI/01",
            "toll": "/FASTag/01",
            "rail": "/FOIS/01",
            "customs": "/ICEGATE/01",
        },
        "auth_type": "bearer",
        "auth_env": "GEOSUPPLY_ULIP_TOKEN",
        "has_rest_api": True,
    },
    "dgft": {
        "base_url": "https://www.dgft.gov.in/CP/",
        "endpoints": {"notifications": "?opt=notification", "circulars": "?opt=circular"},
        "auth_type": None,
        "auth_env": None,
        "has_rest_api": False,  # R20: scrape-dependent
        "fallback_strategy": "rss_then_scrape",
    },
    "imd": {
        "base_url": "https://mausam.imd.gov.in/",
        "endpoints": {"warnings": "backend/rss_warning.xml", "forecast": "backend/rss.xml"},
        "auth_type": None,
        "auth_env": None,
        "has_rest_api": False,  # R20: scrape-dependent
        "fallback_strategy": "xml_rss_feed",
    },
    "rbi": {
        "base_url": "https://www.rbi.org.in/scripts/",
        "endpoints": {"forex": "ReferenceRateArchive.aspx"},
        "auth_type": None,
        "auth_env": None,
        "has_rest_api": False,  # R20: scrape-dependent
        "fallback_strategy": "csv_download_or_fred",
    },
    "ldb": {
        "base_url": "https://ldb.gov.in",
        "endpoints": {"track": "/api/container/track"},
        "auth_type": "registration",
        "auth_env": None,
        "has_rest_api": True,
    },
}

VALID_API_NAMES = frozenset(_API_CONFIGS.keys())

# ULIP endpoint aliases for user-friendly querying
ULIP_ENDPOINT_ALIASES = {
    "vehicle": "VAHAN/01",
    "driver": "SARATHI/01",
    "toll": "FASTag/01",
    "rail": "FOIS/01",
    "customs": "ICEGATE/01",
}


def _build_ulip_url(endpoint: str, params: dict) -> str:
    """Build ULIP API URL for a specific endpoint."""
    base = _API_CONFIGS["ulip"]["base_url"]
    path = _API_CONFIGS["ulip"]["endpoints"].get(endpoint, endpoint)
    query = urlencode(params) if params else ""
    return f"{base}{path}{'?' + query if query else ''}"


def _describe_scrape_strategy(api_name: str) -> dict:
    """
    For APIs without REST endpoints (R20), return a structured
    description of the fallback parsing strategy.
    """
    config = _API_CONFIGS[api_name]
    strategy = config.get("fallback_strategy", "unknown")

    strategies = {
        "rss_then_scrape": {
            "method": "RSS feed → HTML scraping → PDF parsing",
            "libraries": ["feedparser", "beautifulsoup4", "pdfplumber"],
            "schedule": "Daily at 09:00 IST",
            "reliability": "medium",
            "notes": "DGFT publishes during business hours. PDFs may contain trade circulars.",
        },
        "xml_rss_feed": {
            "method": "XML/RSS feed parsing",
            "libraries": ["feedparser", "xml.etree.ElementTree"],
            "schedule": "Every 6 hours (IMD updates 4x/day)",
            "reliability": "medium",
            "notes": "Supplement with NASA EONET for India bbox (6,68,36,98).",
        },
        "csv_download_or_fred": {
            "method": "CSV download → FRED API fallback",
            "libraries": ["pandas", "requests"],
            "schedule": "Daily at 13:30 IST (RBI publishes ~1:30 PM)",
            "reliability": "high",
            "notes": "FRED series DEXINUS as USD/INR proxy if RBI CSV unavailable.",
        },
    }

    return {
        "api_name": api_name,
        "has_rest_api": False,
        "fallback": strategies.get(strategy, {"method": "unknown"}),
        "base_url": config["base_url"],
    }


def _normalise_ulip_response(raw: dict, endpoint: str) -> dict:
    """Normalise ULIP response into standard format."""
    return {
        "endpoint": endpoint,
        "records": raw.get("response", raw.get("data", [])),
        "total": raw.get("totalCount", len(raw.get("response", raw.get("data", [])))),
    }


class IndiaAPIWorker(BaseWorker):
    """
    Ingests data from Indian government APIs and logistics platforms.

    PIPELINE POSITION: Primary India-specific data ingestion.

    DATA FLOW:
        ULIP/DGFT/IMD/RBI/LDB → IndiaAPIWorker → EventBus → IngestionSubAgent

    R20 MITIGATION: For DGFT, IMD, RBI (no REST APIs), returns structured
    scrape strategy description. Actual scraping implemented when
    feedparser/bs4/pdfplumber are available.

    CAPABILITIES: INGEST_INDIA_API, ULIP_QUERY
    TIER: 0 (CPU only, no LLM)
    STATIC: No
    """

    name = "IndiaAPIWorker"
    tier = 0
    use_static = False
    capabilities = {"INGEST_INDIA_API", "ULIP_QUERY"}
    max_retries = 3
    timeout_seconds = 30

    async def process(self, input_data: dict) -> dict:
        """
        Fetch data from an Indian government API.

        Args:
            input_data: {
                "api_name": "ulip"|"dgft"|"imd"|"rbi"|"ldb",
                "params": dict (endpoint-specific parameters),
                "trace_id": str,
                "endpoint": str (for ULIP: vehicle/driver/toll/rail/customs),
            }
        """
        trace_id = input_data.get("trace_id", "unknown")
        api_name = input_data.get("api_name", "").lower().strip()
        params = input_data.get("params", {})

        # ── Input Validation ──
        if not api_name:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Missing 'api_name'. Must be one of: {', '.join(sorted(VALID_API_NAMES))}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if api_name not in VALID_API_NAMES:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Invalid api_name '{api_name}'. Must be one of: {', '.join(sorted(VALID_API_NAMES))}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        config = _API_CONFIGS[api_name]

        # ── Handle scrape-dependent APIs (R20) ──
        if not config["has_rest_api"]:
            strategy = _describe_scrape_strategy(api_name)

            # Attempt RSS/XML fetch if feedparser is available
            data = await self._try_fallback_fetch(api_name, config, trace_id)

            return {
                "result": {
                    "api_name": api_name,
                    "data": data,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "scrape_strategy": strategy,
                    "is_fallback": True,
                },
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.0,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        # ── Handle REST APIs (ULIP, LDB) ──
        try:
            # Check auth
            if config["auth_type"] == "bearer":

                token = os.environ.get(config["auth_env"], "")
                if not token:
                    return WorkerError(
                        error_type="API_FAILURE",
                        message=f"Bearer token required for {api_name} but not found in '{config['auth_env']}'",
                        worker_name=self.name,
                        trace_id=trace_id,
                    ).model_dump()

            # Build URL
            if api_name == "ulip":
                endpoint = input_data.get("endpoint", "vehicle")
                if endpoint not in _API_CONFIGS["ulip"]["endpoints"]:
                    return WorkerError(
                        error_type="INPUT_INVALID",
                        message=f"Invalid ULIP endpoint '{endpoint}'. Valid: {', '.join(_API_CONFIGS['ulip']['endpoints'].keys())}",
                        worker_name=self.name,
                        trace_id=trace_id,
                    ).model_dump()
                url = _build_ulip_url(endpoint, params)
            else:
                # LDB
                url = f"{config['base_url']}{list(config['endpoints'].values())[0]}"
                if params:
                    url += f"?{urlencode(params)}"

            # Fetch
            raw = await self._fetch_url(url, trace_id)

            # Normalise
            if api_name == "ulip":
                data = _normalise_ulip_response(raw, endpoint)
            else:
                data = raw

            logger.info(
                "%s: fetched from %s [trace=%s]",
                self.name, api_name, trace_id,
            )

            return {
                "result": {
                    "api_name": api_name,
                    "data": data,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "is_fallback": False,
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
                self.name, api_name, exc, trace_id,
            )
            return WorkerError(
                error_type="API_FAILURE",
                message=f"{api_name} fetch failed: {str(exc)}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

    async def _try_fallback_fetch(self, api_name: str, config: dict, trace_id: str) -> list:
        """Try to fetch data using fallback strategy (RSS/XML)."""
        try:
            import feedparser
            # Try RSS/XML endpoints
            endpoints = config.get("endpoints", {})
            for name, path in endpoints.items():
                url = f"{config['base_url']}{path}"
                feed = feedparser.parse(url)
                if feed.entries:
                    return [
                        {
                            "title": e.get("title", ""),
                            "summary": e.get("summary", ""),
                            "link": e.get("link", ""),
                            "published": e.get("published", ""),
                        }
                        for e in feed.entries[:20]
                    ]
        except ImportError:
            logger.warning(
                "%s: feedparser not available for %s fallback [trace=%s]",
                self.name, api_name, trace_id,
            )
        except Exception as exc:
            logger.warning(
                "%s: fallback fetch failed for %s: %s [trace=%s]",
                self.name, api_name, exc, trace_id,
            )
        return []

    async def _fetch_url(self, url: str, trace_id: str) -> dict:
        """Fetch JSON from URL. Separated for testability."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except ImportError:
            logger.warning("%s: httpx not installed [trace=%s]", self.name, trace_id)
            return {}
        except Exception as exc:
            raise RuntimeError(f"HTTP request failed: {exc}") from exc

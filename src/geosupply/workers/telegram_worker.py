"""
TelegramWorker — Ingests messages from Telegram OSINT channels
Part of: GeoSupply AI FA v2
Layer: 5 (Worker)
Phase: 2

Capabilities: INGEST_TELEGRAM, OSINT_CHANNEL
Tier: 0 (CPU only, no LLM)
Sources: 27+ Telegram OSINT channels (geopolitical, military, maritime)
Output: Normalised message list [{channel_id, message_id, text, date, views}]
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)

# ── Channel Registry ──────────────────────────────────────
# 27+ OSINT channels categorized by intelligence domain.
# channel_id format: @channel_name or numeric ID.
CHANNEL_REGISTRY: dict[str, dict[str, Any]] = {
    # Geopolitical & Conflict
    "@ryaborig": {"category": "conflict", "region": "eastern_europe", "language": "ru"},
    "@intelooperx": {"category": "conflict", "region": "global", "language": "en"},
    "@world_monitor": {"category": "geopolitical", "region": "global", "language": "en"},
    "@osaborning": {"category": "conflict", "region": "middle_east", "language": "en"},
    "@ConflictIntel": {"category": "conflict", "region": "global", "language": "en"},
    # Maritime & Shipping
    "@WarshipCam": {"category": "maritime", "region": "global", "language": "en"},
    "@MarineTraffic_Alert": {"category": "maritime", "region": "global", "language": "en"},
    # India Specific
    "@Indian_Defence_News": {"category": "military", "region": "india", "language": "en"},
    "@IndiaTradeWatch": {"category": "trade", "region": "india", "language": "en"},
    # Aviation
    "@AirLiveNet": {"category": "aviation", "region": "global", "language": "en"},
    "@MilRadar": {"category": "military_aviation", "region": "global", "language": "en"},
    # Cyber
    "@CyberSecurityHub": {"category": "cyber", "region": "global", "language": "en"},
    "@vaborning": {"category": "cyber", "region": "global", "language": "en"},
    # Disaster
    "@DisasterAlert": {"category": "disaster", "region": "global", "language": "en"},
    "@earthquakebot": {"category": "disaster", "region": "global", "language": "en"},
    # Energy & Commodities
    "@OilPriceAlert": {"category": "energy", "region": "global", "language": "en"},
    "@commoditynews": {"category": "commodities", "region": "global", "language": "en"},
    # Others (placeholders for full 27)
    "@OSINTechnical": {"category": "osint", "region": "global", "language": "en"},
    "@IntelSlavaZ": {"category": "conflict", "region": "eastern_europe", "language": "en"},
    "@neaborning": {"category": "geopolitical", "region": "asia", "language": "en"},
    "@MiddleEastSpect": {"category": "geopolitical", "region": "middle_east", "language": "en"},
    "@NorthAfricaOSINT": {"category": "geopolitical", "region": "africa", "language": "en"},
    "@IndoPacificWatch": {"category": "military", "region": "indo_pacific", "language": "en"},
    "@SupplyChainBrief": {"category": "trade", "region": "global", "language": "en"},
    "@PortCongest": {"category": "maritime", "region": "global", "language": "en"},
    "@SanctionsAlert": {"category": "sanctions", "region": "global", "language": "en"},
    "@ChinaNewsHub": {"category": "geopolitical", "region": "china", "language": "en"},
}

# Valid channel_id patterns: @username or numeric ID
_CHANNEL_PATTERN = re.compile(r'^(@[a-zA-Z0-9_]{5,32}|-?\d{10,20})$')

DEFAULT_MESSAGE_LIMIT = 50
MAX_MESSAGE_LIMIT = 200


def _validate_channel_id(channel_id: str) -> tuple[bool, str]:
    """Validate channel_id format."""
    if not channel_id:
        return False, "Missing 'channel_id' field"
    if not _CHANNEL_PATTERN.match(channel_id):
        return False, (
            f"Invalid channel_id format '{channel_id}'. "
            "Must be @username (5-32 chars) or numeric ID (10-20 digits)"
        )
    return True, ""


def _normalise_messages(raw_messages: list[dict], channel_id: str) -> list[dict]:
    """Normalise Telegram messages into standard format."""
    results = []
    for msg in raw_messages:
        text = msg.get("text", "") or msg.get("message", "")
        if not text:
            continue  # Skip empty/media-only messages

        results.append({
            "channel_id": channel_id,
            "message_id": msg.get("id", msg.get("message_id", 0)),
            "text": text[:2000],  # Cap at 2000 chars
            "date": msg.get("date", ""),
            "views": msg.get("views", 0),
            "forwards": msg.get("forwards", 0),
            "has_media": bool(msg.get("media") or msg.get("photo")),
            "reply_to": msg.get("reply_to_msg_id"),
        })
    return results


class TelegramWorker(BaseWorker):
    """
    Ingests messages from 27+ Telegram OSINT channels.

    PIPELINE POSITION: OSINT message ingestion.

    DATA FLOW:
        Telegram Channels → TelegramWorker → EventBus → NLP Workers

    CAPABILITIES: INGEST_TELEGRAM, OSINT_CHANNEL
    TIER: 0 (CPU only, no LLM)
    STATIC: No
    """

    name = "TelegramWorker"
    tier = 0
    use_static = False
    capabilities = {"INGEST_TELEGRAM", "OSINT_CHANNEL"}
    max_retries = 3
    timeout_seconds = 30

    async def process(self, input_data: dict) -> dict:
        """
        Fetch messages from a Telegram channel.

        Args:
            input_data: {
                "channel_id": str,    # @channel_name or numeric ID
                "limit": int,         # max messages to fetch (default 50)
                "trace_id": str,
                "category_filter": str (optional, e.g. "conflict", "maritime"),
            }
        """
        trace_id = input_data.get("trace_id", "unknown")
        channel_id = input_data.get("channel_id", "").strip()
        limit = input_data.get("limit", DEFAULT_MESSAGE_LIMIT)

        # ── Input Validation ──
        valid, error_msg = _validate_channel_id(channel_id)
        if not valid:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=error_msg,
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        # Cap limit
        if not isinstance(limit, int) or limit < 1:
            limit = DEFAULT_MESSAGE_LIMIT
        limit = min(limit, MAX_MESSAGE_LIMIT)

        # ── Channel Metadata ──
        channel_meta = CHANNEL_REGISTRY.get(channel_id, {
            "category": "unknown",
            "region": "unknown",
            "language": "unknown",
        })

        # ── Category Filter ──
        category_filter = input_data.get("category_filter", "").lower()
        if category_filter and channel_meta.get("category") != category_filter:
            return {
                "result": {
                    "channel_id": channel_id,
                    "messages": [],
                    "count": 0,
                    "skipped_reason": f"Channel category '{channel_meta.get('category')}' doesn't match filter '{category_filter}'",
                },
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.0,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        try:
            # ── Fetch Messages ──
            raw_messages = await self._fetch_messages(channel_id, limit, trace_id)

            # ── Normalise ──
            messages = _normalise_messages(raw_messages, channel_id)

            logger.info(
                "%s: fetched %d messages from %s [category=%s, trace=%s]",
                self.name, len(messages), channel_id,
                channel_meta.get("category", "?"), trace_id,
            )

            return {
                "result": {
                    "channel_id": channel_id,
                    "messages": messages,
                    "count": len(messages),
                    "channel_meta": channel_meta,
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
                "%s: fetch failure for %s: %s [trace=%s]",
                self.name, channel_id, exc, trace_id,
            )
            return WorkerError(
                error_type="API_FAILURE",
                message=f"Telegram fetch failed for {channel_id}: {str(exc)}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

    async def _fetch_messages(self, channel_id: str, limit: int, trace_id: str) -> list[dict]:
        """
        Fetch messages from Telegram. Uses telethon/pyrogram in production.
        Separated for testability.
        """
        try:
            # In production, this would use Telethon:
            # client = TelegramClient(...)
            # messages = await client.get_messages(channel_id, limit=limit)
            # For now, attempt import and fallback gracefully
            import telethon  # noqa: F401
            logger.info("%s: telethon available, would fetch from %s [trace=%s]",
                        self.name, channel_id, trace_id)
            return []  # Placeholder for real implementation
        except ImportError:
            logger.warning(
                "%s: telethon not installed, returning empty [trace=%s]",
                self.name, trace_id,
            )
            return []

    def get_channels_by_category(self, category: str) -> list[str]:
        """Return all registered channel IDs matching a category."""
        return [
            ch_id for ch_id, meta in CHANNEL_REGISTRY.items()
            if meta.get("category") == category
        ]

    def get_channels_by_region(self, region: str) -> list[str]:
        """Return all registered channel IDs matching a region."""
        return [
            ch_id for ch_id, meta in CHANNEL_REGISTRY.items()
            if meta.get("region") == region
        ]

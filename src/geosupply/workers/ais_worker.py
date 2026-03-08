"""
AISWorker — Ingests maritime vessel data from AISStream
Part of: GeoSupply AI FA v2
Layer: 5 (Worker)
Phase: 2

Capabilities: INGEST_AIS, VESSEL_TRACK
Tier: 0 (CPU only, no LLM)
Sources: AISStream WebSocket (relay service)
Output: Normalised vessel list [{mmsi, name, lat, lon, speed, heading, timestamp}]

DESIGN NOTE: AIS is a streaming WebSocket feed, but BaseWorker.process() is
request/response. This worker snapshots current vessel state per process() call
by fetching from a local buffer (populated by a background WS connection).
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any

from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)

# ── Region Bounding Boxes ──────────────────────────────────
# Pre-defined regions for common queries. Format: [lat_min, lon_min, lat_max, lon_max]
REGION_BBOXES: dict[str, list[float]] = {
    "india": [6.0, 68.0, 36.0, 98.0],
    "india_west_coast": [8.0, 68.0, 24.0, 77.0],
    "india_east_coast": [8.0, 78.0, 22.0, 92.0],
    "arabian_sea": [5.0, 50.0, 25.0, 77.0],
    "bay_of_bengal": [5.0, 78.0, 22.0, 97.0],
    "strait_of_hormuz": [24.0, 54.0, 28.0, 58.0],
    "malacca_strait": [-2.0, 99.0, 6.0, 105.0],
    "suez_canal": [29.0, 32.0, 32.0, 34.0],
    "red_sea": [12.0, 36.0, 30.0, 43.0],
    "south_china_sea": [0.0, 105.0, 22.0, 121.0],
    "persian_gulf": [24.0, 48.0, 30.0, 56.0],
    "global": [-90.0, -180.0, 90.0, 180.0],
}

VALID_REGIONS = frozenset(REGION_BBOXES.keys())

# AIS message types we care about
AIS_MSG_TYPES = {
    1: "Position Report Class A",
    2: "Position Report Class A (Assigned)",
    3: "Position Report Class A (Interrogated)",
    5: "Static and Voyage Related Data",
    18: "Standard Class B Position Report",
    19: "Extended Class B Position Report",
    24: "Class B CS Static Data Report",
}

# Vessel type classifications for military detection
VESSEL_TYPE_MILITARY = frozenset([35, 55])  # Military / Law Enforcement
VESSEL_TYPE_CARGO = frozenset(range(70, 80))  # Cargo ships
VESSEL_TYPE_TANKER = frozenset(range(80, 90))  # Tankers


def _validate_mmsi(mmsi: str) -> bool:
    """Validate MMSI format: 9 digits, first digit 2-7."""
    if not mmsi or len(mmsi) != 9:
        return False
    if not mmsi.isdigit():
        return False
    return mmsi[0] in "234567"


def _normalise_vessel(raw: dict) -> dict:
    """Normalise AIS message into standard vessel record."""
    lat = raw.get("latitude", raw.get("lat"))
    lon = raw.get("longitude", raw.get("lon"))

    # Validate coordinates
    if lat is not None and lon is not None:
        try:
            lat = float(lat)
            lon = float(lon)
            # AIS uses 91/181 as "not available"
            if lat == 91.0 or lon == 181.0:
                lat = None
                lon = None
        except (ValueError, TypeError):
            lat = None
            lon = None

    speed = raw.get("speed", raw.get("sog"))
    if speed is not None:
        try:
            speed = float(speed)
            if speed == 102.3:  # AIS "not available" value
                speed = None
        except (ValueError, TypeError):
            speed = None

    heading = raw.get("heading", raw.get("true_heading"))
    if heading is not None:
        try:
            heading = float(heading)
            if heading == 511:  # AIS "not available" value
                heading = None
        except (ValueError, TypeError):
            heading = None

    vessel_type = raw.get("ship_type", raw.get("vessel_type", 0))
    try:
        vessel_type = int(vessel_type)
    except (ValueError, TypeError):
        vessel_type = 0

    return {
        "mmsi": str(raw.get("mmsi", "")),
        "name": (raw.get("name", raw.get("ship_name", "")) or "").strip(),
        "callsign": (raw.get("callsign", "") or "").strip(),
        "lat": lat,
        "lon": lon,
        "speed_knots": speed,
        "heading": heading,
        "vessel_type": vessel_type,
        "is_military": vessel_type in VESSEL_TYPE_MILITARY,
        "is_cargo": vessel_type in VESSEL_TYPE_CARGO,
        "is_tanker": vessel_type in VESSEL_TYPE_TANKER,
        "destination": (raw.get("destination", "") or "").strip(),
        "nav_status": raw.get("navigational_status", raw.get("nav_status")),
        "timestamp": raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
    }


def _filter_by_bbox(vessels: list[dict], bbox: list[float]) -> list[dict]:
    """Filter vessels within a bounding box [lat_min, lon_min, lat_max, lon_max]."""
    lat_min, lon_min, lat_max, lon_max = bbox
    return [
        v for v in vessels
        if v.get("lat") is not None
        and v.get("lon") is not None
        and lat_min <= v["lat"] <= lat_max
        and lon_min <= v["lon"] <= lon_max
    ]


class AISWorker(BaseWorker):
    """
    Ingests maritime vessel data from AISStream WebSocket feed.

    PIPELINE POSITION: Maritime domain awareness ingestion.

    DATA FLOW:
        AISStream WS → background buffer → AISWorker.process() → EventBus

    DESIGN: process() snapshots current vessel state from a buffer.
    A background asyncio task maintains the WebSocket connection
    and populates the buffer. Each process() call returns the
    latest snapshot, filtered by region/MMSI.

    CAPABILITIES: INGEST_AIS, VESSEL_TRACK
    TIER: 0 (CPU only, no LLM)
    STATIC: No
    """

    name = "AISWorker"
    tier = 0
    use_static = False
    capabilities = {"INGEST_AIS", "VESSEL_TRACK"}
    max_retries = 3
    timeout_seconds = 30

    def __init__(self) -> None:
        super().__init__() if hasattr(super(), '__init__') else None
        # In-memory vessel buffer: MMSI → latest position
        self._vessel_buffer: dict[str, dict] = {}

    async def setup(self) -> None:
        """Initialize buffer. In production, start WS background task."""
        await super().setup()
        self._vessel_buffer = {}
        logger.info("%s: setup complete, buffer initialized", self.name)

    async def teardown(self) -> None:
        """Clear buffer. In production, close WS connection."""
        self._vessel_buffer.clear()
        await super().teardown()

    async def process(self, input_data: dict) -> dict:
        """
        Return vessel snapshot for a region or specific vessel.

        Args:
            input_data: {
                "region": str,             # required: key from REGION_BBOXES
                "vessel_mmsi": str|None,   # optional: specific vessel
                "trace_id": str,
            }
        """
        trace_id = input_data.get("trace_id", "unknown")
        region = input_data.get("region", "").lower().strip()
        vessel_mmsi = input_data.get("vessel_mmsi")

        # ── Input Validation ──
        if not region:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Missing 'region'. Must be one of: {', '.join(sorted(VALID_REGIONS))}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if region not in VALID_REGIONS:
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Invalid region '{region}'. Must be one of: {', '.join(sorted(VALID_REGIONS))}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        if vessel_mmsi and not _validate_mmsi(vessel_mmsi):
            return WorkerError(
                error_type="INPUT_INVALID",
                message=f"Invalid MMSI format '{vessel_mmsi}'. Must be 9 digits, first digit 2-7.",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

        try:
            # ── Fetch/Buffer Check ──
            raw_vessels = await self._get_vessel_data(region, vessel_mmsi, trace_id)

            # ── Normalise ──
            vessels = [_normalise_vessel(v) for v in raw_vessels]

            # ── Region Filter ──
            bbox = REGION_BBOXES[region]
            if region != "global":
                vessels = _filter_by_bbox(vessels, bbox)

            # ── MMSI Filter ──
            if vessel_mmsi:
                vessels = [v for v in vessels if v["mmsi"] == vessel_mmsi]

            # ── Classify ──
            military_count = sum(1 for v in vessels if v.get("is_military"))
            cargo_count = sum(1 for v in vessels if v.get("is_cargo"))
            tanker_count = sum(1 for v in vessels if v.get("is_tanker"))

            logger.info(
                "%s: %d vessels in %s (mil=%d, cargo=%d, tanker=%d) [trace=%s]",
                self.name, len(vessels), region,
                military_count, cargo_count, tanker_count, trace_id,
            )

            return {
                "result": {
                    "region": region,
                    "bbox": bbox,
                    "vessels": vessels,
                    "count": len(vessels),
                    "military_count": military_count,
                    "cargo_count": cargo_count,
                    "tanker_count": tanker_count,
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
                "%s: AIS failure for %s: %s [trace=%s]",
                self.name, region, exc, trace_id,
            )
            return WorkerError(
                error_type="API_FAILURE",
                message=f"AIS fetch failed for {region}: {str(exc)}",
                worker_name=self.name,
                trace_id=trace_id,
            ).model_dump()

    async def _get_vessel_data(self, region: str, mmsi: str | None, trace_id: str) -> list[dict]:
        """
        Get vessel data. In production, reads from WS buffer.
        If buffer is empty, attempts a REST API fallback.
        Separated for testability.
        """
        # Check buffer first
        if self._vessel_buffer:
            return list(self._vessel_buffer.values())

        # Try AISStream REST fallback
        try:
            import httpx

            api_key = os.environ.get("GEOSUPPLY_AISSTREAM_KEY", "")
            if not api_key:
                logger.warning("%s: AISSTREAM_KEY not set [trace=%s]", self.name, trace_id)
                return []

            bbox = REGION_BBOXES.get(region, REGION_BBOXES["global"])
            # AISStream uses WebSocket, but we simulate with empty for now
            logger.info("%s: would connect to AISStream WS for %s [trace=%s]",
                        self.name, region, trace_id)
            return []
        except ImportError:
            logger.warning("%s: httpx not installed [trace=%s]", self.name, trace_id)
            return []

    def update_buffer(self, vessels: list[dict]) -> int:
        """
        Update the vessel buffer with new data. Called by the
        background WebSocket listener.
        Returns number of vessels updated.
        """
        count = 0
        for v in vessels:
            mmsi = str(v.get("mmsi", ""))
            if mmsi:
                self._vessel_buffer[mmsi] = v
                count += 1
        return count

    def get_buffer_size(self) -> int:
        """Return current buffer size."""
        return len(self._vessel_buffer)

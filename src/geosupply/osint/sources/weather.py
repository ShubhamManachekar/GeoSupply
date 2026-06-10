"""
Open-Meteo current weather for India's 12 major ports. Free, key-free.
Batched call: comma-separated latitude/longitude returns a list of results.
"""
from __future__ import annotations

import httpx

from geosupply.osint.models import PortStatus
from geosupply.osint.registry import INDIA_PORTS
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Operational thresholds (port marine ops): sustained wind / heavy rain
WIND_WATCH_KMH = 40.0
WIND_DISRUPT_KMH = 62.0   # gale force — cargo ops typically suspended
RAIN_WATCH_MM = 7.5
RAIN_DISRUPT_MM = 15.0    # very heavy rainfall rate

# Monsoon supply-chain risk: 3-day forecast rain accumulation (IMD-style bands)
MONSOON_MODERATE_MM = 60.0
MONSOON_HEAVY_MM = 120.0
MONSOON_EXTREME_MM = 200.0


def classify_port(wind_kmh: float | None, precip_mm: float | None) -> tuple[str, str]:
    """Map current weather to an operational status + human note."""
    wind = wind_kmh or 0.0
    rain = precip_mm or 0.0
    if wind >= WIND_DISRUPT_KMH or rain >= RAIN_DISRUPT_MM:
        return "DISRUPTED", "Gale-force wind or very heavy rain — ops likely suspended"
    if wind >= WIND_WATCH_KMH or rain >= RAIN_WATCH_MM:
        return "WATCH", "Strong wind or heavy rain — possible slowdowns"
    return "OPERATIONAL", ""


def classify_monsoon(rain_3d_mm: float | None) -> str:
    """3-day forecast accumulation → monsoon supply-chain risk band."""
    rain = rain_3d_mm or 0.0
    if rain >= MONSOON_EXTREME_MM:
        return "EXTREME"
    if rain >= MONSOON_HEAVY_MM:
        return "HEAVY"
    if rain >= MONSOON_MODERATE_MM:
        return "MODERATE"
    return "LOW"


def parse_open_meteo(payload: list | dict, ports: list[dict]) -> list[PortStatus]:
    """Normalize a batched Open-Meteo response against the port registry."""
    rows = payload if isinstance(payload, list) else [payload]
    statuses: list[PortStatus] = []
    for port, row in zip(ports, rows):
        current = (row or {}).get("current") or {}
        wind = current.get("wind_speed_10m")
        precip = current.get("precipitation")
        daily = (row or {}).get("daily") or {}
        sums = [v for v in (daily.get("precipitation_sum") or []) if v is not None]
        rain_3d = round(sum(sums), 1) if sums else None
        monsoon = classify_monsoon(rain_3d)
        status, note = classify_port(wind, precip)
        if status == "OPERATIONAL" and monsoon in ("HEAVY", "EXTREME"):
            status, note = "WATCH", f"{monsoon.title()} monsoon rain forecast ({rain_3d}mm/3d)"
        statuses.append(PortStatus(
            name=port["name"], state=port["state"],
            lat=port["lat"], lon=port["lon"],
            status=status, note=note,
            wind_kmh=wind, precipitation_mm=precip,
            rain_3d_mm=rain_3d, monsoon_risk=monsoon,
        ))
    return statuses


class IndiaPortWeatherSource(BaseSource):
    """Current wind/precipitation at India's 12 major ports."""

    name = "India Port Weather"
    ttl_s = 1800.0

    async def fetch(self, client: httpx.AsyncClient) -> list[PortStatus]:
        resp = await client.get(
            OPEN_METEO_URL,
            params={
                "latitude": ",".join(str(p["lat"]) for p in INDIA_PORTS),
                "longitude": ",".join(str(p["lon"]) for p in INDIA_PORTS),
                "current": "wind_speed_10m,precipitation,weather_code",
                "daily": "precipitation_sum",
                "forecast_days": "3",
                "timezone": "UTC",
            },
            timeout=DEFAULT_TIMEOUT_S,
            headers=http_headers(),
        )
        resp.raise_for_status()
        return parse_open_meteo(resp.json(), INDIA_PORTS)

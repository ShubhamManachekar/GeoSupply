"""
GeoSupply AI — OSINT Dashboard Layer (Phase 9+)

Live open-source intelligence backend powering the world-monitor style
dashboard: real, key-free data sources (GDELT, USGS, NASA EONET, RSS,
markets, Open-Meteo), a TTL-cached aggregation middleware, and a
WebSocket hub for live fan-out to the frontend.

All sources are free — cost_inr = 0.0 across this layer.
"""
from geosupply.osint.aggregator import OsintAggregator, get_aggregator

__all__ = ["OsintAggregator", "get_aggregator"]

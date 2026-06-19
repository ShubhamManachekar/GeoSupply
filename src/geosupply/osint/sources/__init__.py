"""OSINT source connectors — all free, key-free, breaker-guarded."""
from geosupply.osint.sources.base import BaseSource, SourceResult
from geosupply.osint.sources.usgs import UsgsQuakeSource
from geosupply.osint.sources.eonet import EonetDisasterSource
from geosupply.osint.sources.gdelt import GdeltConflictSource, GdeltNewsSource
from geosupply.osint.sources.rss import RssNewsSource
from geosupply.osint.sources.markets import MarketsSource
from geosupply.osint.sources.weather import IndiaPortWeatherSource

__all__ = [
    "BaseSource",
    "SourceResult",
    "UsgsQuakeSource",
    "EonetDisasterSource",
    "GdeltConflictSource",
    "GdeltNewsSource",
    "RssNewsSource",
    "MarketsSource",
    "IndiaPortWeatherSource",
]

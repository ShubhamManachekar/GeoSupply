"""
RSS news aggregator — global + India outlets, parsed with stdlib XML.
Supports RSS 2.0 and Atom. No extra dependencies, no API keys.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from geosupply.osint.models import NewsItem
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers
from geosupply.osint.sources.gdelt import headline_priority

logger = logging.getLogger(__name__)

# (label, region tag, url) — all free public feeds
FEEDS: list[tuple[str, str, str]] = [
    # Global wire
    ("BBC World",      "GLOBAL", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera",     "GLOBAL", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("DW News",        "GLOBAL", "https://rss.dw.com/rdf/rss-en-world"),
    ("France 24",      "GLOBAL", "https://www.france24.com/en/rss"),
    ("Google News World", "GLOBAL",
     "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
    ("The Diplomat",   "ASIA",   "https://thediplomat.com/feed/"),
    # Defence / conflict
    ("Defense News",   "DEFENCE",
     "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"),
    # Maritime / supply chain
    ("gCaptain",       "MARITIME", "https://gcaptain.com/feed/"),
    ("Splash247",      "MARITIME", "https://splash247.com/feed/"),
    # India focus
    ("The Hindu",      "INDIA",  "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("Times of India", "INDIA",  "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    ("NDTV World",     "INDIA",  "https://feeds.feedburner.com/ndtvnews-world-news"),
    ("Hindustan Times", "INDIA",
     "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"),
    ("Economic Times", "INDIA",
     "https://economictimes.indiatimes.com/rssfeedsdefault.cms"),
    ("Google News India", "INDIA",
     "https://news.google.com/rss/search?q=india+geopolitics+OR+defence+OR+trade&hl=en-IN&gl=IN&ceid=IN:en"),
]

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_date(text: str | None) -> datetime:
    if not text:
        return datetime.now(timezone.utc)
    text = text.strip()
    try:  # RFC 822 (RSS)
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:  # ISO 8601 (Atom)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def parse_feed_xml(xml_text: str, source_label: str, region: str) -> list[NewsItem]:
    """Parse RSS 2.0 / RDF / Atom XML into NewsItems. Never raises on bad items."""
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("RSS parse error for %s: %s", source_label, exc)
        return items

    # RSS 2.0 + RDF: <item>; Atom: <entry>
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(f".//{_ATOM_NS}entry") or root.findall(
            ".//{http://purl.org/rss/1.0/}item")
    for node in nodes[:25]:
        title = _text(node, "title") or _text(node, f"{_ATOM_NS}title")
        if not title:
            continue
        link = _text(node, "link") or _text(node, "{http://purl.org/rss/1.0/}link")
        if not link:  # Atom link is an attribute
            link_el = node.find(f"{_ATOM_NS}link")
            link = link_el.get("href", "") if link_el is not None else ""
        pub = (_text(node, "pubDate")
               or _text(node, f"{_ATOM_NS}updated")
               or _text(node, f"{_ATOM_NS}published")
               or _text(node, "{http://purl.org/dc/elements/1.1/}date"))
        uid = hashlib.sha1((link or title).encode()).hexdigest()[:12]
        items.append(NewsItem(
            id=f"rss-{uid}",
            title=title.strip(),
            source=source_label,
            url=(link or "").strip(),
            published=_parse_date(pub),
            region=region,
            priority=headline_priority(title),
            category="maritime" if region == "MARITIME" else "news",
        ))
    return items


def _text(node: ET.Element, tag: str) -> str | None:
    el = node.find(tag)
    return el.text if el is not None and el.text else None


class RssNewsSource(BaseSource):
    """Aggregates all configured RSS feeds concurrently into one feed."""

    name = "RSS Wire"
    ttl_s = 300.0

    def __init__(self, feeds: list[tuple[str, str, str]] | None = None) -> None:
        super().__init__()
        self.feeds = feeds if feeds is not None else FEEDS

    async def _fetch_one(
        self, client: httpx.AsyncClient, label: str, region: str, url: str,
    ) -> list[NewsItem]:
        try:
            resp = await client.get(url, timeout=DEFAULT_TIMEOUT_S,
                                    headers=http_headers(), follow_redirects=True)
            resp.raise_for_status()
            return parse_feed_xml(resp.text, label, region)
        except Exception as exc:  # noqa: BLE001 — one dead feed must not kill the wire
            logger.warning("RSS feed %s failed: %s", label, exc)
            return []

    async def fetch(self, client: httpx.AsyncClient) -> list[NewsItem]:
        batches = await asyncio.gather(
            *(self._fetch_one(client, lb, rg, url) for lb, rg, url in self.feeds)
        )
        merged: list[NewsItem] = [item for batch in batches for item in batch]
        if not merged:
            raise RuntimeError("all RSS feeds failed")
        merged.sort(key=lambda n: n.published, reverse=True)
        return merged[:80]

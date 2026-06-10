"""
Market watch — FX (open.er-api.com), crypto (CoinGecko), commodities (Stooq).
All free, key-free endpoints. Costs: INR 0.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging

import httpx

from geosupply.osint.models import MarketQuote
from geosupply.osint.sources.base import BaseSource, DEFAULT_TIMEOUT_S, http_headers

logger = logging.getLogger(__name__)

ERAPI_URL = "https://open.er-api.com/v6/latest/USD"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
)
# Stooq free CSV quotes: WTI crude, Brent crude, Gold + USD/INR (for INR stress)
STOOQ_URL = "https://stooq.com/q/l/?s=cl.f,cb.f,gc.f,usdinr&f=sd2t2ohlcv&h&e=csv"

_STOOQ_NAMES = {"CL.F": "WTI Crude", "CB.F": "Brent Crude", "GC.F": "Gold",
                "USDINR": "USD/INR (intraday)"}
_STOOQ_UNITS = {"CL.F": "USD/bbl", "CB.F": "USD/bbl", "GC.F": "USD/oz",
                "USDINR": "INR"}


def parse_fx(payload: dict) -> list[MarketQuote]:
    """USD-base rates → INR-relevant FX quotes."""
    rates = payload.get("rates") or {}
    quotes: list[MarketQuote] = []
    inr = rates.get("INR")
    if inr:
        quotes.append(MarketQuote(symbol="USD/INR", name="US Dollar / Rupee",
                                  value=round(float(inr), 4), unit="INR"))
    eur, cny = rates.get("EUR"), rates.get("CNY")
    if inr and eur:
        quotes.append(MarketQuote(symbol="EUR/INR", name="Euro / Rupee",
                                  value=round(float(inr) / float(eur), 4), unit="INR"))
    if cny:
        quotes.append(MarketQuote(symbol="USD/CNY", name="US Dollar / Yuan",
                                  value=round(float(cny), 4), unit="CNY"))
    return quotes


def parse_crypto(payload: dict) -> list[MarketQuote]:
    quotes: list[MarketQuote] = []
    for cid, symbol, name in (("bitcoin", "BTC", "Bitcoin"), ("ethereum", "ETH", "Ethereum")):
        row = payload.get(cid) or {}
        if "usd" in row:
            quotes.append(MarketQuote(
                symbol=symbol, name=name,
                value=round(float(row["usd"]), 2),
                change_pct=round(float(row.get("usd_24h_change", 0.0)), 2),
                unit="USD",
            ))
    return quotes


def parse_stooq(csv_text: str) -> list[MarketQuote]:
    """Parse Stooq CSV (Symbol,Date,Time,Open,High,Low,Close,Volume)."""
    quotes: list[MarketQuote] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        sym = (row.get("Symbol") or "").upper()
        close, open_ = row.get("Close"), row.get("Open")
        if sym not in _STOOQ_NAMES or not close or close == "N/D":
            continue
        try:
            close_f = float(close)
            change = (round((close_f - float(open_)) / float(open_) * 100, 2)
                      if open_ and open_ != "N/D" and float(open_) else None)
        except ValueError:
            continue
        quotes.append(MarketQuote(symbol=sym, name=_STOOQ_NAMES[sym], value=close_f,
                                  change_pct=change, unit=_STOOQ_UNITS[sym]))
    return quotes


def merge_inr_stress(quotes: list[MarketQuote]) -> list[MarketQuote]:
    """
    INR stress enrichment: Stooq's intraday USDINR change is folded into the
    er-api USD/INR quote (which has the authoritative level but no change),
    and the duplicate intraday row is dropped.
    """
    intraday = next((q for q in quotes if q.symbol == "USDINR"), None)
    if intraday is None:
        return quotes
    usdinr = next((q for q in quotes if q.symbol == "USD/INR"), None)
    if usdinr is not None:
        usdinr.change_pct = intraday.change_pct
        return [q for q in quotes if q.symbol != "USDINR"]
    intraday.symbol, intraday.name = "USD/INR", "US Dollar / Rupee"
    return quotes


class MarketsSource(BaseSource):
    """FX + crypto + commodities in one panel refresh."""

    name = "Markets"
    ttl_s = 600.0

    async def fetch(self, client: httpx.AsyncClient) -> list[MarketQuote]:
        async def _get(url: str) -> httpx.Response | None:
            try:
                resp = await client.get(url, timeout=DEFAULT_TIMEOUT_S,
                                        headers=http_headers(), follow_redirects=True)
                resp.raise_for_status()
                return resp
            except Exception as exc:  # noqa: BLE001 — one feed must not kill the panel
                logger.warning("Markets feed %s failed: %s", url.split("/")[2], exc)
                return None

        fx_r, cg_r, st_r = await asyncio.gather(_get(ERAPI_URL), _get(COINGECKO_URL), _get(STOOQ_URL))
        quotes: list[MarketQuote] = []
        if fx_r is not None:
            quotes.extend(parse_fx(fx_r.json()))
        if cg_r is not None:
            quotes.extend(parse_crypto(cg_r.json()))
        if st_r is not None:
            quotes.extend(parse_stooq(st_r.text))
        if not quotes:
            raise RuntimeError("all market feeds failed")
        return merge_inr_stress(quotes)

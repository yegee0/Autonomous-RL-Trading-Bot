"""Free Binance Futures intelligence: funding rate + open interest + delta.

Used by the UI to show perpetual-futures sentiment, and by the drift/guardrail
layers to flag crowded positioning:
  - |funding| > 0.05%/8h ⇒ longs or shorts are paying a lot ⇒ crowded trade
  - OI change > 20% over 24h ⇒ aggressive leverage build-up or unwind
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import requests

_CACHE: dict = {}
_CACHE_TTL = 60.0  # seconds; funding changes every 8h so 1-min cache is fine
_LOCK = Lock()


def _ticker_to_binance_perp(ticker: str) -> Optional[str]:
    """BTC-USD / BTC-USDT / BTCUSDT → BTCUSDT; non-crypto → None."""
    t = ticker.upper().replace("-", "")
    if t.endswith("USD") and not t.endswith("USDT"):
        t = t[:-3] + "USDT"
    if not t.endswith(("USDT", "BUSD", "USDC")):
        return None
    return t


def _cached_get(key: str, url: str, params: Optional[dict] = None) -> Optional[dict]:
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (time.time() - hit[0]) < _CACHE_TTL:
            return hit[1]
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None
    with _LOCK:
        _CACHE[key] = (time.time(), data)
    return data


@dataclass
class OnChainSnapshot:
    symbol: str
    funding_rate: Optional[float]      # e.g. 0.0001 = 0.01% per 8h
    funding_annualized: Optional[float]  # funding × 3 × 365
    next_funding_time: Optional[int]   # unix seconds
    mark_price: Optional[float]
    open_interest: Optional[float]     # contracts
    open_interest_usd: Optional[float]
    oi_change_24h: Optional[float]     # fractional change
    crowded_side: Optional[str]        # "long" | "short" | "neutral"


def fetch_onchain(ticker: str) -> Optional[OnChainSnapshot]:
    sym = _ticker_to_binance_perp(ticker)
    if not sym:
        return None

    # 1) Premium index = funding + mark price
    premium = _cached_get(
        f"premium:{sym}",
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        params={"symbol": sym},
    )
    # 2) Current open interest
    oi = _cached_get(
        f"oi:{sym}",
        "https://fapi.binance.com/fapi/v1/openInterest",
        params={"symbol": sym},
    )
    # 3) 24h OI history for delta — 5m granularity, last 288 points = 24h
    oi_hist = _cached_get(
        f"oihist:{sym}",
        "https://fapi.binance.com/futures/data/openInterestHist",
        params={"symbol": sym, "period": "1h", "limit": 25},
    )

    funding_rate = None
    mark = None
    next_t = None
    if premium:
        try:
            funding_rate = float(premium.get("lastFundingRate")) if premium.get("lastFundingRate") else None
            mark = float(premium.get("markPrice")) if premium.get("markPrice") else None
            raw_t = premium.get("nextFundingTime")
            next_t = int(int(raw_t) / 1000) if raw_t else None
        except (TypeError, ValueError):
            pass

    oi_val = None
    if oi:
        try:
            oi_val = float(oi.get("openInterest"))
        except (TypeError, ValueError):
            pass

    oi_change = None
    if isinstance(oi_hist, list) and len(oi_hist) >= 2:
        try:
            first = float(oi_hist[0]["sumOpenInterest"])
            last = float(oi_hist[-1]["sumOpenInterest"])
            if first > 0:
                oi_change = (last - first) / first
        except (KeyError, TypeError, ValueError):
            pass

    oi_usd = (oi_val * mark) if (oi_val is not None and mark is not None) else None

    # Crowded-side classification (one funding period, 8h cost).
    crowded = "neutral"
    if funding_rate is not None:
        if funding_rate > 5e-4:
            crowded = "long"      # longs pay → long-heavy book
        elif funding_rate < -5e-4:
            crowded = "short"

    funding_ann = funding_rate * 3 * 365 if funding_rate is not None else None

    return OnChainSnapshot(
        symbol=sym,
        funding_rate=funding_rate,
        funding_annualized=funding_ann,
        next_funding_time=next_t,
        mark_price=mark,
        open_interest=oi_val,
        open_interest_usd=oi_usd,
        oi_change_24h=oi_change,
        crowded_side=crowded,
    )

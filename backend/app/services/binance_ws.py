"""Relay Binance's public kline WebSocket to internal subscribers.

Only handles crypto symbols shaped like `BTC-USD` → maps to `btcusdt`.
For non-crypto tickers callers should fall back to yfinance polling.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import websockets

log = logging.getLogger("binance_ws")

BINANCE_WS = "wss://stream.binance.com:9443/ws"


def ticker_to_binance_symbol(ticker: str) -> Optional[str]:
    t = ticker.upper().replace("-", "")
    if t.endswith("USD"):
        t = t[:-3] + "USDT"
    if not t.endswith(("USDT", "BUSD", "USDC", "BTC", "ETH")):
        return None
    return t.lower()


async def stream_klines(ticker: str, interval: str = "1m") -> AsyncIterator[dict]:
    """Yield kline dicts from Binance for the given ticker.

    Yields:
        {"time": int (sec), "open": float, "high": float, "low": float,
         "close": float, "volume": float, "closed": bool}
    """
    symbol = ticker_to_binance_symbol(ticker)
    if not symbol:
        return

    url = f"{BINANCE_WS}/{symbol}@kline_{interval}"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    k = msg.get("k") or {}
                    if not k:
                        continue
                    yield {
                        "time": int(k["t"] // 1000),
                        "open": float(k["o"]),
                        "high": float(k["h"]),
                        "low": float(k["l"]),
                        "close": float(k["c"]),
                        "volume": float(k["v"]),
                        "closed": bool(k["x"]),
                    }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("Binance WS error for %s: %s; reconnecting in 3s", symbol, e)
            await asyncio.sleep(3)

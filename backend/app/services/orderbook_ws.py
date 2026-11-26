"""Relay Binance's public order-book + liquidation streams.

depth20@100ms is the top-of-book: {bids:[[price, qty]x20], asks:[[price,qty]x20]}.
!forceOrder@arr is the aggregated liquidation feed (futures-wide; filtered client-side).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import websockets

log = logging.getLogger("orderbook_ws")

BINANCE_WS = "wss://stream.binance.com:9443/ws"
BINANCE_FUTURES_WS = "wss://fstream.binance.com/ws"


def ticker_to_binance_spot(ticker: str) -> Optional[str]:
    t = ticker.upper().replace("-", "")
    if t.endswith("USD") and not t.endswith("USDT"):
        t = t[:-3] + "USDT"
    if not t.endswith(("USDT", "BUSD", "USDC", "BTC", "ETH")):
        return None
    return t.lower()


async def stream_depth(ticker: str, levels: int = 20) -> AsyncIterator[dict]:
    """Yield depth snapshots. Reconnects forever on drop."""
    symbol = ticker_to_binance_spot(ticker)
    if not symbol:
        return
    url = f"{BINANCE_WS}/{symbol}@depth{levels}@100ms"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    bids = [[float(p), float(q)] for p, q in msg.get("bids", [])]
                    asks = [[float(p), float(q)] for p, q in msg.get("asks", [])]
                    yield {"bids": bids, "asks": asks}
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("depth WS error for %s: %s; reconnecting in 3s", symbol, e)
            await asyncio.sleep(3)


async def stream_liquidations(ticker: Optional[str] = None) -> AsyncIterator[dict]:
    """Yield liquidation events. If ticker is set, filter to that symbol."""
    sym_lower = ticker_to_binance_spot(ticker) if ticker else None
    want_sym = sym_lower.upper() if sym_lower else None
    url = f"{BINANCE_FUTURES_WS}/!forceOrder@arr"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    o = msg.get("o") or {}
                    if not o:
                        continue
                    sym = o.get("s", "")
                    if want_sym and sym != want_sym:
                        continue
                    try:
                        yield {
                            "symbol": sym,
                            "side": "long" if o.get("S") == "SELL" else "short",
                            "price": float(o.get("ap", o.get("p", 0))),
                            "qty": float(o.get("q", 0)),
                            "usd": float(o.get("ap", o.get("p", 0))) * float(o.get("q", 0)),
                            "time": int(int(o.get("T", 0)) / 1000) if o.get("T") else None,
                        }
                    except (TypeError, ValueError):
                        continue
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("liquidation WS error: %s; reconnecting in 3s", e)
            await asyncio.sleep(3)

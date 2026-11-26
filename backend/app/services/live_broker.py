"""Binance Spot Testnet broker — ONLY talks to testnet.binance.vision.

Safety rails baked in:
  * The client refuses to initialize unless BINANCE_TESTNET=1 is set.
  * The base URL is pinned to the testnet host; no code path picks mainnet.
  * The API keys live under BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET
    (deliberately different names than any mainnet convention) so a
    misconfigured .env can't accidentally send mainnet creds.
  * The paper guardrail layer still runs before every order — the only
    difference from paper is that execute_trade is replaced by a REST call.

Create free testnet keys at https://testnet.binance.vision/.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger("live_broker")

TESTNET_HOST = "https://testnet.binance.vision"
_TIMEOUT = 8.0


def _creds() -> Optional[tuple]:
    if os.getenv("BINANCE_TESTNET", "").strip() not in ("1", "true", "yes"):
        return None
    key = os.getenv("BINANCE_TESTNET_KEY", "").strip()
    secret = os.getenv("BINANCE_TESTNET_SECRET", "").strip()
    if not key or not secret:
        return None
    return key, secret


def is_enabled() -> bool:
    return _creds() is not None


def _signed_request(method: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    c = _creds()
    if c is None:
        raise RuntimeError(
            "Binance testnet is not configured — set BINANCE_TESTNET=1 and "
            "BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET."
        )
    key, secret = c
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    query = urllib.parse.urlencode(params, doseq=True)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{TESTNET_HOST}{path}?{query}&signature={sig}"
    headers = {"X-MBX-APIKEY": key}
    r = requests.request(method, url, headers=headers, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"Binance testnet {path} {r.status_code}: {r.text[:200]}")
    return r.json()


@dataclass
class Balance:
    asset: str
    free: float
    locked: float


@dataclass
class LiveOrder:
    order_id: int
    symbol: str
    side: str          # "BUY" / "SELL"
    type: str          # "MARKET" / "LIMIT"
    status: str
    price: float
    qty: float
    executed_qty: float
    cummulative_quote_qty: float


def _symbol_from_ticker(ticker: str) -> str:
    """BTC-USD, BTC/USDT, btcusdt → BTCUSDT."""
    t = ticker.upper().replace("-", "").replace("/", "")
    if t.endswith("USD") and not t.endswith("USDT"):
        t = t[:-3] + "USDT"
    return t


def account_balances() -> List[Balance]:
    data = _signed_request("GET", "/api/v3/account", {})
    out: List[Balance] = []
    for b in data.get("balances", []):
        free = float(b.get("free", 0) or 0)
        locked = float(b.get("locked", 0) or 0)
        if free > 0 or locked > 0:
            out.append(Balance(asset=b["asset"], free=free, locked=locked))
    return out


def place_order(
    ticker: str,
    side: str,
    qty: float,
    order_type: str = "MARKET",
    price: Optional[float] = None,
) -> LiveOrder:
    symbol = _symbol_from_ticker(ticker)
    side_u = side.upper()
    if side_u not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")

    params: Dict[str, Any] = {
        "symbol": symbol,
        "side": side_u,
        "type": order_type.upper(),
        "quantity": f"{qty:.8f}".rstrip("0").rstrip("."),
    }
    if order_type.upper() == "LIMIT":
        if price is None:
            raise ValueError("LIMIT orders need a price")
        params["timeInForce"] = "GTC"
        params["price"] = f"{price:.8f}".rstrip("0").rstrip(".")

    data = _signed_request("POST", "/api/v3/order", params)
    return LiveOrder(
        order_id=int(data.get("orderId", 0)),
        symbol=data.get("symbol", symbol),
        side=data.get("side", side_u),
        type=data.get("type", order_type.upper()),
        status=data.get("status", "NEW"),
        price=float(data.get("price", 0) or 0),
        qty=float(data.get("origQty", qty) or 0),
        executed_qty=float(data.get("executedQty", 0) or 0),
        cummulative_quote_qty=float(data.get("cummulativeQuoteQty", 0) or 0),
    )


def open_orders(ticker: Optional[str] = None) -> List[LiveOrder]:
    params: Dict[str, Any] = {}
    if ticker:
        params["symbol"] = _symbol_from_ticker(ticker)
    data = _signed_request("GET", "/api/v3/openOrders", params)
    return [
        LiveOrder(
            order_id=int(o.get("orderId", 0)),
            symbol=o.get("symbol", ""),
            side=o.get("side", ""),
            type=o.get("type", ""),
            status=o.get("status", ""),
            price=float(o.get("price", 0) or 0),
            qty=float(o.get("origQty", 0) or 0),
            executed_qty=float(o.get("executedQty", 0) or 0),
            cummulative_quote_qty=float(o.get("cummulativeQuoteQty", 0) or 0),
        )
        for o in data
    ]


def cancel_order(ticker: str, order_id: int) -> LiveOrder:
    params = {"symbol": _symbol_from_ticker(ticker), "orderId": order_id}
    data = _signed_request("DELETE", "/api/v3/order", params)
    return LiveOrder(
        order_id=int(data.get("orderId", order_id)),
        symbol=data.get("symbol", ""),
        side=data.get("side", ""),
        type=data.get("type", ""),
        status=data.get("status", "CANCELED"),
        price=float(data.get("price", 0) or 0),
        qty=float(data.get("origQty", 0) or 0),
        executed_qty=float(data.get("executedQty", 0) or 0),
        cummulative_quote_qty=float(data.get("cummulativeQuoteQty", 0) or 0),
    )

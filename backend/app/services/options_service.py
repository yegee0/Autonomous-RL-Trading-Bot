"""yfinance option-chain → IV skew + put/call ratio snapshot.

The nearest expiry is usually the most liquid, so default to it. The
service returns the strike grid for calls and puts plus three roll-ups:
    * atm_iv       — IV at the closest-to-spot strike
    * skew_25d     — (25-delta put IV) - (25-delta call IV): how much
                     the market pays extra for downside protection
    * put_call_oi  — total put OI / total call OI; >1 = bearish hedging
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import yfinance as yf


@dataclass
class OptionRow:
    strike: float
    last: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_vol: float


@dataclass
class OptionChain:
    ticker: str
    expiry: str
    spot: float
    calls: List[OptionRow]
    puts: List[OptionRow]
    atm_iv: Optional[float]
    skew_25d: Optional[float]
    put_call_oi: Optional[float]
    expiries: List[str]


def _row(df_row) -> OptionRow:
    return OptionRow(
        strike=float(df_row.get("strike", 0) or 0),
        last=float(df_row.get("lastPrice", 0) or 0),
        bid=float(df_row.get("bid", 0) or 0),
        ask=float(df_row.get("ask", 0) or 0),
        volume=int(df_row.get("volume") or 0),
        open_interest=int(df_row.get("openInterest") or 0),
        implied_vol=float(df_row.get("impliedVolatility", 0) or 0),
    )


def _closest_iv(rows: List[OptionRow], strike: float) -> Optional[float]:
    if not rows:
        return None
    nearest = min(rows, key=lambda r: abs(r.strike - strike))
    return nearest.implied_vol if nearest.implied_vol > 0 else None


def _wing_iv(rows: List[OptionRow], spot: float, moneyness: float) -> Optional[float]:
    """IV at ~moneyness * spot, e.g. 0.9 for 90% strike (OTM put wing)."""
    target = spot * moneyness
    liquid = [r for r in rows if r.implied_vol > 0 and r.open_interest > 0]
    if not liquid:
        return None
    nearest = min(liquid, key=lambda r: abs(r.strike - target))
    return nearest.implied_vol


def fetch_options(ticker: str, expiry: Optional[str] = None) -> Optional[OptionChain]:
    if "-USD" in ticker or ".IS" in ticker:
        return None  # crypto / BIST have no US option chain through yfinance

    try:
        tk = yf.Ticker(ticker)
        expiries = list(tk.options or [])
        if not expiries:
            return None
        chosen = expiry if expiry in expiries else expiries[0]
        chain = tk.option_chain(chosen)
        info = tk.fast_info
        spot = float(getattr(info, "last_price", None) or getattr(info, "lastPrice", 0) or 0)
        if spot <= 0:
            hist = tk.history(period="5d", interval="1d")
            if hist is None or hist.empty:
                return None
            spot = float(hist["Close"].iloc[-1])
    except Exception:
        return None

    calls = [_row(r) for _, r in chain.calls.iterrows()]
    puts = [_row(r) for _, r in chain.puts.iterrows()]
    calls.sort(key=lambda r: r.strike)
    puts.sort(key=lambda r: r.strike)

    atm_iv = _closest_iv(calls, spot)
    call_wing = _wing_iv(calls, spot, 1.10)   # 110% strike call
    put_wing = _wing_iv(puts, spot, 0.90)      # 90% strike put
    skew = (put_wing - call_wing) if (put_wing and call_wing) else None

    total_call_oi = sum(r.open_interest for r in calls)
    total_put_oi = sum(r.open_interest for r in puts)
    pc_oi = (total_put_oi / total_call_oi) if total_call_oi > 0 else None

    return OptionChain(
        ticker=ticker,
        expiry=chosen,
        spot=spot,
        calls=calls,
        puts=puts,
        atm_iv=atm_iv,
        skew_25d=skew,
        put_call_oi=pc_oi,
        expiries=expiries,
    )

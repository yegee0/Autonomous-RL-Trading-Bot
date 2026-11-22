"""Deterministic risk layer between the model and order execution.

Every paper trade passes through ``check_order`` BEFORE hitting the ledger.
Rules are intentionally boring and explicit — the whole point is that a
mis-behaving model can't bypass them.

Config via env vars so operators can tighten without code changes:
    MAX_POSITION_PCT   (default 20%): single-ticker position cap vs equity
    MAX_ORDER_PCT      (default 10%): single order notional cap vs equity
    MAX_DAILY_LOSS_PCT (default  5%): daily loss cap — triggers kill-switch
    TRADE_RATE_LIMIT   (default 10 per 60s): orders/window
    KILL_SWITCH_FILE:  disk sentinel; create to halt all trading immediately
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Optional

log = logging.getLogger("guardrails")


@dataclass
class GuardrailDecision:
    allowed: bool
    reason: str = ""
    code: str = ""


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

MAX_POSITION_PCT = _env_float("MAX_POSITION_PCT", 0.20)      # 20% of equity in one ticker
MAX_ORDER_PCT = _env_float("MAX_ORDER_PCT", 0.10)            # 10% of equity per order
MAX_DAILY_LOSS_PCT = _env_float("MAX_DAILY_LOSS_PCT", 0.05)  # 5% daily loss → kill
TRADE_RATE_MAX = _env_int("TRADE_RATE_LIMIT", 10)            # orders per window
TRADE_RATE_WINDOW_S = _env_int("TRADE_RATE_WINDOW", 60)
KILL_SWITCH_FILE = os.getenv(
    "KILL_SWITCH_FILE", os.path.join(PROJECT_ROOT, "KILL_SWITCH")
)
RSI_BUY_BLOCK = _env_float("RSI_BUY_BLOCK", 85.0)            # refuse buy if RSI >= this
RSI_SELL_BLOCK = _env_float("RSI_SELL_BLOCK", 15.0)          # refuse short/sell if RSI <= this


# ---- Rate limiter (sliding window, in-memory) ------------------------------
_RATE_LOCK = Lock()
_RATE_HITS: Deque[float] = deque()

# ---- Daily PnL high-watermark (for kill switch) ----------------------------
_PNL_LOCK = Lock()
_pnl_day: Optional[str] = None
_day_start_equity: float = 0.0
_kill_tripped_until_reset: bool = False


def _today_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def mark_day_start(equity: float) -> None:
    """Record the equity at session/day start so the kill switch can compare."""
    global _pnl_day, _day_start_equity, _kill_tripped_until_reset
    with _PNL_LOCK:
        _pnl_day = _today_key()
        _day_start_equity = float(equity)
        _kill_tripped_until_reset = False


def _ensure_day(equity: float) -> None:
    global _pnl_day, _day_start_equity, _kill_tripped_until_reset
    today = _today_key()
    if _pnl_day != today:
        _pnl_day = today
        _day_start_equity = float(equity)
        _kill_tripped_until_reset = False


def reset_kill_switch() -> None:
    """Clear the daily-loss trip and remove the on-disk sentinel if present."""
    global _kill_tripped_until_reset
    with _PNL_LOCK:
        _kill_tripped_until_reset = False
    try:
        if os.path.exists(KILL_SWITCH_FILE):
            os.remove(KILL_SWITCH_FILE)
    except OSError as e:
        log.warning("could not remove kill-switch sentinel: %s", e)


def kill_switch_active() -> bool:
    """True if the kill switch is tripped by daily-loss OR by the sentinel file."""
    if _kill_tripped_until_reset:
        return True
    if os.path.exists(KILL_SWITCH_FILE):
        return True
    return False


def _rate_limited_now() -> bool:
    cutoff = time.time() - TRADE_RATE_WINDOW_S
    with _RATE_LOCK:
        while _RATE_HITS and _RATE_HITS[0] < cutoff:
            _RATE_HITS.popleft()
        return len(_RATE_HITS) >= TRADE_RATE_MAX


def _record_hit() -> None:
    with _RATE_LOCK:
        _RATE_HITS.append(time.time())


def check_order(
    *,
    ticker: str,
    side: str,
    qty: float,
    price: float,
    equity: float,
    current_position_qty: float = 0.0,
    rsi: Optional[float] = None,
) -> GuardrailDecision:
    """Return ``GuardrailDecision`` for the proposed order. Does NOT execute.

    Call ``record_fill`` after a successful execution so the rate limiter
    counts it; a rejection should NOT be recorded.
    """
    # 1) Kill switch (file sentinel OR daily-loss trip) — hardest stop.
    if kill_switch_active():
        return GuardrailDecision(False, "Kill switch is active", "KILL_SWITCH")

    # 2) Daily loss check.
    _ensure_day(equity)
    global _kill_tripped_until_reset
    if _day_start_equity > 0:
        day_pnl_pct = (equity - _day_start_equity) / _day_start_equity
        if day_pnl_pct <= -MAX_DAILY_LOSS_PCT:
            _kill_tripped_until_reset = True
            return GuardrailDecision(
                False,
                f"Daily loss limit reached ({day_pnl_pct:.2%}); kill switch engaged",
                "DAILY_LOSS",
            )

    # 3) Rate limit.
    if _rate_limited_now():
        return GuardrailDecision(
            False,
            f"Too many orders — max {TRADE_RATE_MAX} per {TRADE_RATE_WINDOW_S}s",
            "RATE_LIMIT",
        )

    # 4) Basic sanity.
    if qty <= 0 or price <= 0:
        return GuardrailDecision(False, "qty and price must be positive", "INVALID")
    if side.lower() not in ("buy", "sell"):
        return GuardrailDecision(False, "side must be buy/sell", "INVALID")

    notional = qty * price
    if equity <= 0:
        return GuardrailDecision(False, "No equity to trade", "NO_EQUITY")

    # 5) Order notional cap.
    order_pct = notional / equity
    if order_pct > MAX_ORDER_PCT:
        return GuardrailDecision(
            False,
            f"Order size {order_pct:.1%} exceeds per-order cap {MAX_ORDER_PCT:.1%}",
            "ORDER_CAP",
        )

    # 6) Post-trade position cap (only tightens for buys that grow the position).
    if side == "buy":
        new_qty = current_position_qty + qty
        new_notional = new_qty * price
        if new_notional / equity > MAX_POSITION_PCT:
            return GuardrailDecision(
                False,
                f"Position would reach {new_notional / equity:.1%} of equity > {MAX_POSITION_PCT:.1%}",
                "POSITION_CAP",
            )

    # 7) Overbought / oversold filter (defensive, NOT contrarian).
    if rsi is not None:
        if side == "buy" and rsi >= RSI_BUY_BLOCK:
            return GuardrailDecision(
                False,
                f"RSI {rsi:.1f} is extreme overbought (≥{RSI_BUY_BLOCK:.0f}); buys blocked",
                "RSI_BLOCK",
            )
        if side == "sell" and current_position_qty <= 0 and rsi <= RSI_SELL_BLOCK:
            return GuardrailDecision(
                False,
                f"RSI {rsi:.1f} is extreme oversold (≤{RSI_SELL_BLOCK:.0f}); short entries blocked",
                "RSI_BLOCK",
            )

    return GuardrailDecision(True, "", "")


def record_fill() -> None:
    """Call after a successful execution so the rate limiter counts it."""
    _record_hit()


def snapshot() -> dict:
    """Debug / monitoring view of the current guardrail state."""
    with _RATE_LOCK:
        hits = list(_RATE_HITS)
    return {
        "kill_switch_active": kill_switch_active(),
        "kill_switch_file": KILL_SWITCH_FILE,
        "kill_switch_file_exists": os.path.exists(KILL_SWITCH_FILE),
        "daily_loss_tripped": _kill_tripped_until_reset,
        "day_start_equity": _day_start_equity,
        "day_key": _pnl_day,
        "rate_hits_in_window": len(hits),
        "rate_limit_max": TRADE_RATE_MAX,
        "rate_limit_window_s": TRADE_RATE_WINDOW_S,
        "limits": {
            "max_position_pct": MAX_POSITION_PCT,
            "max_order_pct": MAX_ORDER_PCT,
            "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
            "rsi_buy_block": RSI_BUY_BLOCK,
            "rsi_sell_block": RSI_SELL_BLOCK,
        },
    }

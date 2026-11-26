"""Walk-forward backtest for the loaded PPO policy against historical bars.

If no PPO model is available, falls back to the rule-based signal so the
backtest always returns a comparable report.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from src.agents.rl_agent import (
    N_STACK,
    calculate_fallback_signal,
    load_agent,
)
from src.models.trading_env import (
    COMMISSION,
    SLIPPAGE_BPS_PER_ATR,
    SPREAD_BPS,
    build_observation,
)


INITIAL_BALANCE = 10_000.0


def _fill_price(mid: float, atr: float, frac: float, side: str) -> float:
    """Realistic fill = mid price adjusted for half-spread + size-aware slippage."""
    spread = SPREAD_BPS / 10_000.0
    size_impact = (atr / max(mid, 1e-9)) * SLIPPAGE_BPS_PER_ATR * abs(frac) / 10.0
    bps = spread + size_impact
    return mid * (1.0 + bps if side == "buy" else 1.0 - bps)


def _normalize_stacked(env, df: pd.DataFrame, idx: int, cash: float, shares: float) -> np.ndarray:
    """Build a FrameStack(10)-shaped normalised obs from df up to idx."""
    start = max(0, idx - N_STACK + 1)
    frames = []
    vecnorm = env.venv if hasattr(env, "venv") else env
    for i in range(start, idx + 1):
        raw = build_observation(df, i, cash, shares, INITIAL_BALANCE).reshape(1, -1)
        frames.append(vecnorm.normalize_obs(raw))
    while len(frames) < N_STACK:
        frames.insert(0, frames[0])
    return np.concatenate(frames, axis=1).astype(np.float32)


def _apply_action(
    action: int, cash: float, shares: float, price: float, atr: float = 0.0
) -> Tuple[float, float, str]:
    if action in (1, 2, 3):
        frac = {1: 0.25, 2: 0.50, 3: 1.0}[action]
        spend = cash * frac
        if spend > 10:
            total = spend * (1.0 + COMMISSION)
            if cash >= total:
                fill = _fill_price(price, atr, frac, "buy")
                cash -= total
                shares += spend / fill
                return cash, shares, "buy"
    elif action in (4, 5, 6):
        if shares > 0:
            frac = {4: 0.25, 5: 0.50, 6: 1.0}[action]
            sold = shares * frac
            fill = _fill_price(price, atr, frac, "sell")
            cash += sold * fill * (1.0 - COMMISSION)
            shares -= sold
            return cash, shares, "sell"
    return cash, shares, "hold"


def run_backtest(ticker: str, df: pd.DataFrame, max_bars: int = 400) -> dict:
    """Return a report dict with equity curve, trades, and metrics."""
    if df is None or df.empty:
        raise ValueError("Empty dataframe for backtest")

    df = df.tail(max_bars).reset_index(drop=True)
    model, env = load_agent(ticker)
    source = "ppo" if model else "fallback"

    cash = INITIAL_BALANCE
    shares = 0.0
    equity_curve: List[float] = []
    trades: List[dict] = []
    markers: List[dict] = []

    for i in range(len(df)):
        price = float(df.iloc[i]["Close"])
        atr = float(df.iloc[i].get("ATR", 0.0) or 0.0)

        if model is not None:
            try:
                obs = _normalize_stacked(env, df, i, cash, shares)
                # Stochastic sampling matches the live signal endpoint; argmax-only
                # policies that lean toward HOLD would otherwise never trade here.
                action, _ = model.predict(obs, deterministic=False)
                action = int(action[0])
            except Exception:
                action, _ = calculate_fallback_signal(df.iloc[: i + 1], 0.0)
        else:
            action, _ = calculate_fallback_signal(df.iloc[: i + 1], 0.0)

        new_cash, new_shares, kind = _apply_action(action, cash, shares, price, atr)
        if kind != "hold":
            trades.append(
                {
                    "ts": int(df.iloc[i]["Date"].timestamp()) if hasattr(df.iloc[i]["Date"], "timestamp") else int(i),
                    "price": price,
                    "action": action,
                    "kind": kind,
                    "cash": new_cash,
                    "shares": new_shares,
                }
            )
            markers.append(
                {
                    "time": int(df.iloc[i]["Date"].timestamp()) if hasattr(df.iloc[i]["Date"], "timestamp") else int(i),
                    "kind": kind,
                    "price": price,
                }
            )
        cash, shares = new_cash, new_shares

        equity_curve.append(cash + shares * price)

    final_equity = equity_curve[-1] if equity_curve else INITIAL_BALANCE
    returns = np.diff(equity_curve) / np.array(equity_curve[:-1]) if len(equity_curve) > 1 else np.array([0.0])
    volatility = float(np.std(returns) * np.sqrt(252)) if len(returns) else 0.0
    sharpe = float((np.mean(returns) * 252 - 0.02) / volatility) if volatility > 0 else 0.0
    running_max = np.maximum.accumulate(equity_curve) if equity_curve else np.array([INITIAL_BALANCE])
    drawdowns = (np.array(equity_curve) - running_max) / running_max
    max_dd = float(np.min(drawdowns)) if len(drawdowns) else 0.0

    # Buy & hold baseline for fair comparison.
    first_price = float(df.iloc[0]["Close"])
    last_price = float(df.iloc[-1]["Close"])
    bh_return = (last_price - first_price) / first_price

    return {
        "ticker": ticker,
        "source": source,
        "initial_balance": INITIAL_BALANCE,
        "final_equity": float(final_equity),
        "total_return": float((final_equity - INITIAL_BALANCE) / INITIAL_BALANCE),
        "buy_hold_return": float(bh_return),
        "outperformance": float((final_equity - INITIAL_BALANCE) / INITIAL_BALANCE - bh_return),
        "sharpe": sharpe,
        "volatility": volatility,
        "max_drawdown": max_dd,
        "total_trades": len(trades),
        "equity_curve": [float(x) for x in equity_curve],
        "markers": markers,
        "bars": len(df),
    }

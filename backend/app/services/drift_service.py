"""Concept-drift monitor.

Two cheap drift signals you can get from existing data without labels:

1. **Return-distribution drift** — compare the recent window's returns
   (mean, volatility, skew) against a longer baseline. A fat change in any
   of these means the market regime moved under the model.

2. **Policy-output drift** — replay the policy on the same bars and look at
   how action counts shift versus the backtest baseline. A policy that was
   mixed-BUY/SELL in training going 100% HOLD now is a strong drift signal.

A single ``drift_score`` ∈ [0, 1] aggregates both. ``level`` summarises it:
    < 0.33 ok · 0.33–0.66 watch · > 0.66 retrain
"""
from __future__ import annotations

from typing import List

import numpy as np

from backend.app.services import market_service as ms
from backend.app.services.backtest_service import run_backtest


def _safe(x) -> float:
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return 0.0
        return v
    except (TypeError, ValueError):
        return 0.0


def _action_dist(markers: List[dict]) -> dict:
    buys = sum(1 for m in markers if m.get("kind") == "buy")
    sells = sum(1 for m in markers if m.get("kind") == "sell")
    total = max(1, buys + sells)
    return {"buy_pct": buys / total, "sell_pct": sells / total, "trades": buys + sells}


def _kl(p: float, q: float, eps: float = 1e-6) -> float:
    """Pointwise KL contribution, p·log(p/q), both clamped away from 0."""
    p = max(p, eps)
    q = max(q, eps)
    return p * np.log(p / q)


def compute_drift(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    recent_frac: float = 0.2,
) -> dict:
    """Return drift metrics for ``ticker``.

    ``recent_frac`` is the slice taken as "recent" (default: last 20% of bars).
    The rest of the series acts as the baseline window.
    """
    df = ms.fetch_price_df(ticker, period=period, interval=interval)
    if df is None or df.empty or len(df) < 60:
        return {"ok": False, "reason": "not enough bars", "bars": 0 if df is None else len(df)}

    df = ms.add_advanced_indicators(df)
    if df.empty:
        return {"ok": False, "reason": "no bars after indicators"}

    n = len(df)
    split = max(30, int(n * (1 - recent_frac)))
    baseline = df.iloc[:split].reset_index(drop=True)
    recent = df.iloc[split:].reset_index(drop=True)
    if len(recent) < 10:
        return {"ok": False, "reason": "recent window too small", "bars": n}

    # --- 1) Return distribution drift ---
    b_ret = baseline["Close"].pct_change().dropna()
    r_ret = recent["Close"].pct_change().dropna()

    b_mean, r_mean = _safe(b_ret.mean()), _safe(r_ret.mean())
    b_std, r_std = _safe(b_ret.std()), _safe(r_ret.std())
    b_skew, r_skew = _safe(b_ret.skew()), _safe(r_ret.skew())

    # Normalised distances, clipped so a single outlier window doesn't explode.
    mean_shift = min(1.0, abs(r_mean - b_mean) / (b_std + 1e-6))
    vol_shift = min(1.0, abs(r_std - b_std) / (b_std + 1e-6))
    skew_shift = min(1.0, abs(r_skew - b_skew) / 2.0)
    return_drift = float(0.4 * vol_shift + 0.4 * mean_shift + 0.2 * skew_shift)

    # --- 2) Policy-output drift ---
    try:
        baseline_report = run_backtest(ticker, baseline, max_bars=len(baseline))
        recent_report = run_backtest(ticker, recent, max_bars=len(recent))
    except Exception as e:
        return {"ok": False, "reason": f"policy backtest failed: {e}"}

    b_dist = _action_dist(baseline_report["markers"])
    r_dist = _action_dist(recent_report["markers"])

    # KL between {buy, sell, hold} distributions.
    b_hold = 1.0 - b_dist["buy_pct"] - b_dist["sell_pct"]
    r_hold = 1.0 - r_dist["buy_pct"] - r_dist["sell_pct"]
    kl = (
        _kl(r_dist["buy_pct"], b_dist["buy_pct"])
        + _kl(r_dist["sell_pct"], b_dist["sell_pct"])
        + _kl(r_hold, b_hold)
    )
    # KL is unbounded; squash into [0,1] with a soft cap.
    policy_drift = float(min(1.0, kl / 0.5))

    # --- 3) Realized-return drift (did the policy's recent PnL collapse?) ---
    b_cagr = baseline_report["total_return"]
    r_cagr = recent_report["total_return"]
    pnl_gap = r_cagr - b_cagr  # negative = worse recently
    pnl_drift = float(min(1.0, max(0.0, -pnl_gap)))  # only penalise worsening

    drift_score = float(min(1.0, 0.4 * return_drift + 0.35 * policy_drift + 0.25 * pnl_drift))
    if drift_score < 0.33:
        level = "ok"
    elif drift_score < 0.66:
        level = "watch"
    else:
        level = "retrain"

    return {
        "ok": True,
        "ticker": ticker,
        "bars": n,
        "baseline_bars": len(baseline),
        "recent_bars": len(recent),
        "drift_score": drift_score,
        "level": level,
        "return_drift": return_drift,
        "policy_drift": policy_drift,
        "pnl_drift": pnl_drift,
        "baseline": {
            "mean": b_mean,
            "std": b_std,
            "skew": b_skew,
            "buy_pct": b_dist["buy_pct"],
            "sell_pct": b_dist["sell_pct"],
            "total_return": b_cagr,
        },
        "recent": {
            "mean": r_mean,
            "std": r_std,
            "skew": r_skew,
            "buy_pct": r_dist["buy_pct"],
            "sell_pct": r_dist["sell_pct"],
            "total_return": r_cagr,
        },
    }

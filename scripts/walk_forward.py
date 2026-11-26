"""Rolling walk-forward validation.

Splits each ticker's history into rolling ``train / test`` windows and runs
the current policy's backtest on each test window. The result tells you:

  * Whether returns are consistent across periods (good) or driven by a
    single lucky window (overfit / regime-specific).
  * Whether volatility of returns is stable — a big drift in per-window
    std implies the policy needs retraining.

This DOES NOT retrain between windows — it evaluates the already-trained
policy under walk-forward CONDITIONS. Retrain-between-windows ("expanding
window retraining") is a heavy variant we can add later if needed.

Usage:
    python3 scripts/walk_forward.py --ticker BTC-USD --windows 6 --period 2y
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

from src.utils.technical_indicators import add_advanced_indicators  # noqa: E402
from backend.app.services.backtest_service import run_backtest  # noqa: E402


def _fetch(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise SystemExit(f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime": "Date"}, inplace=True)
    return df


def walk_forward(ticker: str, period: str, interval: str, windows: int) -> List[dict]:
    raw = _fetch(ticker, period, interval)
    df = add_advanced_indicators(raw)
    if df.empty:
        raise SystemExit(f"{ticker}: no bars after indicators")

    n = len(df)
    chunk = n // windows
    if chunk < 40:
        raise SystemExit(
            f"{ticker}: only {n} bars → {chunk}/window < 40. Use --period longer or fewer --windows."
        )

    reports: List[dict] = []
    for w in range(windows):
        lo = w * chunk
        hi = (w + 1) * chunk if w < windows - 1 else n
        window_df = df.iloc[lo:hi].reset_index(drop=True)
        try:
            r = run_backtest(ticker, window_df, max_bars=len(window_df))
        except Exception as e:
            print(f"  window {w + 1}: ERROR {e}")
            continue
        reports.append({
            "window": w + 1,
            "bars": len(window_df),
            "pnl": r["total_return"],
            "bh": r["buy_hold_return"],
            "alpha": r["outperformance"],
            "sharpe": r["sharpe"],
            "max_dd": r["max_drawdown"],
            "trades": r["total_trades"],
            "start": str(window_df.iloc[0]["Date"].date()) if hasattr(window_df.iloc[0]["Date"], "date") else str(window_df.iloc[0]["Date"]),
            "end": str(window_df.iloc[-1]["Date"].date()) if hasattr(window_df.iloc[-1]["Date"], "date") else str(window_df.iloc[-1]["Date"]),
        })
    return reports


def summarise(reports: List[dict]) -> dict:
    if not reports:
        return {"ok": False}
    pnls = np.array([r["pnl"] for r in reports])
    alphas = np.array([r["alpha"] for r in reports])
    return {
        "ok": True,
        "n_windows": len(reports),
        "pnl_mean": float(pnls.mean()),
        "pnl_std": float(pnls.std()),
        "alpha_mean": float(alphas.mean()),
        "alpha_std": float(alphas.std()),
        "pnl_positive_windows": int((pnls > 0).sum()),
        "alpha_positive_windows": int((alphas > 0).sum()),
        "worst_pnl": float(pnls.min()),
        "best_pnl": float(pnls.max()),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--period", default="2y")
    p.add_argument("--interval", default="1d")
    p.add_argument("--windows", type=int, default=6)
    args = p.parse_args()

    print(f"Walk-forward on {args.ticker}: {args.windows} windows of {args.period} at {args.interval}")
    print()

    reports = walk_forward(args.ticker, args.period, args.interval, args.windows)
    print(f'{"Window":<8} {"Start":<12} {"End":<12} {"PnL":>8} {"B&H":>8} {"Alpha":>8} {"Sharpe":>7} {"Trades":>7}')
    print("-" * 80)
    for r in reports:
        print(f'{r["window"]:<8} {r["start"]:<12} {r["end"]:<12} '
              f'{r["pnl"]*100:>+7.2f}% {r["bh"]*100:>+7.2f}% {r["alpha"]*100:>+7.2f}% '
              f'{r["sharpe"]:>7.2f} {r["trades"]:>7d}')
    print("-" * 80)

    summ = summarise(reports)
    if not summ["ok"]:
        return

    print()
    print(f'Mean PnL   : {summ["pnl_mean"]*100:+.2f}%   (std {summ["pnl_std"]*100:.2f}%)')
    print(f'Mean Alpha : {summ["alpha_mean"]*100:+.2f}%   (std {summ["alpha_std"]*100:.2f}%)')
    print(f'Positive-PnL   windows: {summ["pnl_positive_windows"]}/{summ["n_windows"]}')
    print(f'Positive-Alpha windows: {summ["alpha_positive_windows"]}/{summ["n_windows"]}')
    print(f'Worst/Best PnL: {summ["worst_pnl"]*100:+.2f}% / {summ["best_pnl"]*100:+.2f}%')

    # Consistency flag
    if summ["pnl_std"] > 0.15:
        print()
        print("⚠️  High PnL variance across windows — results are regime-specific, not robust.")
    if summ["alpha_positive_windows"] >= summ["n_windows"] * 0.7:
        print("✓  Alpha positive in ≥70% of windows — policy outperforms B&H consistently.")


if __name__ == "__main__":
    main()

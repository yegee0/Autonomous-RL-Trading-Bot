"""Side-by-side backtest of every available expert head + ensemble + buy & hold.

Reads models from ``models/trained/``. Missing heads are skipped (printed as --).
No network calls to the running backend — pulls data and runs the backtester
directly, so it works even if the API is down.

Usage:
    python3 scripts/evaluate_ensemble.py
    python3 scripts/evaluate_ensemble.py --tickers BTC-USD,AAPL --period 6mo
    python3 scripts/evaluate_ensemble.py --save report.md   # markdown report
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import yfinance as yf  # noqa: E402

from src.agents.ensemble import classify_regime, _load_expert  # noqa: E402
from src.agents.rl_agent import (
    calculate_fallback_signal, load_agent, _paths_for,
)
from src.models.trading_env import COMMISSION, SPREAD_BPS, SLIPPAGE_BPS_PER_ATR, build_observation
from src.utils.technical_indicators import add_advanced_indicators

INITIAL_BALANCE = 10_000.0
HEADS = ("general", "trend", "range", "crisis")


def _fetch(ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
    except Exception as e:
        print(f"[data] {ticker} fetch error: {e}")
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime": "Date"}, inplace=True)
    return df


def _fill_price(mid: float, atr: float, frac: float, side: str) -> float:
    spread = SPREAD_BPS / 10_000.0
    size_impact = (atr / max(mid, 1e-9)) * SLIPPAGE_BPS_PER_ATR * abs(frac) / 10.0
    bps = spread + size_impact
    return mid * (1.0 + bps if side == "buy" else 1.0 - bps)


def _apply_action(action: int, cash: float, shares: float, price: float, atr: float):
    if action in (1, 2, 3):
        frac = {1: 0.25, 2: 0.50, 3: 1.0}[action]
        spend = cash * frac
        if spend > 10 and cash >= spend * (1 + COMMISSION):
            fill = _fill_price(price, atr, frac, "buy")
            cash -= spend * (1 + COMMISSION)
            shares += spend / fill
            return cash, shares, "buy"
    elif action in (4, 5, 6):
        if shares > 0:
            frac = {4: 0.25, 5: 0.50, 6: 1.0}[action]
            sold = shares * frac
            fill = _fill_price(price, atr, frac, "sell")
            cash += sold * fill * (1 - COMMISSION)
            shares -= sold
            return cash, shares, "sell"
    return cash, shares, "hold"


def _stacked_obs(env, df: pd.DataFrame, idx: int, cash: float, shares: float) -> np.ndarray:
    from src.agents.rl_agent import N_STACK
    start = max(0, idx - N_STACK + 1)
    vecnorm = env.venv if hasattr(env, "venv") else env
    frames = []
    for i in range(start, idx + 1):
        raw = build_observation(df, i, cash, shares, INITIAL_BALANCE).reshape(1, -1)
        frames.append(vecnorm.normalize_obs(raw))
    while len(frames) < N_STACK:
        frames.insert(0, frames[0])
    return np.concatenate(frames, axis=1).astype(np.float32)


def _run_backtest(df: pd.DataFrame, head_name: str, vix: Optional[float] = None) -> Dict:
    """Run a one-head backtest over df. head_name='buyhold' → pure B&H.
    head_name='ensemble' → regime-routed to best available head each bar."""
    cash, shares = INITIAL_BALANCE, 0.0
    equity_curve: List[float] = []
    trades = 0

    model_cache: Dict[str, Tuple] = {}

    for i in range(len(df)):
        price = float(df.iloc[i]["Close"])
        atr = float(df.iloc[i].get("ATR", 0.0) or 0.0)

        if head_name == "buyhold":
            if i == 0:
                shares = cash / price
                cash = 0.0
            equity_curve.append(cash + shares * price)
            continue

        # Which head to use?
        if head_name == "ensemble":
            # look at last 60 bars for regime
            regime = classify_regime(df.iloc[max(0, i - 60):i + 1], vix=vix)
            chosen_head = regime
        else:
            chosen_head = head_name

        if chosen_head not in model_cache:
            model, env = _load_expert(chosen_head)
            if model is None and chosen_head != "general":
                # fall back to general if specialist missing
                model, env = _load_expert("general")
            if model is None:
                model, env = load_agent("fallback")
            model_cache[chosen_head] = (model, env)
        model, env = model_cache[chosen_head]

        if model is None:
            action, _ = calculate_fallback_signal(df.iloc[: i + 1], 0.0)
        else:
            try:
                obs = _stacked_obs(env, df, i, cash, shares)
                a, _ = model.predict(obs, deterministic=False)
                action = int(a[0])
            except Exception:
                action, _ = calculate_fallback_signal(df.iloc[: i + 1], 0.0)

        new_cash, new_shares, kind = _apply_action(action, cash, shares, price, atr)
        if kind != "hold":
            trades += 1
        cash, shares = new_cash, new_shares
        equity_curve.append(cash + shares * price)

    final = equity_curve[-1] if equity_curve else INITIAL_BALANCE
    returns = np.diff(equity_curve) / np.array(equity_curve[:-1]) if len(equity_curve) > 1 else np.array([0.0])
    vol = float(np.std(returns) * np.sqrt(252)) if len(returns) else 0.0
    sharpe = float((np.mean(returns) * 252 - 0.02) / vol) if vol > 0 else 0.0
    running_max = np.maximum.accumulate(equity_curve) if equity_curve else np.array([INITIAL_BALANCE])
    dd_series = (np.array(equity_curve) - running_max) / running_max
    max_dd = float(np.min(dd_series)) if len(dd_series) else 0.0

    return {
        "pnl": (final - INITIAL_BALANCE) / INITIAL_BALANCE,
        "final": final,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "trades": trades,
    }


def _head_available(head: str) -> bool:
    model_path, vec_path = _paths_for(head)
    return os.path.exists(model_path) and os.path.exists(vec_path)


def evaluate(tickers: List[str], period: str, interval: str) -> List[Dict]:
    rows = []
    for t in tickers:
        print(f"[eval] {t} …", end=" ", flush=True)
        df = _fetch(t, period=period, interval=interval)
        if df is None:
            print("no data")
            continue
        df = add_advanced_indicators(df)
        if df.empty:
            print("no bars after indicators")
            continue

        row = {"ticker": t, "bars": len(df)}
        for head in HEADS + ("ensemble", "buyhold"):
            if head in HEADS and not _head_available(head):
                row[head] = None
                continue
            try:
                r = _run_backtest(df, head)
                row[head] = r
            except Exception as e:
                print(f"[{head}:err {e}]", end=" ")
                row[head] = None
        print("ok")
        rows.append(row)
    return rows


def _fmt_cell(r: Optional[Dict]) -> str:
    if r is None:
        return "    --   "
    pnl = r["pnl"] * 100
    return f"{pnl:>+7.2f}%"


def print_report(rows: List[Dict]) -> str:
    out = []
    hdr = f'{"Ticker":<10} {"General":>10} {"Trend":>10} {"Range":>10} {"Crisis":>10} {"Ensemble":>10} {"B&H":>10}'
    out.append(hdr)
    out.append("-" * len(hdr))

    totals = {k: [] for k in HEADS + ("ensemble", "buyhold")}
    for row in rows:
        line = f'{row["ticker"]:<10}'
        for h in HEADS + ("ensemble", "buyhold"):
            cell = row.get(h)
            line += f' {_fmt_cell(cell):>10}'
            if cell is not None:
                totals[h].append(cell["pnl"] * 100)
        out.append(line)

    out.append("-" * len(hdr))
    avg_line = f'{"AVG":<10}'
    for h in HEADS + ("ensemble", "buyhold"):
        vals = totals[h]
        if vals:
            avg = sum(vals) / len(vals)
            avg_line += f' {avg:>+9.2f}%'
        else:
            avg_line += f' {"--":>10}'
    out.append(avg_line)

    text = "\n".join(out)
    print(text)
    return text


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--tickers",
        default="BTC-USD,ETH-USD,SOL-USD,AAPL,TSLA,MSFT,NVDA,GOOGL",
    )
    p.add_argument("--period", default="1y")
    p.add_argument("--interval", default="1d")
    p.add_argument("--save", default=None, help="Write a markdown report to this path")
    args = p.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    print("Available heads:",
          [h for h in HEADS if _head_available(h)] or "none (only fallback)")
    print(f"Period={args.period}  Interval={args.interval}")
    print()

    rows = evaluate(tickers, args.period, args.interval)
    print()
    text = print_report(rows)

    if args.save:
        with open(args.save, "w") as f:
            f.write("# TradeMaster ensemble evaluation\n\n")
            f.write(f"Period={args.period} Interval={args.interval}\n\n")
            f.write("```\n" + text + "\n```\n")
        print(f"\nSaved report → {args.save}")


if __name__ == "__main__":
    main()

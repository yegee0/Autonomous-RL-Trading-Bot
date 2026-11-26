"""Portfolio-level risk: pairwise correlation, parametric + historical VaR.

Inputs are the paper portfolio's open positions plus 60d of daily closes
per ticker. Returns a snapshot the API and guardrail can both use.

Parametric 95% VaR uses the position-weighted portfolio variance:
    var_p = w @ Σ @ w     where Σ = cov(returns), w = position_value/equity
    VaR95 = 1.645 * sqrt(var_p) * equity

Historical 95% VaR replays the last N daily returns on the current
weights and takes the 5th percentile loss. The two usually agree within
10–20%; a wide divergence means returns are heavy-tailed (fat left).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class PositionSnapshot:
    ticker: str
    qty: float
    price: float

    @property
    def value(self) -> float:
        return self.qty * self.price


@dataclass
class PortfolioRisk:
    equity: float
    cash: float
    market_value: float
    gross_exposure_pct: float       # sum(|pos|) / equity
    net_exposure_pct: float         # sum(pos) / equity (ignores shorts; always >=0 for long-only)
    concentration_pct: float        # biggest single position / equity
    var_95_parametric: float        # dollar loss, 1-day 95% CL
    var_95_historical: float        # dollar loss, 1-day 95% CL
    portfolio_vol_annualized: float
    correlations: Dict[str, Dict[str, float]]
    tickers: List[str]
    warnings: List[str]


def _fetch_closes(tickers: List[str], lookback_days: int = 60) -> Optional[pd.DataFrame]:
    """One batched yfinance call for all tickers → wide DataFrame of closes."""
    if not tickers:
        return None
    try:
        data = yf.download(
            tickers=" ".join(tickers),
            period=f"{lookback_days + 5}d",
            interval="1d",
            progress=False,
            group_by="ticker",
            auto_adjust=False,
        )
    except Exception:
        return None
    if data is None or data.empty:
        return None

    # yfinance returns different shapes for 1 vs many tickers.
    if len(tickers) == 1:
        t = tickers[0]
        if "Close" not in data.columns:
            return None
        return data[["Close"]].rename(columns={"Close": t}).dropna()

    closes: Dict[str, pd.Series] = {}
    for t in tickers:
        try:
            closes[t] = data[t]["Close"].dropna()
        except Exception:
            continue
    if not closes:
        return None
    return pd.DataFrame(closes).dropna(how="all")


def compute_risk(
    positions: List[PositionSnapshot],
    cash: float,
    exposure_cap_pct: float = 0.60,
    concentration_cap_pct: float = 0.25,
    lookback_days: int = 60,
) -> PortfolioRisk:
    """Return a full-portfolio risk snapshot. Zero positions → mostly-empty one."""
    mv = sum(p.value for p in positions)
    equity = cash + mv
    tickers = [p.ticker for p in positions]
    warnings: List[str] = []

    if not positions or equity <= 0:
        return PortfolioRisk(
            equity=equity, cash=cash, market_value=mv,
            gross_exposure_pct=0.0, net_exposure_pct=0.0, concentration_pct=0.0,
            var_95_parametric=0.0, var_95_historical=0.0, portfolio_vol_annualized=0.0,
            correlations={}, tickers=tickers, warnings=warnings,
        )

    gross = sum(abs(p.value) for p in positions) / equity
    net = mv / equity
    biggest = max((abs(p.value) for p in positions), default=0.0) / equity

    if gross > exposure_cap_pct:
        warnings.append(f"Gross exposure {gross:.1%} > cap {exposure_cap_pct:.0%}")
    if biggest > concentration_cap_pct:
        warnings.append(f"Single-position concentration {biggest:.1%} > cap {concentration_cap_pct:.0%}")

    closes = _fetch_closes(tickers, lookback_days=lookback_days)
    if closes is None or len(closes) < 10:
        warnings.append("Not enough price history for VaR — need ≥10 daily bars")
        return PortfolioRisk(
            equity=equity, cash=cash, market_value=mv,
            gross_exposure_pct=gross, net_exposure_pct=net, concentration_pct=biggest,
            var_95_parametric=0.0, var_95_historical=0.0, portfolio_vol_annualized=0.0,
            correlations={}, tickers=tickers, warnings=warnings,
        )

    rets = closes.pct_change().dropna()
    # Align weight vector with the columns yfinance actually returned.
    weights = np.array([
        next((p.value for p in positions if p.ticker == t), 0.0) / equity
        for t in rets.columns
    ])

    cov = rets.cov().values
    port_var_daily = float(weights @ cov @ weights)
    port_vol_daily = max(port_var_daily, 0.0) ** 0.5
    var95_param = 1.645 * port_vol_daily * equity
    port_vol_ann = port_vol_daily * (252 ** 0.5)

    port_returns = rets.values @ weights
    if len(port_returns) >= 20:
        var95_hist = -float(np.percentile(port_returns, 5)) * equity
    else:
        var95_hist = var95_param

    corr = rets.corr().round(3)
    corr_dict: Dict[str, Dict[str, float]] = {
        a: {b: float(corr.loc[a, b]) for b in corr.columns} for a in corr.index
    }

    if len(port_returns) >= 20 and var95_hist > var95_param * 1.5:
        warnings.append("Historical VaR >> parametric: fat-tail risk, trust historical")

    return PortfolioRisk(
        equity=equity, cash=cash, market_value=mv,
        gross_exposure_pct=gross, net_exposure_pct=net, concentration_pct=biggest,
        var_95_parametric=float(var95_param), var_95_historical=float(var95_hist),
        portfolio_vol_annualized=float(port_vol_ann),
        correlations=corr_dict, tickers=list(rets.columns), warnings=warnings,
    )


def would_breach_exposure(
    positions: List[PositionSnapshot],
    cash: float,
    extra_notional: float,
    ticker: str,
    cap_pct: float = 0.60,
) -> Tuple[bool, float, float]:
    """Simulate adding `extra_notional` to `ticker` and check the gross cap.

    Returns (would_breach, projected_gross_pct, equity).
    """
    mv = sum(p.value for p in positions)
    equity = cash + mv
    if equity <= 0:
        return False, 0.0, equity
    extra_abs = abs(extra_notional)
    new_gross_abs = sum(abs(p.value) for p in positions) + extra_abs
    new_pct = new_gross_abs / (equity + extra_abs if extra_notional > 0 else equity)
    return new_pct > cap_pct, float(new_pct), float(equity)

"""Historical signal replay — runs the policy across the last N bars.

Reuses the backtest simulator and surfaces its markers for chart overlays.
"""
from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.backtest import BacktestMarker
from backend.app.services import market_service as ms
from backend.app.services.backtest_service import run_backtest
from typing import List

router = APIRouter()


@router.get("/signals/{ticker}/history", response_model=List[BacktestMarker])
def signal_history(
    ticker: str,
    period: str = Query("3mo"),
    interval: str = Query("1d"),
    max_bars: int = Query(200, ge=20, le=500),
) -> List[BacktestMarker]:
    ticker = ticker.upper().strip()
    df = ms.fetch_price_df(ticker, period=period, interval=interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    df = ms.add_advanced_indicators(df)
    if df.empty:
        raise HTTPException(status_code=422, detail="Not enough data after indicators")

    report = run_backtest(ticker, df, max_bars=max_bars)
    return [BacktestMarker(**m) for m in report["markers"]]

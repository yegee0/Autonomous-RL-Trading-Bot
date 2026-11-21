from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.backtest import BacktestResponse
from backend.app.services import market_service as ms
from backend.app.services.backtest_service import run_backtest

router = APIRouter()


@router.get("/backtest/{ticker}", response_model=BacktestResponse)
def backtest(
    ticker: str,
    period: str = Query("6mo"),
    interval: str = Query("1d"),
    max_bars: int = Query(400, ge=20, le=2000),
) -> BacktestResponse:
    ticker = ticker.upper().strip()
    df = ms.fetch_price_df(ticker, period=period, interval=interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    df = ms.add_advanced_indicators(df)
    if df.empty:
        raise HTTPException(status_code=422, detail="Not enough data after indicators")

    try:
        report = run_backtest(ticker, df, max_bars=max_bars)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}")
    return BacktestResponse(**report)

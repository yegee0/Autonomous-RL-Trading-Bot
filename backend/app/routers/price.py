from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.market import Candle
from backend.app.services import market_service as ms

router = APIRouter()


@router.get("/price/{ticker}", response_model=List[Candle])
def get_price(
    ticker: str,
    period: str = Query("3mo"),
    interval: str = Query("1d"),
    limit: int = Query(400, ge=10, le=2000),
) -> List[Candle]:
    ticker = ticker.upper().strip()
    df = ms.fetch_price_df(ticker, period=period, interval=interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    return ms.df_to_candles(df, limit=limit)

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.market import SignalResponse
from backend.app.services import market_service as ms

router = APIRouter()


@router.get("/signal/{ticker}", response_model=SignalResponse)
def get_signal(
    ticker: str,
    period: str = Query("1mo"),
    interval: str = Query("1d"),
    sentiment: float = Query(0.0, ge=-1.0, le=1.0),
) -> SignalResponse:
    ticker = ticker.upper().strip()
    df = ms.fetch_price_df(ticker, period=period, interval=interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    df = ms.add_advanced_indicators(df)
    return ms.compute_signal(ticker, df, sentiment)

from fastapi import APIRouter, HTTPException

from backend.app.schemas.market import AnalyzeRequest, AnalyzeResponse
from backend.app.services import market_service as ms

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    ticker = req.ticker.upper().strip()
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="Invalid ticker")

    df = ms.fetch_price_df(ticker, period=req.period, interval=req.interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    df = ms.add_advanced_indicators(df)

    # Analyze is the fast path: no news/sentiment here (frontend calls /api/news separately).
    signal = ms.compute_signal(ticker, df, sentiment=0.0)
    risk = ms.compute_risk(df)
    sizing = ms.compute_sizing(df, balance=10_000.0, confidence=max(signal.confidence, 0.5))
    indicators = ms.extract_indicators(df)
    candles = ms.df_to_candles(df)

    return AnalyzeResponse(
        ticker=ticker,
        price=signal.price,
        candles=candles,
        indicators=indicators,
        signal=signal,
        risk=risk,
        sizing=sizing,
        news=[],
        sentiment_score=0.0,
    )

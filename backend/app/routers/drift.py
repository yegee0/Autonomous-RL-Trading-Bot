from fastapi import APIRouter, HTTPException, Query

from backend.app.services import drift_service as ds

router = APIRouter()


@router.get("/drift/{ticker}")
def drift(
    ticker: str,
    period: str = Query("1y"),
    interval: str = Query("1d"),
    recent_frac: float = Query(0.2, ge=0.05, le=0.5),
) -> dict:
    ticker = ticker.upper().strip()
    try:
        return ds.compute_drift(ticker, period=period, interval=interval, recent_frac=recent_frac)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drift analysis failed: {e}")

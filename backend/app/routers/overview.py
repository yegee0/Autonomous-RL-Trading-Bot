from fastapi import APIRouter, HTTPException

from backend.app.schemas.market import Fundamentals, MacroSnapshot
from backend.app.services import market_service as ms

router = APIRouter()


@router.get("/overview/{ticker}", response_model=Fundamentals)
def get_fundamentals(ticker: str) -> Fundamentals:
    ticker = ticker.upper().strip()
    try:
        return ms.fetch_fundamentals(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fundamentals fetch failed: {e}")


@router.get("/macro", response_model=MacroSnapshot)
def get_macro() -> MacroSnapshot:
    try:
        return ms.fetch_macro_snapshot()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Macro fetch failed: {e}")

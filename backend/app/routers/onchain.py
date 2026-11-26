from fastapi import APIRouter, HTTPException
from typing import Optional

from pydantic import BaseModel

from backend.app.services import onchain_service as oc

router = APIRouter()


class OnChain(BaseModel):
    symbol: str
    funding_rate: Optional[float] = None
    funding_annualized: Optional[float] = None
    next_funding_time: Optional[int] = None
    mark_price: Optional[float] = None
    open_interest: Optional[float] = None
    open_interest_usd: Optional[float] = None
    oi_change_24h: Optional[float] = None
    crowded_side: Optional[str] = None


@router.get("/onchain/{ticker}", response_model=OnChain)
def onchain(ticker: str) -> OnChain:
    ticker = ticker.upper().strip()
    snap = oc.fetch_onchain(ticker)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not a tradable perpetual futures pair")
    return OnChain(**snap.__dict__)

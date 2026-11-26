from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.services import options_service as oc

router = APIRouter()


class OptionRowOut(BaseModel):
    strike: float
    last: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_vol: float


class OptionChainOut(BaseModel):
    ticker: str
    expiry: str
    spot: float
    calls: List[OptionRowOut]
    puts: List[OptionRowOut]
    atm_iv: Optional[float] = None
    skew_25d: Optional[float] = None
    put_call_oi: Optional[float] = None
    expiries: List[str]


@router.get("/options/{ticker}", response_model=OptionChainOut)
def options_chain(ticker: str, expiry: Optional[str] = Query(None)) -> OptionChainOut:
    chain = oc.fetch_options(ticker.upper().strip(), expiry=expiry)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"No option chain for {ticker} (crypto / BIST / unknown ticker)",
        )
    return OptionChainOut(
        ticker=chain.ticker,
        expiry=chain.expiry,
        spot=chain.spot,
        calls=[OptionRowOut(**r.__dict__) for r in chain.calls],
        puts=[OptionRowOut(**r.__dict__) for r in chain.puts],
        atm_iv=chain.atm_iv,
        skew_25d=chain.skew_25d,
        put_call_oi=chain.put_call_oi,
        expiries=chain.expiries,
    )

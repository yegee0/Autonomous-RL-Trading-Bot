from typing import Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.services import paper_store as ps
from backend.app.services.market_service import fetch_price_df
from src.utils.portfolio_risk import PositionSnapshot, compute_risk

router = APIRouter()


class PortfolioRiskResponse(BaseModel):
    equity: float
    cash: float
    market_value: float
    gross_exposure_pct: float
    net_exposure_pct: float
    concentration_pct: float
    var_95_parametric: float
    var_95_historical: float
    portfolio_vol_annualized: float
    correlations: Dict[str, Dict[str, float]]
    tickers: List[str]
    warnings: List[str]


def _latest_price(ticker: str) -> float:
    df = fetch_price_df(ticker, period="5d", interval="1d")
    if df is None or df.empty:
        return 0.0
    return float(df.iloc[-1]["Close"])


@router.get("/paper/risk", response_model=PortfolioRiskResponse)
def portfolio_risk() -> PortfolioRiskResponse:
    positions = ps.list_positions()
    snaps = [
        PositionSnapshot(ticker=p.ticker, qty=p.qty, price=_latest_price(p.ticker) or p.avg_cost)
        for p in positions
    ]
    snaps = [s for s in snaps if s.price > 0 and s.qty > 0]
    risk = compute_risk(snaps, cash=ps.get_cash())
    return PortfolioRiskResponse(**risk.__dict__)

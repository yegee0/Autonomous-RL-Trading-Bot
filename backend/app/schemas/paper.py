from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PaperTradeRequest(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    qty: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


class PaperTrade(BaseModel):
    id: int
    ts: int
    ticker: str
    side: Literal["buy", "sell"]
    qty: float
    price: float
    fee: float


class PaperPosition(BaseModel):
    ticker: str
    qty: float
    avg_cost: float
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None


class PaperPortfolio(BaseModel):
    cash: float
    positions: List[PaperPosition]
    total_market_value: float
    total_equity: float

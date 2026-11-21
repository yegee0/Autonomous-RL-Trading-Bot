from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.paper import (
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PaperTradeRequest,
)
from backend.app.services import market_service as ms
from backend.app.services import paper_store as ps

router = APIRouter()


def _enrich_positions(positions: List[ps.Position]) -> List[PaperPosition]:
    out: List[PaperPosition] = []
    for p in positions:
        df = ms.fetch_price_df(p.ticker, period="5d", interval="1d")
        last = float(df.iloc[-1]["Close"]) if df is not None and not df.empty else p.avg_cost
        mv = p.qty * last
        pnl = mv - (p.qty * p.avg_cost)
        out.append(
            PaperPosition(
                ticker=p.ticker,
                qty=p.qty,
                avg_cost=p.avg_cost,
                market_value=mv,
                unrealized_pnl=pnl,
            )
        )
    return out


@router.get("/paper/portfolio", response_model=PaperPortfolio)
def portfolio() -> PaperPortfolio:
    positions = _enrich_positions(ps.list_positions())
    cash = ps.get_cash()
    total_mv = sum((p.market_value or 0.0) for p in positions)
    return PaperPortfolio(
        cash=cash,
        positions=positions,
        total_market_value=total_mv,
        total_equity=cash + total_mv,
    )


@router.get("/paper/trades", response_model=List[PaperTrade])
def trades(limit: int = Query(50, ge=1, le=500), ticker: str | None = None) -> List[PaperTrade]:
    rows = ps.list_trades(limit=limit, ticker=ticker.upper() if ticker else None)
    return [
        PaperTrade(id=r.id, ts=r.ts, ticker=r.ticker, side=r.side, qty=r.qty, price=r.price, fee=r.fee)
        for r in rows
    ]


@router.post("/paper/trade", response_model=PaperTrade)
def trade(req: PaperTradeRequest) -> PaperTrade:
    try:
        t = ps.execute_trade(req.ticker.upper().strip(), req.side, req.qty, req.price)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PaperTrade(id=t.id, ts=t.ts, ticker=t.ticker, side=t.side, qty=t.qty, price=t.price, fee=t.fee)


@router.post("/paper/reset")
def reset() -> dict:
    ps.reset_portfolio()
    return {"status": "reset", "cash": ps.get_cash()}

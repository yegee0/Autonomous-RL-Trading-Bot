from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.paper import (
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PaperTradeRequest,
)
from backend.app.services import guardrails as gr
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
    ticker = req.ticker.upper().strip()

    # Build the equity + position + indicator view the guardrails need.
    positions = {p.ticker: p for p in ps.list_positions()}
    pos = positions.get(ticker)
    cash = ps.get_cash()
    total_mv = sum(p.qty * p.avg_cost for p in positions.values())  # approx, fast path
    equity = cash + total_mv

    rsi = None
    try:
        df = ms.fetch_price_df(ticker, period="1mo", interval="1d")
        if df is not None and not df.empty:
            df = ms.add_advanced_indicators(df)
            if "RSI" in df.columns and not df.empty:
                rsi_val = df.iloc[-1].get("RSI")
                if rsi_val is not None and rsi_val == rsi_val:  # NaN-safe
                    rsi = float(rsi_val)
    except Exception:
        rsi = None  # indicator fetch is best-effort; guardrails degrade gracefully

    decision = gr.check_order(
        ticker=ticker,
        side=req.side,
        qty=req.qty,
        price=req.price,
        equity=equity,
        current_position_qty=pos.qty if pos else 0.0,
        rsi=rsi,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail={"code": decision.code, "message": decision.reason},
        )

    try:
        t = ps.execute_trade(ticker, req.side, req.qty, req.price)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gr.record_fill()
    return PaperTrade(id=t.id, ts=t.ts, ticker=t.ticker, side=t.side, qty=t.qty, price=t.price, fee=t.fee)


@router.post("/paper/reset")
def reset() -> dict:
    ps.reset_portfolio()
    gr.mark_day_start(ps.get_cash())
    gr.reset_kill_switch()
    return {"status": "reset", "cash": ps.get_cash()}


@router.get("/paper/guardrails")
def guardrail_status() -> dict:
    return gr.snapshot()


@router.post("/paper/guardrails/reset")
def guardrail_reset() -> dict:
    gr.reset_kill_switch()
    gr.mark_day_start(_current_equity())
    return gr.snapshot()


def _current_equity() -> float:
    positions = ps.list_positions()
    cash = ps.get_cash()
    total_mv = sum(p.qty * p.avg_cost for p in positions)
    return float(cash + total_mv)

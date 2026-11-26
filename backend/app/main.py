import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.routers import (
    analyze,
    backtest,
    calendar,
    drift,
    live,
    news,
    onchain,
    overview,
    paper,
    portfolio_risk,
    price,
    signal,
    signals_history,
    tickers,
)
from backend.app.services import guardrails as gr
from backend.app.services import paper_store as ps

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend_dist")
if not os.path.isdir(FRONTEND_DIST):
    FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("backend")

app = FastAPI(
    title="TradeMaster API",
    version="0.1.0",
    description="RL-driven market analysis backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("[%s] unhandled error on %s %s", rid, request.method, request.url.path)
        return JSONResponse({"error": "internal_error", "request_id": rid}, status_code=500)
    dur_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = rid
    log.info("[%s] %s %s -> %d (%.1fms)", rid, request.method, request.url.path, response.status_code, dur_ms)
    return response


@app.on_event("startup")
def _init_guardrails() -> None:
    # Snapshot equity so the daily-loss kill-switch has a baseline.
    try:
        positions = ps.list_positions()
        cash = ps.get_cash()
        equity = cash + sum(p.qty * p.avg_cost for p in positions)
        gr.mark_day_start(equity)
        log.info("guardrails baseline equity=%.2f", equity)
    except Exception as e:
        log.warning("guardrails init failed: %s", e)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "trademaster-api",
        "kill_switch_active": gr.kill_switch_active(),
    }


app.include_router(tickers.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(signal.router, prefix="/api")
app.include_router(signals_history.router, prefix="/api")
app.include_router(price.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(paper.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(drift.router, prefix="/api")
app.include_router(onchain.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(portfolio_risk.router, prefix="/api")
app.include_router(live.router)


# ---------- SPA static serving (production) ----------
if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    log.info("Serving SPA from %s", FRONTEND_DIST)

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catchall(full_path: str = ""):
        # API paths handled above; anything else falls through to the SPA shell.
        if full_path.startswith(("api/", "ws/", "docs", "openapi.json")):
            raise HTTPException(status_code=404)
        # Serve concrete files (favicon, robots.txt, etc.) if present.
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        raise HTTPException(status_code=404)
else:
    log.info("No frontend_dist found; API only. Run 'npm run build' in frontend/.")

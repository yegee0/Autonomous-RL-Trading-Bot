# TradeMaster

RL-driven market workbench: regime-routed PPO ensemble scores signals across crypto, US stocks, and BIST — served through a FastAPI backend and a React dashboard.

## Quick start

**Docker (one command):**

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>.

**Local dev:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8000

cd frontend && npm install && npm run dev   # :5173, proxies /api + /ws → :8000
```

## Training

A rule-based classifier routes each bar to one of four PPO heads — `general`, `trend`, `range`, `crisis` — based on ADX, ATR%, VIX, and drawdown. Observations are scale-invariant so the same policy handles BTC at \$60k and AAPL at \$200.

```bash
# Generalist (default; ~30–45 min on CPU for 500k steps)
python scripts/train_general.py --timesteps 500000

# Regime-specific heads
python scripts/train_general.py --regime trend  --timesteps 300000
python scripts/train_general.py --regime range  --timesteps 300000
python scripts/train_general.py --regime crisis --timesteps 300000

# Or train all four in sequence:
./scripts/train_ensemble.sh
```

Models land in `models/trained/`. If a head is missing, the ensemble falls back to the generalist; if none exist, to a deterministic RSI+MACD rule.

**Evaluation:**

```bash
python scripts/evaluate_ensemble.py --period 1y        # head-vs-head-vs-B&H table
python scripts/walk_forward.py --ticker BTC-USD --windows 6   # rolling validation
```

**Pre-trained from Hugging Face:**

```bash
HF_MODEL_REPO=your-user/trademaster-rl-generalist python scripts/download_model.py
```

## Project layout

```
backend/app/        FastAPI app — routers, services, Pydantic schemas
src/agents/         PPO loader, regime ensemble, market intelligence
src/models/         Scale-invariant env, crisis wrapper, policy config
src/utils/          Indicators, data loader, risk manager, regime filter
scripts/            Train / evaluate / walk-forward / HF up- & downloaders
frontend/src/       React + Vite SPA (dashboard, charts, flow panels)
models/trained/     .zip + .pkl artefacts (gitignored)
```

## Environment

| Var | Default | Purpose |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Uvicorn bind |
| `LOG_LEVEL` | `INFO` | Python logging |
| `CORS_ORIGINS` | localhost :5173, :8000 | CORS allowlist |
| `TELEGRAM_BOT_TOKEN` | — | Optional signal alerts |
| `HF_MODEL_REPO` / `HF_MODEL_REV` | — / `main` | Pre-trained model source |
| `REDDIT_CLIENT_ID` / `_SECRET` / `_USER_AGENT` | — | Reddit sentiment (optional) |
| `MAX_POSITION_PCT` / `MAX_ORDER_PCT` / `MAX_DAILY_LOSS_PCT` | 0.20 / 0.10 / 0.05 | Paper-trading guardrails |
| `TRADE_RATE_LIMIT` / `_WINDOW` | 10 / 60s | Order rate limit |
| `EVENT_WINDOW_LOCK` | `1` | Block buys ±30m around FOMC/CPI/NFP/earnings |

See `.env.example`.

## API surface

| | Path | Description |
|---|---|---|
| GET | `/api/health` | Readiness + kill-switch status |
| GET | `/api/tickers` | Catalog + model-availability flag |
| POST | `/api/analyze` | Full dashboard payload (candles, indicators, signal, risk, sizing) |
| GET | `/api/signal/{t}` | Action + confidence + regime + expert used |
| GET | `/api/price/{t}` | OHLCV candles |
| GET | `/api/news/{t}` | Headlines + Reddit + aggregate sentiment |
| GET | `/api/overview/{t}` | Fundamentals (crypto returns `is_crypto`) |
| GET | `/api/macro` | VIX / US10Y / DXY / Fear & Greed |
| GET | `/api/backtest/{t}` | Replay policy over historical bars |
| GET | `/api/drift/{t}` | Feature / policy / PnL drift report |
| GET | `/api/calendar` | Upcoming macro + earnings events |
| GET | `/api/onchain/{t}` | Funding rate + OI + crowded side (crypto) |
| — | `/api/paper/*` | Paper portfolio, trades, guardrails |
| WS | `/ws/live/{t}` | Binance kline stream |
| WS | `/ws/depth/{t}` | Order-book depth20 |
| WS | `/ws/liquidations/{t}` | Forced-liquidation feed |

OpenAPI docs: `/docs`.

## Guardrails

Every paper order passes `check_order` before hitting the ledger — kill-switch, daily-loss cap, rate limit, position size, per-order size, RSI extremes, and ±30m macro-event window. See `backend/app/services/guardrails.py`.

## License

MIT (planned). Trained models released separately on Hugging Face Hub.

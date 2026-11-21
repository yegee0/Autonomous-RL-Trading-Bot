# TradeMaster

An RL-powered market-analysis workbench. One generalist PPO policy, trained on scale-invariant features, scores signals across crypto, US stocks, and BIST. FastAPI backend, React + Vite + Tailwind frontend, Binance WebSocket live feed.

```
┌──────────────────────────┐   HTTP + WS    ┌─────────────────────────────┐
│  Frontend (Vite SPA)     │ ────────────── │  Backend (FastAPI)          │
│  React · Tailwind        │                │  · /api/analyze, /signal    │
│  lightweight-charts      │                │  · /api/price, /news        │
│  TanStack Query          │                │  · /ws/live/{ticker}        │
└──────────────────────────┘                │  Generalist PPO model       │
                                            └─────────────────────────────┘
```

---

## Quick Start — Docker (recommended)

```bash
cp .env.example .env               # optional: fill in TELEGRAM_BOT_TOKEN, HF_MODEL_REPO
docker compose up --build
```

Open <http://localhost:8000> — the SPA and API are served from the same port.

## Quick Start — Local dev

Prereqs: Python 3.10, Node 20, ~2 GB disk (torch + transformers).

```bash
# 1 — backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 2 — frontend (new terminal)
cd frontend
npm install
npm run dev     # opens on :5173, proxies /api and /ws to :8000
```

Visit <http://localhost:5173>.

---

## Model

A single generalist PPO policy serves all tickers. Observations are scale-invariant (ratios + pct returns), so one model handles BTC at \$60k and AAPL at \$200.

### Download a pre-trained model

```bash
HF_MODEL_REPO=your-user/trademaster-rl-generalist \
  python scripts/download_model.py
```

Puts `model_general.zip` + `model_general_vecnorm.pkl` into `models/trained/`.

### Train your own

```bash
python scripts/train_general.py \
  --tickers BTC-USD,ETH-USD,AAPL,TSLA,MSFT,NVDA \
  --timesteps 500000 \
  --period 60d --interval 5m
```

A `MultiTickerEnv` swaps the underlying frame on every reset, so the policy never overfits one asset. 500k steps take ~30–45 min on a mid-range GPU.

If no model is on disk, the backend falls back to a deterministic rule-based signal (RSI + MACD + sentiment).

---

## Project layout

```
.
├── backend/
│   └── app/               FastAPI app, routers, services, Pydantic schemas
├── src/
│   ├── agents/            PPO loader + market intelligence (news/reddit)
│   ├── models/            Scale-invariant env + policy config
│   └── utils/             Indicators, data loader, risk manager, alerts
├── frontend/
│   └── src/               React + Vite SPA
├── scripts/
│   ├── train_general.py   Generalist PPO trainer
│   └── download_model.py  Hugging Face Hub downloader
├── models/trained/        .zip + .pkl artefacts (gitignored)
├── Dockerfile             Multi-stage: frontend build → Python runtime
└── docker-compose.yml     Single-container deployment
```

---

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Uvicorn bind host |
| `PORT` | `8000` | Uvicorn port |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | localhost:5173,:3000,:8000 | Comma-separated CORS allowlist |
| `TELEGRAM_BOT_TOKEN` | — | Optional bot token for signal alerts |
| `HF_MODEL_REPO` | — | HF repo id for `scripts/download_model.py` |
| `HF_MODEL_REV` | `main` | Branch/tag/commit for the above |

Copy `.env.example` → `.env` and fill as needed.

---

## API surface (summary)

| Method | Path | Description |
|---|---|---|
| GET  | `/api/health` | Readiness probe |
| GET  | `/api/tickers` | Catalog + model-availability flag |
| POST | `/api/analyze` | `{ticker, period, interval}` → full dashboard payload (fast path, news excluded) |
| GET  | `/api/signal/{ticker}` | AI action + confidence |
| GET  | `/api/price/{ticker}` | OHLCV candles |
| GET  | `/api/news/{ticker}` | Financial headlines + sentiment |
| WS   | `/ws/live/{ticker}` | Binance kline relay (crypto pairs) |

OpenAPI docs are served at `/docs`.

---

## Türkçe hızlı başlangıç

### Docker ile tek komut
```bash
cp .env.example .env
docker compose up --build
```
Ardından <http://localhost:8000>.

### Yerel geliştirme
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8000

cd frontend && npm install && npm run dev
```
<http://localhost:5173> aç.

### Model eğitimi
```bash
python scripts/train_general.py --timesteps 500000
```
Çıkışta `models/trained/model_general.zip` oluşur, backend otomatik yükler.

---

## License

MIT (planned). Trained models are released separately on Hugging Face Hub.

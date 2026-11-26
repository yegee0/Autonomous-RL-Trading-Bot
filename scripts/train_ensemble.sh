#!/usr/bin/env bash
# One command → trains all 4 heads (general, trend, range, crisis) sequentially.
#
# Typical runtime on CPU for 500k steps is ~45-70 min per head, so budget
# ~3-4 hours for the full sweep. GPU shrinks this to 20-30 min each.
#
# Use:
#   bash scripts/train_ensemble.sh
#   TIMESTEPS=1500000 bash scripts/train_ensemble.sh       # heavier
#   INTERVAL=15m PERIOD=90d bash scripts/train_ensemble.sh # different bars

set -euo pipefail
cd "$(dirname "$0")/.."

TIMESTEPS=${TIMESTEPS:-500000}
TICKERS=${TICKERS:-"BTC-USD,ETH-USD,SOL-USD,AAPL,TSLA,MSFT,NVDA,GOOGL"}
PERIOD=${PERIOD:-60d}
INTERVAL=${INTERVAL:-5m}
# Force CPU so training doesn't abort on an unsupported GPU.
export CUDA_VISIBLE_DEVICES=""

mkdir -p logs

for regime in general trend range crisis; do
    if [[ "$regime" == "general" ]]; then
        flag="--regime all --name general"
    else
        flag="--regime $regime --name $regime"
    fi
    log="logs/train_${regime}.log"
    echo "============================================"
    echo "Training '${regime}' head → $log"
    echo "  timesteps=$TIMESTEPS  interval=$INTERVAL  period=$PERIOD"
    echo "============================================"
    # shellcheck disable=SC2086
    python3 scripts/train_general.py \
        --tickers "$TICKERS" \
        --period "$PERIOD" \
        --interval "$INTERVAL" \
        --timesteps "$TIMESTEPS" \
        $flag 2>&1 | tee "$log"
    echo "[$regime] done. artifact: models/trained/model_${regime}.zip"
done

echo ""
echo "All heads trained. Ensemble picks between them automatically — restart the API."

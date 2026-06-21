#!/usr/bin/env bash
# Wait, then eval the LIVE rust net (net/model.npz on server) vs c9 — restart-proof.
cd "$(dirname "$0")/.."
SLEEP=${1:-1200}; SRV=nixos@100.106.20.11
sleep "$SLEEP"
rsync -az "$SRV":~/tempo/net/model.npz net/model_live.npz 2>/dev/null
echo "=== LIVE rust net vs c9, 40g @$(date +%H:%M) ==="
./scripts/run.sh -m tools.par_eval --deck0 data/decks/abomasnow.csv --deck1 data/decks/abomasnow.csv \
  --p0 rust --pv0 net/model_live.npz --opp0 data/decks/mega_lucario.csv --iters0 150 \
  --p1 rust --pv1 net/ckpt/model_c9.npz --opp1 data/decks/mega_lucario.csv --iters1 150 \
  --games 40 --workers 10 --label "live vs c9" 2>&1 | grep -E "win-rate|games="

#!/usr/bin/env bash
# Eval LIVE Lucario net (server net/lucario.npz) vs the frozen BC baseline (net/lucario_bc.npz).
cd "$(dirname "$0")/.."
SLEEP=${1:-1500}; SRV=nixos@100.106.20.11
sleep "$SLEEP"
rsync -az "$SRV":~/tempo/net/lucario.npz net/lucario_live.npz 2>/dev/null
echo "=== LIVE Lucario net vs BC baseline, 40g @$(date +%H:%M) ==="
./scripts/run.sh -m tools.par_eval --deck0 data/decks/lucario_praxel.csv --deck1 data/decks/lucario_praxel.csv \
  --p0 rust --pv0 net/lucario_live.npz --opp0 data/decks/lucario_praxel.csv --iters0 150 \
  --p1 rust --pv1 net/lucario_bc.npz --opp1 data/decks/lucario_praxel.csv --iters1 150 \
  --games 40 --workers 10 --label "luc-live vs luc-BC" 2>&1 | grep -E "win-rate|games="

#!/usr/bin/env bash
cd "$(dirname "$0")/.."
sleep "${1:-900}"
rsync -az nixos@100.106.20.11:~/tempo/net/lucario_s2.npz net/lucario_s2.npz 2>/dev/null
echo "=== Stage 2 @$(date +%H:%M) ==="
ssh -o ConnectTimeout=10 nixos@100.106.20.11 'tail -3 ~/tempo/az_s2_progress.log' 2>/dev/null
echo "--- frontier-agreement (BC=40.4%, drift<38%) ---"
./scripts/run.sh -m tools.frontier_agreement --pv net/lucario_s2.npz --bc data/bc_lucario/records_7962.jsonl --n 1500 2>&1 | tail -1
echo "--- strength: S2 vs BC net-vs-net (>50% = improving) ---"
./scripts/run.sh -m tools.par_eval --deck0 data/decks/lucario_praxel.csv --deck1 data/decks/lucario_praxel.csv --p0 rust --pv0 net/lucario_s2.npz --opp0 data/decks/lucario_praxel.csv --iters0 150 --p1 rust --pv1 net/lucario_best.npz --opp1 data/decks/lucario_praxel.csv --iters1 150 --games 40 --workers 10 --label "S2 vs BC" 2>&1 | grep win-rate

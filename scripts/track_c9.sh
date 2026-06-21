#!/usr/bin/env bash
cd "$(dirname "$0")/.."
TGT=${1:-13}; SRV=nixos@100.106.20.11
for i in $(seq 1 120); do
  c=$(ssh -o ConnectTimeout=10 "$SRV" 'grep -c rust-cycle ~/tempo/az_rust_progress.log 2>/dev/null' || echo 0)
  [ "${c:-0}" -ge "$TGT" ] && break
  sleep 60
done
c=${c:-0}
rsync -az "$SRV":~/tempo/net/ckpt_rust/model_r${c}.npz net/ckpt_rust/ 2>/dev/null
echo "=== rust-cycle $c: net-in-Rust(r$c) vs net-in-Rust(c9), 40g ==="
./scripts/run.sh -m tools.par_eval --deck0 data/decks/abomasnow.csv --deck1 data/decks/abomasnow.csv \
  --p0 rust --pv0 "net/ckpt_rust/model_r${c}.npz" --opp0 data/decks/mega_lucario.csv --iters0 150 \
  --p1 rust --pv1 net/ckpt/model_c9.npz --opp1 data/decks/mega_lucario.csv --iters1 150 \
  --games 40 --workers 10 --label "r$c vs c9" 2>&1 | grep -E "win-rate|games="
echo "TRACKED=$c"

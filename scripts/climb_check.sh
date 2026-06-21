#!/usr/bin/env bash
cd "$(dirname "$0")/.."
AFTER=${1:-0}; SRV=nixos@100.106.20.11
for i in $(seq 1 90); do
  c=$(ssh -o ConnectTimeout=10 "$SRV" 'grep -c "rust-cycle" ~/tempo/az_rust_progress.log 2>/dev/null' || echo "$AFTER")
  [ "${c:-0}" -gt "$AFTER" ] && break
  sleep 60
done
c=${c:-0}; [ "$c" -le "$AFTER" ] && { echo "no new rust-cycle"; echo "RCYCLE=$AFTER"; exit 0; }
rsync -az "$SRV":~/tempo/net/ckpt_rust/model_r${c}.npz net/ckpt_rust/ 2>/dev/null
echo "=== rust-cycle $c: net-in-Rust(r$c) vs Rust-vanilla @1.5s (baseline c9=83.3%) ==="
./scripts/run.sh -m tools.par_eval --deck0 data/decks/abomasnow.csv --deck1 data/decks/abomasnow.csv \
  --p0 rust --pv0 "net/ckpt_rust/model_r${c}.npz" --opp0 data/decks/mega_lucario.csv --iters0 150 \
  --p1 rust --opp1 data/decks/mega_lucario.csv --iters1 150 --games 24 --workers 8 \
  --label "net-in-Rust(r$c) vs vanilla" 2>&1 | grep -E "win-rate|games="
echo "RCYCLE=$c"

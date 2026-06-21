#!/usr/bin/env bash
# Wait for the next AZ cycle after $1, pull its checkpoint, and eval net-guided MCTS vs vanilla MCTS
# (low iters, where the learned prior matters most). Prints the win-rate + CYCLE_EVALED=N.
cd "$(dirname "$0")/.."
AFTER=${1:-0}
SRV=nixos@100.106.20.11
cyc=$AFTER
for i in $(seq 1 80); do
  cyc=$(ssh -o ConnectTimeout=10 "$SRV" 'grep -c "done;" ~/tempo/az_progress.log 2>/dev/null' || echo "$AFTER")
  [ "${cyc:-0}" -gt "$AFTER" ] && break
  sleep 90
done
if [ "${cyc:-0}" -le "$AFTER" ]; then echo "no new cycle (still $AFTER)"; echo "CYCLE_EVALED=$AFTER"; exit 0; fi
rsync -az "$SRV":~/tempo/net/ckpt/model_c${cyc}.pt net/ckpt/ 2>/dev/null
echo "=== cycle $cyc: net-MCTS vs vanilla-MCTS (20 iters, 24 games) ==="
./scripts/run.sh -m tools.par_eval --deck0 data/decks/abomasnow.csv --deck1 data/decks/abomasnow.csv \
  --p0 mcts --pv0 "net/ckpt/model_c${cyc}.pt" --opp0 data/decks/mega_lucario.csv --iters0 20 \
  --p1 mcts --opp1 data/decks/mega_lucario.csv --iters1 20 --games 24 --workers 12 \
  --label "net-c${cyc} vs vanilla" 2>&1 | grep -E "win-rate|games="
echo "CYCLE_EVALED=$cyc"

#!/usr/bin/env bash
# AlphaZero loop: self-play (MCTS w/ current net) -> train -> repeat. Each cycle the net improves
# and self-play data accumulates (rolling window). Runs for hours; checkpoints each cycle.
#   cd ~/tempo && nohup bash scripts/az_loop.sh 60 > /dev/null 2>&1 &
cd "$(dirname "$0")/.."
N="${1:-60}"
[ -f net/model.pt ] || cp net/bc_model.pt net/model.pt
mkdir -p net/ckpt
for c in $(seq 1 "$N"); do
  ts=$(date +%H:%M:%S)
  # Fast vanilla-MCTS self-play (no net per node) -> distill its visit-counts into the net.
  ./scripts/run.sh -m train.selfplay_gen --games 120 --iters 60 --workers 14 >> az_loop.log 2>&1
  tail -n 80000 data/selfplay/records.jsonl > data/selfplay/records.tmp 2>/dev/null && mv data/selfplay/records.tmp data/selfplay/records.jsonl
  ./scripts/run.sh -m train.train_net --init net/model.pt --out net/model.pt --epochs 6 >> az_loop.log 2>&1
  cp net/model.pt "net/ckpt/model_c${c}.pt"
  echo "[$ts] cycle $c done; selfplay_records=$(wc -l < data/selfplay/records.jsonl 2>/dev/null)" >> az_progress.log
done
echo "AZ LOOP DONE" >> az_progress.log

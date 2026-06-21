#!/usr/bin/env bash
# Rollout-policy A/B on the 16-core server. Does a floor-heuristic playout beat lethal+random?
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="tune2.log"
W=14
ML=data/decks/mega_lucario.csv
run() { echo -e "\n### $* ###"; ./scripts/run.sh -m tools.par_eval "$@"; }
{
echo "===== TUNE2 START ====="; date

# A — equal iters: floor-rollout vs default-rollout (quality per iteration)
run --deck0 $ML --deck1 $ML --p0 mcts --rollout0 floor --iters0 60 \
    --p1 mcts --rollout1 default --iters1 60 --opp0 $ML --opp1 $ML \
    --games 64 --workers $W --label "floor-rollout(60) vs default-rollout(60)"

# B — equal-time proxy: floor playouts are ~2x slower, so 30 vs 60 iters
run --deck0 $ML --deck1 $ML --p0 mcts --rollout0 floor --iters0 30 \
    --p1 mcts --rollout1 default --iters1 60 --opp0 $ML --opp1 $ML \
    --games 64 --workers $W --label "floor-rollout(30) vs default-rollout(60) [equal-time]"

# C — absolute: floor-rollout MCTS vs the floor pilot itself
run --deck0 $ML --deck1 $ML --p0 mcts --rollout0 floor --iters0 60 --opp0 $ML \
    --p1 floor --games 64 --workers $W --label "floor-rollout mcts(60) vs floor pilot"

echo "===== TUNE2 DONE ====="; date
} >> "$LOG" 2>&1

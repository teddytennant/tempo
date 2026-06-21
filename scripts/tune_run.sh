#!/usr/bin/env bash
# Heavy tuning batch for the 16-core server. Logs to tune.log. Launch with:
#   cd ~/tempo && nohup bash scripts/tune_run.sh > /dev/null 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="tune.log"
W=14
ML=data/decks/mega_lucario.csv
DP=data/decks/dragapult.csv

run() { echo -e "\n### $* ###"; ./scripts/run.sh -m tools.par_eval "$@"; }

{
echo "===== TUNE RUN START ====="; date

# EXP1 — does more search help? (lucario mirror)
run --deck0 $ML --deck1 $ML --p0 mcts --p1 mcts --opp0 $ML --opp1 $ML \
    --iters0 150 --iters1 25 --games 48 --workers $W --label "scaling mcts150_vs_mcts25"

# EXP2 — does opponent modeling help? dragapult vs a floor pilot playing lucario
run --deck0 $DP --deck1 $ML --p0 mcts --opp0 $ML --iters0 60 --p1 floor \
    --games 64 --workers $W --label "dragapult opp=LUCARIO vs floor-lucario"
run --deck0 $DP --deck1 $ML --p0 mcts --opp0 $DP --iters0 60 --p1 floor \
    --games 64 --workers $W --label "dragapult opp=mirror vs floor-lucario"

# EXP3 — which deck wins, mcts both sides with correct opp models
run --deck0 $ML --deck1 $DP --p0 mcts --p1 mcts --opp0 $DP --opp1 $ML \
    --iters0 60 --iters1 60 --games 48 --workers $W --label "lucario vs dragapult (mcts both)"

# EXP4 — our deploy-strength agent (lucario, opp=lucario) vs floor on lucario (sanity: search >> heuristic on same deck)
run --deck0 $ML --deck1 $ML --p0 mcts --opp0 $ML --iters0 120 --p1 floor \
    --games 64 --workers $W --label "lucario mcts120 vs lucario floor"

echo "===== TUNE RUN DONE ====="; date
} >> "$LOG" 2>&1

#!/usr/bin/env bash
# Final config question: for our Abomasnow agent vs the real Lucario field, which opponent model?
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="tune3.log"; W=14
AB=data/decks/abomasnow.csv
ML=data/decks/mega_lucario.csv
run() { echo -e "\n### $* ###"; ./scripts/run.sh -m tools.par_eval "$@"; }
{
echo "===== TUNE3 START ====="; date
# Abomasnow MCTS vs a Lucario opponent (floor pilot) — opp_model = Lucario (real) vs mirror
run --deck0 $AB --deck1 $ML --p0 mcts --opp0 $ML --iters0 60 --p1 floor \
    --games 80 --workers $W --label "ABO opp=LUCARIO vs Lucario-floor"
run --deck0 $AB --deck1 $ML --p0 mcts --opp0 $AB --iters0 60 --p1 floor \
    --games 80 --workers $W --label "ABO opp=mirror vs Lucario-floor"
# Stronger opponent: Lucario piloted by MCTS
run --deck0 $AB --deck1 $ML --p0 mcts --opp0 $ML --iters0 60 \
    --p1 mcts --opp1 $ML --iters1 60 --games 64 --workers $W --label "ABO(opp=Luc) vs Lucario-MCTS"
echo "===== TUNE3 DONE ====="; date
} >> "$LOG" 2>&1

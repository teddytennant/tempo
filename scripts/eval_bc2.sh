#!/usr/bin/env bash
# Instrumented eval of the trained BC2 hybrid: two candidate decks x {mirror, vs crustle floor}.
# Gates: error_games == 0 everywhere; winrate + anomaly profile pick the deck.
set -euo pipefail
cd /home/gradient/projects/ai/tempo
GAMES="${GAMES:-24}"
cp net/bc_top2.npz agent/model.npz
TEA=data/decks/mined/The_Debauchery_Tea_Party.csv
KAZ=data/decks/mined/kazuki0123.csv

run() { # name deck opp [opp_deck]
  local name=$1 deck=$2 opp=$3 oppdeck=${4:-}
  local extra=()
  [ -n "$oppdeck" ] && extra=(--opp_deck "$oppdeck")
  BC2_DECK="$deck" ./scripts/run.sh -m arena.anomaly_eval --me bc2 --opp "$opp" \
    --games "$GAMES" --deck "$deck" "${extra[@]}" > "eval_bc2_$name.log" 2>&1
  echo "== $name"; tail -n 4 "eval_bc2_$name.log"
}

run tea_mirror   "$TEA" bc2 &
run tea_crustle  "$TEA" floor data/decks/crustle.csv &
run kaz_mirror   "$KAZ" bc2 &
run kaz_crustle  "$KAZ" floor data/decks/crustle.csv &
wait
echo EVAL-DONE

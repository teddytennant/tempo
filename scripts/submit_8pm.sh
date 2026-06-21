#!/usr/bin/env bash
# Wait until 8pm tonight, then submit the staged Rust agent (retry if the daily reset lags).
cd "$(dirname "$0")/.."
LOG="submit_8pm.log"
KCMD="$HOME/.local/bin/kaggle"
TARGET=$(date -d 'today 20:00' +%s)
NOW=$(date +%s)
WAIT=$((TARGET - NOW))
echo "[$(date)] waiting ${WAIT}s until 8pm" >> "$LOG"
[ "$WAIT" -gt 0 ] && sleep "$WAIT"
for i in 1 2 3 4 5 6; do
  echo "[$(date)] submit attempt $i" >> "$LOG"
  out=$("$KCMD" competitions submit pokemon-tcg-ai-battle -f agent/submission_rust.tar.gz \
        -m "tempo Rust MCTS core (native 10x sims, Abomasnow, opp=Lucario)" 2>&1)
  echo "$out" >> "$LOG"
  echo "$out" | grep -qi "Successfully submitted" && { echo "[$(date)] DONE" >> "$LOG"; break; }
  sleep 300
done

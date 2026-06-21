#!/usr/bin/env bash
# Slowly accumulate new real ladder replays (the feed adds games as the ladder plays 24/7).
cd "$(dirname "$0")/.."
KCMD="$HOME/.local/bin/kaggle"
SUBS="53915967 53915585 53915143 53908104 53903200"
cd data/episodes
for cycle in $(seq 1 40); do
  for s in $SUBS; do
    for id in $($KCMD competitions episodes "$s" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+$'); do
      [ -f "episode-$id-replay.json" ] || $KCMD competitions replay "$id" >/dev/null 2>&1
    done
  done
  echo "cycle $cycle: $(ls *replay*.json 2>/dev/null | wc -l) replays @ $(date)" >> ../../harvest_loop.log
  sleep 420
done

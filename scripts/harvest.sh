#!/usr/bin/env bash
# Harvest real ladder replays across the field and report the metagame. Needs kaggle creds.
#   nohup bash scripts/harvest.sh > harvest.log 2>&1 &
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KCMD="$HOME/.local/bin/kaggle"
N="${1:-40}"
# Source episode IDs from several submissions (ours + the team's higher-rated ones -> stronger games)
SUBS="53915585 53915967 53915143 53903200 53908104"

echo "collecting episode ids..."
ids=$(for s in $SUBS; do $KCMD competitions episodes "$s" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+$'; done | sort -u | head -"$N")
echo "downloading $(echo "$ids" | wc -l) replays..."
cd "$ROOT/data/episodes"
for id in $ids; do
  [ -f "episode-$id-replay.json" ] || $KCMD competitions replay "$id" >/dev/null 2>&1
done
cd "$ROOT"
echo "=== METAGAME ==="
python3 tools/meta_from_replays.py
echo "HARVEST DONE"

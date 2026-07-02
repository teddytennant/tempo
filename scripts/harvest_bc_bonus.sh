#!/usr/bin/env bash
# Download + extract the two bonus days (06-20, 06-21). Waits for the main harvest's downloads
# to finish first so the two don't fight over bandwidth.
set -u
cd /home/gradient/projects/ai/tempo
LB=$(ls data/lb_now/pokemon-tcg-ai-battle-publicleaderboard-*.csv | sort | tail -1)  # augmented teacher set
# wait until the main harvest has all 9 zips (or gave up), max 30 min
for i in $(seq 180); do
  n=$(ls data/episodes_daily/zips/*/done 2>/dev/null | wc -l)
  [ "$n" -ge 9 ] && break
  sleep 10
done
for d in 2026-06-20 2026-06-21; do
  tag=${d:5:2}${d:8:2}
  out="data/bc_top/records_$tag.jsonl"
  [ -e "$out" ] && continue
  z="data/episodes_daily/zips/$tag"; mkdir -p "$z"
  echo "$(date -u +%H:%M:%S) downloading $d"
  kaggle datasets download "kaggle/pokemon-tcg-ai-battle-episodes-$d" -p "$z" || { echo "DL FAIL $d"; continue; }
  raw="data/episodes_daily/raw_$tag"; mkdir -p "$raw"
  echo "$(date -u +%H:%M:%S) unzip $tag"
  unzip -o -q "$z"/*.zip -d "$raw" || { echo "UNZIP FAIL $tag"; rm -rf "$raw"; continue; }
  echo "$(date -u +%H:%M:%S) extract $tag"
  python3 tools/extract_bc_top.py --episodes "$raw/**/*.json" \
    --leaderboard "$LB" --min-score 1050 --out "$out.tmp" > "data/bc_top/extract_$tag.log" 2>&1 \
    && mv "$out.tmp" "$out" || echo "EXTRACT FAIL $tag"
  rm -rf "$raw" "$z"
  echo "$(date -u +%H:%M:%S) done $tag: $(wc -l < "$out" 2>/dev/null || echo 0)"
done
echo BONUS DONE

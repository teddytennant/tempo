#!/usr/bin/env bash
# Harvest a multi-day top-player BC corpus: download each daily episode dataset,
# extract teacher decisions (min-score 1050 vs fresh leaderboard), delete raw JSON.
set -u
cd /home/gradient/projects/ai/tempo
LB=$(ls data/lb_now/pokemon-tcg-ai-battle-publicleaderboard-*.csv | sort | tail -1)  # augmented teacher set
DAYS="2026-06-23 2026-06-24 2026-06-25 2026-06-26 2026-06-27 2026-06-28 2026-06-29 2026-06-30 2026-07-01"
mkdir -p data/bc_top data/episodes_daily/zips

# ---- download all zips sequentially (kaggle CLI is flaky under parallelism) ----
for d in $DAYS; do
  tag=${d:5:2}${d:8:2}
  z="data/episodes_daily/zips/$tag"
  if [ -e "data/bc_top/records_$tag.jsonl" ]; then echo "SKIP $d (records exist)"; continue; fi
  if [ -e "$z/done" ]; then echo "SKIP download $d"; continue; fi
  mkdir -p "$z"
  echo "$(date -u +%H:%M:%S) downloading $d ..."
  for try in 1 2 3; do
    kaggle datasets download "kaggle/pokemon-tcg-ai-battle-episodes-$d" -p "$z" && { touch "$z/done"; break; }
    echo "retry $try for $d"; sleep 10
  done
done

extract_day() {
  d=$1; tag=${d:5:2}${d:8:2}
  out="data/bc_top/records_$tag.jsonl"
  [ -e "$out" ] && return 0
  z="data/episodes_daily/zips/$tag"
  raw="data/episodes_daily/raw_$tag"
  mkdir -p "$raw"
  echo "$(date -u +%H:%M:%S) unzip $d"
  unzip -o -q "$z"/*.zip -d "$raw" || { echo "UNZIP FAIL $d"; return 1; }
  echo "$(date -u +%H:%M:%S) extract $d"
  python3 tools/extract_bc_top.py --episodes "$raw/**/*.json" \
    --leaderboard "$LB" --min-score 1050 --out "$out.tmp" > "data/bc_top/extract_$tag.log" 2>&1 \
    && mv "$out.tmp" "$out" || echo "EXTRACT FAIL $d"
  rm -rf "$raw" "$z"
  echo "$(date -u +%H:%M:%S) done $d: $(wc -l < "$out" 2>/dev/null || echo 0) records"
}

# ---- re-extract 06-22 from the already-unzipped dir with the new teacher set ----
if [ -d data/episodes_daily/ep2206 ] && [ ! -e data/bc_top/records_0622.jsonl ]; then
  ( python3 tools/extract_bc_top.py --episodes 'data/episodes_daily/ep2206/*.json' \
      --leaderboard "$LB" --min-score 1050 --out data/bc_top/records_0622.jsonl.tmp \
      > data/bc_top/extract_0622.log 2>&1 \
    && mv data/bc_top/records_0622.jsonl.tmp data/bc_top/records_0622.jsonl \
    && rm -rf data/episodes_daily/ep2206
    echo "$(date -u +%H:%M:%S) done 06-22 re-extract" ) &
fi

# ---- extract days, 3 at a time (peak ~3x21G raw on disk) ----
i=0
for d in $DAYS; do
  extract_day "$d" &
  i=$((i+1))
  [ $((i % 3)) -eq 0 ] && wait
done
wait
echo "$(date -u +%H:%M:%S) HARVEST COMPLETE"
wc -l data/bc_top/records_*.jsonl

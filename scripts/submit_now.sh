#!/usr/bin/env bash
# Idempotent submit of the best two agents (Iono + Crustle). Safe to run multiple times / from
# multiple triggers (crontab + harness cron + manual) — it skips any already submitted today.
cd "$(dirname "$0")/.." || exit 1
KCMD="$HOME/.local/bin/kaggle"
today=$(date -u +%Y-%m-%d)
recent=$("$KCMD" competitions submissions pokemon-tcg-ai-battle 2>/dev/null)
log() { echo "$(date '+%F %T') $*" >> submit_now.log; }
for deck in iono crustle; do
  if echo "$recent" | grep -q "submission_${deck}.tar.gz.*${today}"; then
    log "skip ${deck}: already submitted today"; continue
  fi
  for i in 1 2 3; do
    out=$("$KCMD" competitions submit pokemon-tcg-ai-battle -f "agent/submission_${deck}.tar.gz" \
      -m "tempo: ${deck} specialist (validated best vs 7-bot pool: Iono 67% / Crustle 58%, complementary)" 2>&1)
    log "${deck} attempt ${i}: ${out}"
    echo "$out" | grep -qi "Successfully submitted" && break
    sleep 90
  done
  sleep 20
  recent=$("$KCMD" competitions submissions pokemon-tcg-ai-battle 2>/dev/null)
done
log "submit_now done"

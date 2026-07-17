#!/usr/bin/env bash
# ARMED submitter for starmie v11: sleeps until 00:00:30 UTC (daily 5-submission window reset),
# then submits the already-built + packed-smoke-verified tarball. Built/validated beforehand via
#   bash scripts/ship_starmie_v11.sh "<msg>" --dry-run
# Launch:  nohup bash scripts/arm_starmie_v11.sh > arm_starmie_v11.log 2>&1 &
set -uo pipefail
cd /home/gradient/projects/ai/tempo
TARBALL=agent/submission_starmie_v11.tar.gz
MSG="tempo starmie v11: ladder-loss fix from real ep 86501434 (Dragapult ex) — front Froslass/Refrain into their 5-9 card hand (OHKOs 320HP Dragapult), Gravity Mountain to 290; all _VS_DRAG-gated. Paired bot:dragapult 30->40% (N=160 cand / 40 base); gates green: crustle 75, grimm 60, mirror 40, 0 errors"

[ -f "$TARBALL" ] || { echo "FATAL: $TARBALL missing"; exit 1; }

now=$(date -u +%s)
# next 00:00:30 UTC strictly after now
midnight=$(date -u -d "tomorrow 00:00:30" +%s)
today_mid=$(date -u -d "today 00:00:30" +%s)
if [ "$today_mid" -gt "$now" ]; then midnight=$today_mid; fi
wait_s=$((midnight - now))
echo "$(date -u): armed; sleeping ${wait_s}s until 00:00:30 UTC"
sleep "$wait_s"

echo "$(date -u): submitting $TARBALL"
for attempt in 1 2 3; do
  if kaggle competitions submit -c pokemon-tcg-ai-battle -f "$TARBALL" -m "$MSG"; then
    echo "$(date -u): SUBMITTED (attempt $attempt)"
    break
  fi
  echo "$(date -u): submit attempt $attempt failed; retrying in 60s"
  sleep 60
done
kaggle competitions submissions -c pokemon-tcg-ai-battle 2>/dev/null | head -4

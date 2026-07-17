#!/usr/bin/env bash
# Arm the floor submission: sleep until just past the 00:00 UTC daily reset, then submit.
# The tarball + message are read AT SUBMIT TIME from $TARGET_FILE (two lines: path, message),
# so the payload can be upgraded after arming without re-arming.
#   nohup bash scripts/arm_floor.sh <target_file> >> ship_floor.log 2>&1 &
set -uo pipefail
cd /home/gradient/projects/ai/tempo
TARGET_FILE="${1:?usage: arm_floor.sh <target_file>}"

now=$(date -u +%s)
# next 00:00:30 UTC strictly in the future
midnight=$(date -u -d "tomorrow 00:00:30" +%s)
today_mid=$(date -u -d "today 00:00:30" +%s)
if [ "$today_mid" -gt "$now" ]; then midnight="$today_mid"; fi
wait_s=$((midnight - now))
echo "[arm_floor] $(date -u) armed; sleeping ${wait_s}s until $(date -u -d @$midnight)"
sleep "$wait_s"

TARBALL=$(sed -n 1p "$TARGET_FILE")
MSG=$(sed -n 2p "$TARGET_FILE")
if [ ! -f "$TARBALL" ]; then
  echo "[arm_floor] FATAL: tarball missing: $TARBALL"; exit 1
fi
echo "[arm_floor] $(date -u) submitting $TARBALL"
echo "[arm_floor] message: $MSG"

exec 200>/tmp/tempo_ship.lock
flock -x 200
# Max 2 attempts: the second only guards against the daily reset landing a few
# seconds late (a boundary limit-error), NOT a retry-loop. If both fail, stop.
for attempt in 1 2; do
  if kaggle competitions submit -c pokemon-tcg-ai-battle -f "$TARBALL" -m "$MSG"; then
    echo "[arm_floor] $(date -u) SUBMITTED (attempt $attempt)"
    sleep 30
    kaggle competitions submissions -c pokemon-tcg-ai-battle -v 2>/dev/null | head -4
    exit 0
  fi
  echo "[arm_floor] $(date -u) submit attempt $attempt failed"
  [ "$attempt" = 1 ] && { echo "[arm_floor] reset may be a few s late; one more attempt in 75s"; sleep 75; }
done
echo "[arm_floor] $(date -u) BOTH ATTEMPTS FAILED — diagnose manually, do NOT auto-resubmit"
exit 1

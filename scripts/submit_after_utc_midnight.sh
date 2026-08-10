#!/usr/bin/env bash
# Deferred second submission across the UTC cap reset.
#
# The daily cap (5) was already spent when this run started, and the cap resets at UTC midnight
# (RESEARCH.md, "Daily cap resets at UTC midnight"). This waits for the reset, submits the prepared
# artifact ONCE, and verifies it registered — the Kaggle API can return a 400 after a successful
# upload, so the submissions list is the only trustworthy confirmation, and a blind retry would
# burn a slot on something that already landed.
#
#   nohup setsid bash scripts/submit_after_utc_midnight.sh <tarball> <message-file> > log 2>&1 &
set -uo pipefail
ART="$(realpath "$1")"
MSGFILE="$(realpath "$2")"
BASE="$(basename "$ART")"
COMP=pokemon-tcg-ai-battle
KAGGLE=/home/nixos/.local/bin/kaggle

landed() { "$KAGGLE" competitions submissions -c "$COMP" 2>/dev/null | head -6 | grep -q "$BASE"; }

echo "[$(date -u)] deferred submit armed: $ART"
[ -f "$ART" ] || { echo "MISSING ARTIFACT"; exit 1; }

# Wait for the UTC day to roll over, then give the reset two minutes of slack.
TODAY="$(date -u +%Y-%m-%d)"
while [ "$(date -u +%Y-%m-%d)" = "$TODAY" ]; do
  sleep 60
done
sleep 120
echo "[$(date -u)] UTC day rolled over; submitting"

if landed; then
  echo "[$(date -u)] $BASE is already in the recent submissions list — not submitting again"
  exit 0
fi

"$KAGGLE" competitions submit -c "$COMP" -f "$ART" -m "$(cat "$MSGFILE")" 2>&1 | tail -3

sleep 45
if landed; then
  echo "[$(date -u)] VERIFIED: $BASE registered"
else
  echo "[$(date -u)] NOT registered after upload — retrying once"
  "$KAGGLE" competitions submit -c "$COMP" -f "$ART" -m "$(cat "$MSGFILE")" 2>&1 | tail -3
  sleep 45
  landed && echo "[$(date -u)] VERIFIED on retry" || echo "[$(date -u)] STILL NOT REGISTERED — needs a human"
fi

echo "[$(date -u)] final state:"
"$KAGGLE" competitions submissions -c "$COMP" 2>&1 | head -5

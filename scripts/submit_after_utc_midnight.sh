#!/usr/bin/env bash
# Deferred second submission.
#
# The daily cap (5) was already spent when this run started, and the cap resets at UTC midnight
# (RESEARCH.md, "Daily cap resets at UTC midnight"). This waits for the reset, submits the
# prepared artifact once, and verifies it registered — the Kaggle API can 400 after a successful
# upload, so the submissions list is the only trustworthy confirmation.
#
#   nohup setsid bash scripts/submit_after_utc_midnight.sh <tarball> <message-file> > log 2>&1 &
set -uo pipefail
ART="$(realpath "$1")"
MSGFILE="$(realpath "$2")"
COMP=pokemon-tcg-ai-battle
KAGGLE=/home/nixos/.local/bin/kaggle

echo "[$(date -u)] deferred submit armed for $ART"

# Wait for the UTC day to roll over, then give the reset two minutes of slack.
TODAY="$(date -u +%Y-%m-%d)"
while [ "$(date -u +%Y-%m-%d)" = "$TODAY" ]; do
  sleep 60
done
sleep 120
echo "[$(date -u)] UTC day rolled over; submitting"

MSG="$(cat "$MSGFILE")"
"$KAGGLE" competitions submit -c "$COMP" -f "$ART" -m "$MSG" 2>&1 | tail -3

sleep 30
echo "[$(date -u)] verifying:"
"$KAGGLE" competitions submissions -c "$COMP" -v 2>&1 | head -4
echo "[$(date -u)] done"

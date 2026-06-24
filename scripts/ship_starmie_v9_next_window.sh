#!/usr/bin/env bash
# Ship the notebook-informed Starmie v9 at the next Kaggle daily-budget reset (00:00 UTC).
# v9 = prize-corrected lethal verifier + correct Starmie deck (footgun fixed), built 2026-06-24.
# This A/B-probes the improved Starmie on the ladder while our proven Crustle floor (submitted
# 2026-06-24 15:06, scored ~863 historically) stays as the second active submission. Only the
# latest 2 submissions are scored, so after this fires the active pair is {crustle, starmie_v9}
# and our score = max of the two (crustle protects us if v9 under-performs).
set -u
REPO=/home/gradient/projects/ai/tempo
KCMD="$HOME/.local/bin/kaggle"
TARBALL="$REPO/agent/submission_starmie_v9.tar.gz"
LOG="$REPO/ship_v9.log"
TARGET=20260625   # UTC date == next 00:00 UTC reset (8pm ET 2026-06-24)

cd "$REPO" || exit 1
[ -f "$TARBALL" ] || { echo "$(date '+%F %T %Z') MISSING $TARBALL" >> "$LOG"; exit 1; }
echo "$(date '+%F %T %Z') watcher started; waiting for 00:00 UTC ($TARGET)..." >> "$LOG"
while [ "$(date -u +%Y%m%d)" -lt "$TARGET" ]; do sleep 30; done
sleep 20   # buffer so the reset has applied
echo "$(date '+%F %T %Z') reset reached; submitting Starmie v9..." >> "$LOG"
for i in 1 2 3; do
  out=$("$KCMD" competitions submit pokemon-tcg-ai-battle -f "$TARBALL" \
    -m "tempo: Starmie v9 — prize-corrected lethal verifier (non-overlapping deck/prize determinization, never plans on a prized card) + deck footgun fixed. Notebook-informed (top-3 '1250+ Starmie' design). A/B probe vs Crustle floor." 2>&1)
  echo "$(date '+%F %T %Z') attempt $i: $out" >> "$LOG"
  echo "$out" | grep -qi "Successfully submitted" && { echo "$(date '+%F %T %Z') SUCCESS" >> "$LOG"; exit 0; }
  sleep 60
done
echo "$(date '+%F %T %Z') gave up after 3 attempts" >> "$LOG"
exit 1

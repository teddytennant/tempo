#!/usr/bin/env bash
# Ship the BC-from-top-players agent at the next Kaggle reset (00:00 UTC) as a ladder A/B probe.
# Net = policy distilled from the 32 top leaderboard teams' winning moves (held-out top-1 ~56% vs
# 27% random); deck = Hop's Snorlax (the #2 team "The Debauchery Tea Party", our biggest teacher at
# 150 games). Submitting this alone makes the scored latest-2 = {crustle (today, ~869 floor),
# BC+hops (probe)} — crustle protects our score while we get the first real ladder read on whether
# imitating the best players beats our hand-written pilots.
set -u
REPO=/home/gradient/projects/ai/tempo
KCMD="$HOME/.local/bin/kaggle"
TARBALL="$REPO/agent/submission_bc_hops.tar.gz"
LOG="$REPO/ship_bc.log"
TARGET=20260625

cd "$REPO" || exit 1
[ -f "$TARBALL" ] || { echo "$(date '+%F %T %Z') MISSING $TARBALL" >> "$LOG"; exit 1; }
echo "$(date '+%F %T %Z') BC watcher started; waiting for 00:00 UTC ($TARGET)..." >> "$LOG"
while [ "$(date -u +%Y%m%d)" -lt "$TARGET" ]; do sleep 30; done
sleep 20
echo "$(date '+%F %T %Z') reset reached; submitting BC+hops probe..." >> "$LOG"
for i in 1 2 3; do
  out=$("$KCMD" competitions submit pokemon-tcg-ai-battle -f "$TARBALL" \
    -m "tempo: BC-from-top-players — policy cloned from the 32 top teams' winning moves (held-out 56% move-match vs 27% rand), piloting the #2 team's Hop's Snorlax deck. A/B probe vs Crustle floor." 2>&1)
  echo "$(date '+%F %T %Z') attempt $i: $out" >> "$LOG"
  echo "$out" | grep -qi "Successfully submitted" && { echo "$(date '+%F %T %Z') SUCCESS" >> "$LOG"; exit 0; }
  sleep 60
done
echo "$(date '+%F %T %Z') gave up after 3 attempts" >> "$LOG"
exit 1

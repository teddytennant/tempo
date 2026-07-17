#!/usr/bin/env bash
# Build + packed-smoke + submit the Alakazam "Powerful Hand" rules agent (dunsparce list,
# elite-calibrated pilot). Whole sequence serialized against sibling ships via /tmp/tempo_ship.lock.
#   bash scripts/ship_alakazam.sh "submission message" [--dry-run]
set -euo pipefail
cd /home/gradient/projects/ai/tempo
MSG="${1:?usage: ship_alakazam.sh <message> [--dry-run]}"
DRY="${2:-}"
DECK=data/decks/dunsparce.csv
OUT="/home/gradient/projects/ai/tempo/agent/submission_alakazam.tar.gz"

exec 200>/tmp/tempo_ship.lock
flock -x 200

# deck.csv must be the dunsparce Alakazam list or the specialist (incl. its pre-deal go-first
# gate, which reads the packed deck.csv) never fires.
cp "$DECK" agent/deck.csv
EXPECT_DECK="$DECK" CG_LIB_PATH="$(pwd)/cg" bash agent/build_submission.sh
mv agent/submission.tar.gz "$OUT"

# Packed smoke: untar to a temp dir and run a FULL kaggle_environments cabt mirror episode on the
# extracted main.py — the exact harness Kaggle validation uses (agents loaded via exec: catches
# __file__-undefined and every other loader-context bug module-import smokes cannot see).
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -xzf "$OUT" -C "$TMP"
SMOKE_DIR="$TMP" ./scripts/run.sh - <<'EOF'
import os
d = os.environ["SMOKE_DIR"]
import kaggle_environments as k
env = k.make("cabt", configuration={"runTimeout": 600}, debug=True)
steps = env.run([os.path.join(d, "main.py"), os.path.join(d, "main.py")])
last = steps[-1]
statuses = [a.status for a in last]
rewards = [a.reward for a in last]
print(f"episode steps={len(steps)} statuses={statuses} rewards={rewards}")
assert all(s == "DONE" for s in statuses), f"validation-style episode failed: {statuses}"
assert all(r is not None for r in rewards), f"agent errored (reward None): {rewards}"
print("PACKED SMOKE OK: full cabt mirror episode completed with both agents DONE")
EOF

echo "packed smoke passed for $OUT"
if [ "$DRY" = "--dry-run" ]; then
  echo "DRY RUN — not submitting."
  exit 0
fi
kaggle competitions submit -c pokemon-tcg-ai-battle -f "$OUT" -m "$MSG"
echo "SUBMITTED: $MSG"

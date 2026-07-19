#!/usr/bin/env bash
# Build + packed-smoke + (optionally) submit the Crustle wall v9 (Mist-blanks-Powerful-Hand fix
# on the PROVEN base).
#
# RE-SHIP > REBUILD: v9 is NOT built from the live agent/ tree. It is the proven
# agent/submission_crustle.tar.gz (old 366-line-rules artifact; hit 863 once, converges 775-795)
# repacked with ONLY crustle_rules.py swapped for the v9 fix set (= v8's three fixes + the
# Mist-first counter-effect rule) — every other byte identical to the proven artifact.
#
#   bash scripts/ship_crustle_v9.sh "submission message" [--dry-run]
set -euo pipefail
cd /home/gradient/projects/ai/tempo
MSG="${1:?usage: ship_crustle_v9.sh <message> [--dry-run]}"
DRY="${2:-}"
BASE_TAR=agent/submission_crustle.tar.gz
RULES=agent/crustle_rules.py
OUT="/home/gradient/projects/ai/tempo/agent/submission_crustle_v9.tar.gz"

# Serialize the whole ship sequence against sibling sessions.
exec 200>/tmp/tempo_ship.lock
flock -x 200

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
PK="$WORK/pack"; mkdir -p "$PK"
tar -xzf "$BASE_TAR" -C "$PK"
# The proven tarball must really be the old 366-line-rules artifact (sanity: crustle deck inside).
# grep -c (not -q) so pipefail does not eat tar's SIGPIPE.
if [ "$(grep -cx 344 "$PK/deck.csv")" -eq 0 ]; then
  echo "ERROR: $BASE_TAR does not contain the Crustle deck" >&2; exit 3
fi
cp "$RULES" "$PK/crustle_rules.py"
( cd "$PK" && tar -czf "$OUT" . )
echo "packed $OUT (proven base + v9 crustle_rules.py)"

# Packed smoke: untar to a temp dir and run a FULL kaggle_environments cabt mirror episode on the
# extracted main.py — the exact harness Kaggle validation uses (agents loaded via exec: catches
# __file__-undefined and every other loader-context bug module-import smokes cannot see).
SMK="$WORK/smoke"; mkdir -p "$SMK"
tar -xzf "$OUT" -C "$SMK"
SMOKE_DIR="$SMK" ./scripts/run.sh - <<'EOF'
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

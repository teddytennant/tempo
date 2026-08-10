#!/usr/bin/env bash
# Pack a foreign/forked agent tree (main.py + deck.csv [+ group.txt]) into a Kaggle submission
# tarball whose ROOT holds main.py, deck.csv and the cg/ engine, then run the exact validation
# harness Kaggle uses (a full kaggle_environments "cabt" mirror episode, agents loaded by path).
#
#   bash tools/pack_fork.sh experiments/fork_alakazam experiments/alakazam_fork.tar.gz
set -euo pipefail
SRC="$(cd "$1" && pwd)"; OUT="$2"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$(realpath -m "$OUT")"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp "$SRC/main.py" "$TMP/main.py"
cp "$SRC/deck.csv" "$TMP/deck.csv"
[ -f "$SRC/group.txt" ] && cp "$SRC/group.txt" "$TMP/group.txt"
cp -r "$ROOT/cg" "$TMP/cg"
rm -rf "$TMP/cg/__pycache__"
python3 -c "
import sys
deck=[int(x) for x in open('$TMP/deck.csv').read().split() if x.strip()]
assert len(deck)==60, f'deck.csv has {len(deck)} cards, expected 60'
compile(open('$TMP/main.py').read(),'main.py','exec')
print(f'  deck 60 cards ({len(set(deck))} unique); main.py compiles')
"
( cd "$TMP" && tar -czf "$OUT" . )
echo "built $OUT"
tar -tzf "$OUT" | head -20

# The packed smoke: a real cabt episode on the EXTRACTED tarball, both seats. This is the harness
# Kaggle validation uses, and it loads main.py via exec — it catches loader-context bugs
# (undefined __file__, cwd-relative deck.csv) that a plain module import cannot see.
#
# Kaggle's loader execs main.py with globals() == {}, so `__file__` is UNDEFINED and cwd is not the
# archive directory: the only path an agent can rely on to find its own deck.csv is
# /kaggle_simulations/agent/. We therefore extract THERE, exactly as the ladder does — extracting
# to a mktemp dir instead makes deck-resolution-by-absolute-path silently fail and reports a
# perfectly good agent as INVALID.
SMOKE=/kaggle_simulations/agent
rm -rf "$SMOKE"; mkdir -p "$SMOKE"
tar -xzf "$OUT" -C "$SMOKE"
SMOKE_DIR="$SMOKE" ./scripts/run.sh - <<'EOF'
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

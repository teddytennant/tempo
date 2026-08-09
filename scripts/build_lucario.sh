#!/usr/bin/env bash
# Build the Mega Lucario ex / Hariyama specialist from a clean git tree, with a selectable decklist.
#
# Why parameterised: the pilot (agent/lucario_rules.py) is archetype-specific but not list-specific,
# so the 60-card list is a free variable we can A/B. The current #1 team (Majkel1337, 1218.7) plays
# a list that shares 50/60 cards with ours — the 10-card delta is exactly what this compares.
#
#   bash scripts/build_lucario.sh <deck.csv> <outfile> [commit]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DECK="${1:?usage: build_lucario.sh <deck.csv> <outfile> [commit]}"
OUT="${2:?usage: build_lucario.sh <deck.csv> <outfile> [commit]}"
case "$OUT" in /*) ;; *) OUT="$ROOT/$OUT" ;; esac   # packing runs from a temp cwd — OUT must be absolute
COMMIT="${3:-HEAD}"

[ -d "$ROOT/cg" ] || { echo "ERROR: cg/ engine missing" >&2; exit 1; }
[ -f "$DECK" ] || { echo "ERROR: no such deck $DECK" >&2; exit 1; }

SRCDIR="${OUT%.tar.gz}_src"
rm -rf "$SRCDIR"; mkdir -p "$SRCDIR"
git archive "$COMMIT" agent search | tar -x -C "$SRCDIR"
cp "$DECK" "$SRCDIR/agent/deck.csv"

# The Lucario pilot only engages when it can see its own signature line in the shipped list.
for id in 673 674 675 676 677 678; do
  grep -qx "$id" "$SRCDIR/agent/deck.csv" || { echo "ERROR: deck lacks Lucario signature card $id" >&2; exit 3; }
done
[ "$(grep -cx 678 "$SRCDIR/agent/deck.csv")" -ge 3 ] || { echo "ERROR: <3 Mega Lucario ex" >&2; exit 3; }
[ "$(wc -l < "$SRCDIR/agent/deck.csv")" -eq 60 ] || { echo "ERROR: deck is not 60 cards" >&2; exit 3; }

mkdir -p "$ROOT/engine_rs/target/wheels"
WHL=$(ls "$ROOT"/engine_rs-0.1.0-*manylinux2014*.whl 2>/dev/null | head -1)
[ -n "$WHL" ] && cp -n "$WHL" "$ROOT/engine_rs/target/wheels/" 2>/dev/null || true
ln -sfn "$ROOT/engine_rs" "$SRCDIR/engine_rs"

EXPECT_DECK=none CG_LIB_PATH="$ROOT/cg" bash "$SRCDIR/agent/build_submission.sh" >/dev/null

PK=$(mktemp -d "$ROOT/experiments/.pack.XXXXXX")
tar -xzf "$SRCDIR/agent/submission.tar.gz" -C "$PK"
find "$PK" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
( cd "$PK" && tar -czf "$OUT" . )
rm -rf "$PK"

echo "built $OUT  (src tree kept at $SRCDIR for local eval)"
echo "  deck: $(tar -xzOf "$OUT" ./deck.csv | wc -l) cards, Mega Lucario x$(tar -xzOf "$OUT" ./deck.csv | grep -cx 678)"

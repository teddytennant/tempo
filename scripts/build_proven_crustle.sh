#!/usr/bin/env bash
# Deterministically rebuild the PROVEN Crustle wall submission from git alone.
#
# Why this exists: the original artifact (agent/submission_crustle.tar.gz) was the single
# best-scoring thing we own — 775.6 / 776.9 / 791.3 / 795.3 over four re-ships, 863 once — and it
# was LOST when the workspace moved, because *.tar.gz is gitignored. Everything needed to
# reproduce it IS in git, so this script is the durable replacement for the binary.
#
# Recipe (established 2026-08-09, see RESEARCH.md):
#   tree @da08caf (the 2026-06-22 20:00 build that shipped as ref 53960682 and was re-shipped
#   unmodified as 54015053 / 54041091 / 54181814 / 54794471)
#   + agent/deck.csv := data/decks/crustle.csv   (the ship scripts overwrite deck.csv; the
#     deck.csv committed in agent/ at that commit is a leftover from another archetype)
#   + the era's own agent/build_submission.sh
#   + the manylinux2014 engine_rs wheel
#
#   bash scripts/build_proven_crustle.sh [outfile]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${1:-$ROOT/experiments/submission_crustle_proven.tar.gz}"
PROVEN_COMMIT=da08caf

command -v git >/dev/null || { echo "git required" >&2; exit 1; }
[ -d "$ROOT/cg" ] || { echo "ERROR: cg/ engine missing (downloaded from Kaggle, never committed)" >&2; exit 1; }

SRC=$(mktemp -d "$ROOT/experiments/.proven.XXXXXX"); trap 'rm -rf "$SRC"' EXIT
git archive "$PROVEN_COMMIT" agent search | tar -x -C "$SRC"
cp "$ROOT/data/decks/crustle.csv" "$SRC/agent/deck.csv"

# The era build script reads the wheel from engine_rs/target/wheels/.
mkdir -p "$ROOT/engine_rs/target/wheels"
WHL=$(ls "$ROOT"/engine_rs-0.1.0-*manylinux2014*.whl 2>/dev/null | head -1)
[ -n "$WHL" ] && cp -n "$WHL" "$ROOT/engine_rs/target/wheels/" 2>/dev/null || true
ln -sfn "$ROOT/engine_rs" "$SRC/engine_rs"

# Sanity BEFORE building: the Crustle list (4x card 344) and the 366-line proven rules.
[ "$(grep -cx 344 "$SRC/agent/deck.csv")" -eq 4 ] || { echo "ERROR: deck.csv is not the Crustle list" >&2; exit 3; }
[ "$(wc -l < "$SRC/agent/crustle_rules.py")" -eq 366 ] || { echo "ERROR: crustle_rules.py is not the proven 366-line version" >&2; exit 3; }

CG_LIB_PATH="$ROOT/cg" bash "$SRC/agent/build_submission.sh" >/dev/null

# Repack without __pycache__ (keeps the artifact byte-stable and matches the original ~1.5MB).
PK=$(mktemp -d "$ROOT/experiments/.pack.XXXXXX")
tar -xzf "$SRC/agent/submission.tar.gz" -C "$PK"
find "$PK" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
( cd "$PK" && tar -czf "$OUT" . )
rm -rf "$PK"

echo "built $OUT"
echo "  crustle_rules.py: $(tar -xzOf "$OUT" ./crustle_rules.py | wc -l) lines"
echo "  deck.csv: $(tar -xzOf "$OUT" ./deck.csv | wc -l) cards, 344 x$(tar -xzOf "$OUT" ./deck.csv | grep -cx 344)"

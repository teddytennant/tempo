#!/usr/bin/env bash
# Pack the hybrid BC agent (main_bc2.py + top-player net + lethal verifier stack + a deck + cg
# engine) into a submission tarball.
#   DECK=/path/to/deck.csv NPZ=/path/to/net.npz CG_LIB_PATH=/path/to/cg bash build_bc2.sh out.tar.gz
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SRC/.." && pwd)"
OUT="${1:-$SRC/submission_bc2.tar.gz}"
DECK="${DECK:-$REPO/data/decks/hops_snorlax.csv}"
NPZ="${NPZ:-$REPO/net/bc_top2.npz}"
CG_LIB_PATH="${CG_LIB_PATH:-$REPO/cg}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

cp "$SRC/main_bc2.py" "$TMP/main.py"
cp "$SRC/lethal.py" "$SRC/belief.py" "$SRC/prize_tracker.py" "$TMP/"
cp "$DECK" "$TMP/deck.csv"
[ "$(wc -l < "$TMP/deck.csv")" -eq 60 ] || { echo "ERROR: deck.csv is not 60 cards" >&2; exit 2; }
mkdir -p "$TMP/net"
cp "$REPO/net/__init__.py" "$REPO/net/features.py" "$REPO/net/infer_np.py" "$TMP/net/"
cp "$NPZ" "$TMP/model.npz"
cp -r "$CG_LIB_PATH" "$TMP/cg"
( cd "$TMP" && tar -czf "$OUT" . )
echo "Done: $OUT (deck=$(basename "$DECK"), net=$(basename "$NPZ"))"
tar -tzf "$OUT" | head -25

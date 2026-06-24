#!/usr/bin/env bash
# Pack the standalone BC agent (main_bc.py + top-player net + a deck + cg engine) into a submission.
#   CG_LIB_PATH=/path/to/cg DECK=/path/to/deck.csv NPZ=/path/to/net.npz bash build_bc.sh out.tar.gz
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SRC/.." && pwd)"
OUT="${1:-$SRC/submission_bc.tar.gz}"
DECK="${DECK:-$REPO/data/decks/hops_snorlax.csv}"
NPZ="${NPZ:-$REPO/net/bc_top.npz}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

cp "$SRC/main_bc.py" "$TMP/main.py"
cp "$DECK" "$TMP/deck.csv"
[ "$(wc -l < "$TMP/deck.csv")" -eq 60 ] || { echo "ERROR: deck.csv is not 60 cards" >&2; exit 2; }
mkdir -p "$TMP/net"
cp "$REPO/net/__init__.py" "$REPO/net/features.py" "$REPO/net/infer_np.py" "$TMP/net/"
cp "$NPZ" "$TMP/model.npz"
if [ -n "${CG_LIB_PATH:-}" ]; then
  cp -r "$CG_LIB_PATH" "$TMP/cg"
else
  echo "WARN: CG_LIB_PATH unset — cg/ engine NOT bundled; submission will fail to import." >&2
fi
( cd "$TMP" && tar -czf "$OUT" . )
echo "Done: $OUT (deck=$(basename "$DECK"), net=$(basename "$NPZ"))"
tar -tzf "$OUT" | head -20

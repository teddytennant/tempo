#!/usr/bin/env bash
# Pack the agent (main.py + deck.csv + the cg engine) into submission.tar.gz.
#   CG_LIB_PATH=/path/to/cg-lib/cg bash build_submission.sh
# The cg/ engine is downloaded from Kaggle and never committed (license).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

REPO="$(cd "$SRC/.." && pwd)"
cp "$SRC/main.py" "$TMP/main.py"
cp "$SRC/deck.csv" "$TMP/deck.csv"
# Bundle the search package (MCTS over the native engine API) so main.py can import it.
mkdir -p "$TMP/search"
cp "$REPO/search/__init__.py" "$REPO/search/mcts.py" "$TMP/search/"

if [ -n "${CG_LIB_PATH:-}" ]; then
  cp -r "$CG_LIB_PATH" "$TMP/cg"
else
  echo "WARN: CG_LIB_PATH unset — cg/ engine NOT bundled; submission will fail to import." >&2
fi

( cd "$TMP" && tar -czf "$SRC/submission.tar.gz" . )
echo "Done: $SRC/submission.tar.gz"
tar -tzf "$SRC/submission.tar.gz"

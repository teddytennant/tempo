#!/usr/bin/env bash
# Pack the agent (main.py + deck.csv + the cg engine) into submission.tar.gz.
#   CG_LIB_PATH=/path/to/cg-lib/cg bash build_submission.sh
# The cg/ engine is downloaded from Kaggle and never committed (license).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

REPO="$(cd "$SRC/.." && pwd)"
cp "$SRC/main.py" "$TMP/main.py"
cp "$SRC/prize_tracker.py" "$SRC/belief.py" "$SRC/opp_detect.py" "$SRC/opp_decks.py" "$SRC/scorer.py" "$SRC/crustle_rules.py" "$SRC/lucario_rules.py" "$SRC/starmie_rules.py" "$SRC/dunsparce_rules.py" "$SRC/lethal.py" "$TMP/" 2>/dev/null || true
cp "$SRC/deck.csv" "$TMP/deck.csv"
[ -f "$SRC/opp_model.csv" ] && cp "$SRC/opp_model.csv" "$TMP/opp_model.csv"
# Bundle the search package (MCTS over the native engine API) so main.py can import it.
mkdir -p "$TMP/search"
cp "$REPO/search/__init__.py" "$REPO/search/mcts.py" "$TMP/search/"

# Rust search core (manylinux2014 / glibc-2.17 .so) — main.py does `import engine_rs`.
ML_WHL=$(ls "$REPO"/engine_rs/target/wheels/*manylinux2014*.whl 2>/dev/null | head -1)
if [ -n "$ML_WHL" ]; then
  ( cd "$TMP" && unzip -oq "$ML_WHL" 'engine_rs/*' )
  echo "  (bundled Rust engine_rs from $(basename "$ML_WHL"))"
fi

# Optional learned net (numpy deploy). BUNDLE_NET=1 to include a proven model.
if [ "${BUNDLE_NET:-0}" = "1" ] && [ -f "$REPO/net/model.npz" ]; then
  mkdir -p "$TMP/net"
  cp "$REPO/net/__init__.py" "$REPO/net/features.py" "$REPO/net/infer_np.py" "$TMP/net/"
  cp "$REPO/net/model.npz" "$TMP/model.npz"
  echo "  (bundled learned net: net/ + model.npz)"
fi

if [ -n "${CG_LIB_PATH:-}" ]; then
  cp -r "$CG_LIB_PATH" "$TMP/cg"
else
  echo "WARN: CG_LIB_PATH unset — cg/ engine NOT bundled; submission will fail to import." >&2
fi

( cd "$TMP" && tar -czf "$SRC/submission.tar.gz" . )
echo "Done: $SRC/submission.tar.gz"
tar -tzf "$SRC/submission.tar.gz"

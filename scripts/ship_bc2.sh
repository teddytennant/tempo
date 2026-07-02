#!/usr/bin/env bash
# Build + packed-smoke + submit the hybrid BC2 agent.
#   DECK=data/decks/mined/The_Debauchery_Tea_Party.csv NPZ=net/bc_top2.npz \
#     bash scripts/ship_bc2.sh "submission message" [--dry-run]
set -euo pipefail
cd /home/gradient/projects/ai/tempo
MSG="${1:?usage: ship_bc2.sh <message> [--dry-run]}"
DRY="${2:-}"
DECK="${DECK:-data/decks/mined/The_Debauchery_Tea_Party.csv}"
NPZ="${NPZ:-net/bc_top2.npz}"
OUT="/home/gradient/projects/ai/tempo/agent/submission_bc2.tar.gz"

DECK="$DECK" NPZ="$NPZ" bash agent/build_bc2.sh "$OUT"

# Packed smoke: untar to a temp dir and drive the packed main.py through deck phase +
# a couple of real-engine decisions, exactly as extracted.
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -xzf "$OUT" -C "$TMP"
LIBSTDCXX="$(gcc -print-file-name=libstdc++.so.6 2>/dev/null || true)"
( cd "$TMP" && LD_LIBRARY_PATH="$(dirname "$LIBSTDCXX"):${LD_LIBRARY_PATH:-}" \
  "$OLDPWD/.venv/bin/python" - <<'EOF'
import main
d = main.agent({"select": None})
assert isinstance(d, list) and len(d) == 60, f"deck phase broken: {len(d) if isinstance(d,list) else d}"
assert main._net is not None, "model.npz did not load in packed layout"
from cg.game import battle_start, battle_select, battle_finish
obs, _ = battle_start(d, d)
assert obs is not None, "engine rejected the deck"
steps = 0
try:
    for _ in range(200):
        from cg.api import to_observation_class
        o = to_observation_class(obs)
        if o.current is not None and getattr(o.current, "result", -1) != -1:
            break
        if o.select is None:
            break
        sel = main.agent(obs)
        n = len(o.select.option)
        assert isinstance(sel, list) and all(0 <= i < n for i in sel) and sel, f"illegal selection {sel} (n={n})"
        obs = battle_select(sel)
        steps += 1
finally:
    battle_finish()
print(f"PACKED SMOKE OK: net loaded, deck accepted, {steps} legal decisions")
EOF
)

echo "packed smoke passed for $OUT (deck=$(basename "$DECK"), net=$(basename "$NPZ"))"
if [ "$DRY" = "--dry-run" ]; then
  echo "DRY RUN — not submitting."
  exit 0
fi
kaggle competitions submit -c pokemon-tcg-ai-battle -f "$OUT" -m "$MSG"
echo "SUBMITTED: $MSG"

#!/usr/bin/env bash
# Play one candidate tree against the whole independent-bot pool and print a per-bot table.
#
# The bots in agent/bots/ are faithful ports of published notebooks; none of them call our scorer,
# so this is the closest thing to a field measurement we can run offline. A head-to-head against a
# single opponent can be a counter-matchup artefact — this is what tells the two apart.
#
#   bash tools/fork_gauntlet.sh experiments/fork_alakazam alakazam 60
set -uo pipefail
SRC="$1"; LABEL="${2:-$(basename "$SRC")}"; GAMES="${3:-60}"; WORKERS="${4:-14}"; ENTRY="${5:-agent}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TOT_W=0; TOT_N=0
echo "=== gauntlet: $LABEL ($SRC), $GAMES games per bot ==="
for b in crustle crustle_hardened baseline950 dragapult ragingbolt abomasnow iono; do
  out=$(timeout 1800 ./scripts/run.sh -m tools.fork_arena \
        --a "$SRC" --b "experiments/botdir_$b" --label-a "$LABEL" --label-b "$b" \
        --entry-a "$ENTRY" --games "$GAMES" --workers "$WORKERS" 2>&1)
  line=$(echo "$out" | grep -E "^${LABEL}: " || true)
  w=$(echo "$line" | sed -E 's/^[^:]+: ([0-9]+) wins.*/\1/')
  l=$(echo "$line" | sed -E 's/.*  [^:]+: ([0-9]+) wins.*/\1/')
  exc=$(echo "$out" | grep -E "^exceptions:" || echo "exceptions: ?")
  rate=$(echo "$out" | grep -E "^A win-rate" || echo "n/a")
  if [ -n "${w:-}" ] && [ -n "${l:-}" ]; then
    TOT_W=$((TOT_W + w)); TOT_N=$((TOT_N + w + l))
  fi
  printf '  %-18s %s   [%s]\n' "$b" "$rate" "$exc"
done
if [ "$TOT_N" -gt 0 ]; then
  python3 -c "
import math
w,n=$TOT_W,$TOT_N
p=w/n; z=1.96; d=1+z*z/n
c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
print(f'  AGGREGATE $LABEL: {w}/{n} = {100*p:.2f}%  95% CI [{100*(c-h):.2f}, {100*(c+h):.2f}]')
"
fi

#!/usr/bin/env bash
# Run a Python entrypoint with the cg engine loadable on NixOS.
# The precompiled libcg.so needs libstdc++.so.6, which isn't on NixOS's default loader path.
# (Kaggle's sandbox has it; this wrapper is local-dev only.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

LIBSTDCXX="$(gcc -print-file-name=libstdc++.so.6 2>/dev/null || true)"
if [ ! -e "$LIBSTDCXX" ]; then
  LIBSTDCXX="$(find /nix/store -maxdepth 3 -name libstdc++.so.6 -path '*gcc*' 2>/dev/null | head -1)"
fi
[ -e "$LIBSTDCXX" ] || { echo "ERROR: libstdc++.so.6 not found; install gcc lib" >&2; exit 1; }

export LD_LIBRARY_PATH="$(dirname "$LIBSTDCXX"):${LD_LIBRARY_PATH:-}"
cd "$ROOT"
PY="python3"
[ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"
exec "$PY" "$@"

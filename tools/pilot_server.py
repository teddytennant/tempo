"""Stdin/stdout pilot worker for the mirror self-play A/B harness (tools/selfplay_ab.py).

WHY THIS EXISTS: a candidate agent and a baseline agent both define the SAME top-level
modules (`scorer`, `starmie_rules`, `prize_tracker`, …). They cannot coexist in one Python
process — the first `import scorer` wins and the second is silently aliased to it. So each
pilot runs in its OWN subprocess with a PRIVATE sys.path:

    sys.path = [<agent_dir>, <engine_root>, ...]   # agent dir FIRST, engine second

`<agent_dir>` supplies that pilot's scorer.py / starmie_rules.py / prize_tracker.py / …;
`<engine_root>` supplies the shared, read-only `cg` engine. Because the two pilots are
separate OS processes, the candidate's scorer and the baseline's scorer never collide.

PROTOCOL (newline-delimited JSON over stdin/stdout):
  • On startup, after `from scorer import best_options` succeeds, print a single line: READY
  • Then loop: read one line = a JSON obs dict -> compute best_options(obs) -> write one
    line = JSON list[int]. EOF on stdin -> clean exit.

The driver (selfplay_ab.py) owns the single live battle and never imports scorer at all;
it only ships the JSON obs to whichever pilot owns the seat-to-move and reads back the
selection. This keeps the two agents fully isolated while the engine state stays in one place.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True, help="agent dir (has scorer.py); placed FIRST on sys.path")
    ap.add_argument("--engine-root", required=True, help="root that contains the `cg` engine package")
    args = ap.parse_args()

    # PRIVATE path: this pilot's agent modules first, then the shared engine. Insert in reverse
    # so agent_dir ends up at index 0 (highest priority) and engine_root right after it.
    sys.path.insert(0, os.path.abspath(args.engine_root))
    sys.path.insert(0, os.path.abspath(args.agent))

    try:
        from scorer import best_options  # noqa: E402  (the pilot under test)
    except Exception as e:  # surface import failures to the driver instead of hanging
        sys.stdout.write(f"ERROR import failed: {e!r}\n")
        sys.stdout.flush()
        return 1

    # Handshake: the driver blocks on this line before sending the first obs.
    sys.stdout.write("READY\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obs = json.loads(line)
            sel = best_options(obs)
            # best_options always returns list[int]; coerce defensively so the wire stays clean.
            sel = [int(i) for i in (sel or [])]
        except Exception:
            sel = []  # never hang the driver; an illegal/empty pick just loses the game cleanly
        sys.stdout.write(json.dumps(sel) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

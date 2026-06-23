"""Durable mirror self-play A/B harness: candidate pilot vs baseline pilot, SAME deck both seats.

Both seats play data/decks/starmie.csv; the ONLY thing that differs is which agent pilots the
seat. This isolates a pilot change (e.g. an edit to agent/starmie_rules.py) from deck/luck noise.

THE COLLISION PROBLEM. The candidate and the baseline are two copies of the same agent codebase;
both define top-level modules `scorer` / `starmie_rules` / `prize_tracker`. They cannot live in one
Python process. SOLUTION: each pilot runs in its OWN subprocess (tools/pilot_server.py) with a
private sys.path (its agent dir first, the shared `cg` engine second). This driver owns the single
live battle, never imports `scorer`, and merely ships the JSON obs to whichever pilot owns the
seat-to-move, reading back the list[int] selection.

PARALLELISM. Each worker process runs its own engine battle and owns its own dedicated pair of
pilot subprocesses (spawned once in the pool initializer, reused across that worker's games). So a
run uses workers * (1 driver + 2 pilots) processes; keep --workers modest on a small box.

SEATS ALTERNATE every game so neither pilot gets a permanent first/second-player edge.

Usage (engine needs libstdc++ on the loader path on NixOS):
  export LD_LIBRARY_PATH="$(dirname "$(gcc -print-file-name=libstdc++.so.6)")"
  .venv/bin/python -m tools.selfplay_ab --games 400 --workers 6
  # candidate=a worktree, baseline=the frozen HEAD snapshot:
  .venv/bin/python -m tools.selfplay_ab \
      --candidate /home/gradient/.claude/worktrees/wt_pilotup \
      --baseline  tools/baseline_starmie_agent --games 400 --workers 6
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Per-worker globals (populated by _init): the engine entrypoints + the two pilot subprocesses.
_ENGINE = None          # (battle_start, battle_finish, battle_select, to_observation_class)
_CAND = None            # candidate pilot Popen
_BASE = None            # baseline  pilot Popen
_DECK = None


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _spawn_pilot(agent_dir, engine_root):
    """Start a pilot subprocess and wait for its READY handshake."""
    cmd = [sys.executable, os.path.join(_ROOT, "tools", "pilot_server.py"),
           "--agent", agent_dir, "--engine-root", engine_root]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, bufsize=1, env=os.environ.copy())
    line = p.stdout.readline().strip()
    if line != "READY":
        rest = ""
        try:
            rest = p.stdout.read()
        except Exception:
            pass
        raise RuntimeError(f"pilot {agent_dir} failed to start: {line!r} {rest!r}")
    return p


def _ask(pilot, obs):
    """Ship one JSON obs to a pilot, read back list[int]. Raises on a dead pilot."""
    pilot.stdin.write(json.dumps(obs) + "\n")
    pilot.stdin.flush()
    line = pilot.stdout.readline()
    if not line:
        raise RuntimeError("pilot died")
    return json.loads(line)


def _init(cand_agent, base_agent, engine_root, deck):
    global _ENGINE, _CAND, _BASE, _DECK
    sys.path.insert(0, engine_root)
    from cg.api import to_observation_class
    from cg.game import battle_start, battle_finish, battle_select
    _ENGINE = (battle_start, battle_finish, battle_select, to_observation_class)
    _DECK = deck
    _CAND = _spawn_pilot(cand_agent, engine_root)
    _BASE = _spawn_pilot(base_agent, engine_root)

    import atexit
    def _cleanup():
        for p in (_CAND, _BASE):
            try:
                p.stdin.close()
            except Exception:
                pass
            try:
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
    atexit.register(_cleanup)


def _play_one(args):
    """Play one mirror game. `cand_seat` is the seat (0/1) the CANDIDATE pilots; baseline takes the
    other. Returns 'W' (candidate won), 'L' (baseline won), 'D' (draw/unfinished), 'E' (error)."""
    cand_seat, max_steps = args
    battle_start, battle_finish, battle_select, to_observation_class = _ENGINE
    try:
        obs, _start = battle_start(_DECK, _DECK)
        if obs is None:
            return "E"
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                if res == 2:
                    return "D"
                return "W" if res == cand_seat else "L"
            if oc.select is None:
                battle_finish()
                return "D"
            who = oc.current.yourIndex
            pilot = _CAND if who == cand_seat else _BASE
            sel = _ask(pilot, obs)
            obs = battle_select(sel)
        battle_finish()
        return "D"  # unfinished within step budget
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return "E"


def _wilson(w, n, z=1.96):
    """95% Wilson score interval for a binomial proportion (w wins of n decided games)."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = w / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=_ROOT,
                    help="candidate REPO path; its agent/ subdir is the pilot (default: live repo)")
    ap.add_argument("--baseline", default=os.path.join(_ROOT, "tools", "baseline_starmie_agent"),
                    help="baseline FLAT agent dir (has scorer.py at top level)")
    ap.add_argument("--engine-root", default=_ROOT, help="root containing the shared `cg` engine")
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data", "decks", "starmie.csv"))
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-steps", type=int, default=6000)
    args = ap.parse_args()

    # Resolve the candidate agent dir: a repo path uses its agent/ subdir; a flat dir is used as-is.
    cand = os.path.abspath(args.candidate)
    cand_agent = os.path.join(cand, "agent")
    if not os.path.isfile(os.path.join(cand_agent, "scorer.py")):
        cand_agent = cand  # already a flat agent dir
    base_agent = os.path.abspath(args.baseline)
    engine_root = os.path.abspath(args.engine_root)
    deck = _read_deck(args.deck)

    for label, d in (("candidate agent", cand_agent), ("baseline agent", base_agent)):
        ok = os.path.isfile(os.path.join(d, "scorer.py"))
        print(f"{label:16s}: {d}  [{'ok' if ok else 'MISSING scorer.py'}]")
    print(f"engine root     : {engine_root}")
    print(f"deck            : {args.deck}  ({len(deck)} cards)")
    print(f"games           : {args.games}   workers: {args.workers}\n")

    jobs = [(g % 2, args.max_steps) for g in range(args.games)]  # alternate candidate seat

    counts = {"W": 0, "L": 0, "D": 0, "E": 0}
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=args.workers, initializer=_init,
                  initargs=(cand_agent, base_agent, engine_root, deck)) as pool:
        done = 0
        for outcome in pool.imap_unordered(_play_one, jobs, chunksize=1):
            counts[outcome] += 1
            done += 1
            if done % 20 == 0 or done == len(jobs):
                w, l = counts["W"], counts["L"]
                dec = w + l
                wr = (w / dec) if dec else 0.0
                print(f"  [{done:4d}/{len(jobs)}] cand W{w} L{l} D{counts['D']} E{counts['E']}  "
                      f"wr={wr:5.1%}  ({time.time()-t0:5.1f}s)", flush=True)
    dt = time.time() - t0

    w, l, draws, errs = counts["W"], counts["L"], counts["D"], counts["E"]
    dec = w + l
    p, lo, hi = _wilson(w, dec)
    print("\n=== mirror self-play A/B: CANDIDATE vs BASELINE (same deck, seats alternated) ===")
    print(f"candidate: W{w} L{l}  draws={draws}  errors={errs}  (decided={dec}/{args.games})")
    print(f"candidate win-rate = {p:.1%}   95% Wilson CI [{lo:.1%}, {hi:.1%}]")
    if lo > 0.5:
        verdict = "STRONGER (CI excludes 50%)"
    elif hi < 0.5:
        verdict = "WEAKER (CI excludes 50%)"
    else:
        verdict = "inconclusive (CI spans 50%)"
    print(f"VERDICT: {verdict}")
    print(f"time={dt:.1f}s  ({dt/max(1,args.games)*1000:.0f} ms/game)")


if __name__ == "__main__":
    main()

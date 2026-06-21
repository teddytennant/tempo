"""Parallel matchup evaluation across cores (for the 16-core server).

Runs one matchup (p0 vs p1, each a pilot on a deck, mcts pilots may use an opponent model) over
many games spread across worker processes, and reports p0 win-rate with a 95% CI. Each worker is a
separate process with its own engine instance (spawn), so the native lib's global state is isolated.

Run (via scripts/run.sh so libcg.so loads):
  ./scripts/run.sh -m tools.par_eval --deck0 data/decks/dragapult.csv --deck1 data/decks/mega_lucario.csv \
      --p0 mcts --opp0 data/decks/mega_lucario.csv --iters0 60 --p1 floor --games 64 --workers 14
"""
from __future__ import annotations

import argparse
import math
import os
import random as _random
import sys
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from arena.selfplay import play_game  # noqa: E402
from cg.api import to_observation_class  # noqa: E402


def _read(path):
    if not path:
        return None
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _rand_pilot(obs_dict):
    o = to_observation_class(obs_dict)
    if o.select is None:
        return []
    n = len(o.select.option); k = o.select.maxCount
    return _random.sample(range(n), min(k, n)) if (k and n) else []


def _mk(spec, seed):
    pilot, deck, opp, iters = spec
    if pilot == "random":
        return _rand_pilot
    import main as m
    if pilot == "floor":
        return m.floor_agent
    from search.mcts import MctsAgent
    return MctsAgent(deck, iters=iters, seed=seed, opp_model=opp, fallback=m.floor_agent)


def _worker(task):
    seed, p0spec, p1spec, deck0, deck1 = task
    _random.seed(seed)
    a0 = _mk(p0spec, seed); a1 = _mk(p1spec, seed + 7919)
    try:
        res, _, errs = play_game(a0, a1, deck0, deck1)
        return (res, errs)
    except Exception:
        return (-1, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck0", required=True); ap.add_argument("--deck1", required=True)
    ap.add_argument("--p0", default="mcts"); ap.add_argument("--p1", default="floor")
    ap.add_argument("--opp0", default=None); ap.add_argument("--opp1", default=None)
    ap.add_argument("--iters0", type=int, default=60); ap.add_argument("--iters1", type=int, default=60)
    ap.add_argument("--games", type=int, default=32); ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--label", default="")
    a = ap.parse_args()

    d0, d1 = _read(a.deck0), _read(a.deck1)
    p0spec = (a.p0, d0, _read(a.opp0), a.iters0)
    p1spec = (a.p1, d1, _read(a.opp1), a.iters1)
    tasks = [(a.seed + i, p0spec, p1spec, d0, d1) for i in range(a.games)]

    ctx = get_context("spawn")
    with ctx.Pool(a.workers) as pool:
        out = pool.map(_worker, tasks)

    w0 = sum(1 for r, _ in out if r == 0)
    w1 = sum(1 for r, _ in out if r == 1)
    draw = sum(1 for r, _ in out if r == 2)
    unf = sum(1 for r, _ in out if r == -1)
    errs = sum(e for _, e in out)
    dec = w0 + w1
    wr = w0 / dec if dec else 0.0
    ci = 1.96 * math.sqrt(wr * (1 - wr) / dec) if dec else 0.0
    lab = a.label or f"{a.p0}({os.path.basename(a.deck0)}) vs {a.p1}({os.path.basename(a.deck1)})"
    print(f"[{lab}] games={a.games} p0={w0} p1={w1} draw={draw} unfinished={unf} errors={errs}")
    print(f"    p0 win-rate = {wr:.1%} ± {ci:.1%}  (95% CI, n={dec})")


if __name__ == "__main__":
    main()

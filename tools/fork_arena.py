"""Head-to-head arena between two *arbitrary* packed agent trees.

`tools/eval_vs_bots.py` plays our scorer against hand-ported bots that live inside this repo.
That port step is the expensive, error-prone part, and it cannot be done for a foreign agent we
want to evaluate today. This harness skips it: point it at two directories, each containing a
self-contained `main.py` exposing `agent(obs_dict)` (plus whatever that file imports and its own
`deck.csv`), and it plays full real-engine games between them with seats alternated.

Each side is loaded by file path under a private module name, with cwd and sys.path set to that
side's own directory during the load, so two trees that both call their entry file `main.py` and
both read a relative `deck.csv` do not collide.

  ./scripts/run.sh -m tools.fork_arena --a experiments/fork_mak1084 --b experiments/luc_majkel_v8_src/agent \
      --games 200 --workers 12

Reports A's win-rate with a 95% CI, plus per-side exception counts and latency — an agent that
throws here would fail Kaggle's validation game, so a nonzero exception count is disqualifying
regardless of the win-rate.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import random
import sys
import time
import traceback
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LATENCY_BUDGET_S = 1.0
GAME_CLOCK_S = 600.0


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _load_side(src, modname, entry):
    """Import <src>/main.py as `modname` with <src> as cwd and first on sys.path."""
    src = os.path.abspath(src)
    old_cwd = os.getcwd()
    old_path = list(sys.path)
    try:
        os.chdir(src)
        sys.path.insert(0, src)
        # A packed tree may keep its modules one level up (agent/ next to search/).
        parent = os.path.dirname(src)
        if os.path.isdir(os.path.join(parent, "search")):
            sys.path.insert(1, parent)
        spec = importlib.util.spec_from_file_location(modname, os.path.join(src, "main.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[modname] = mod
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path
    fn = getattr(mod, entry)
    return fn


def _play_one(task):
    src_a, entry_a, src_b, entry_b, swap, max_steps, seed = task
    random.seed(seed)
    res = {"winner": None, "steps": 0, "exc": [0, 0], "time": [0.0, 0.0], "max_lat": [0.0, 0.0],
           "over_budget": [0, 0], "fail": []}
    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class
        fa = _load_side(src_a, "_forkA", entry_a)
        deck_a = _read_deck(os.path.join(src_a, "deck.csv"))
        fb = _load_side(src_b, "_forkB", entry_b)
        deck_b = _read_deck(os.path.join(src_b, "deck.csv"))
    except Exception:
        res["fail"].append(("import", traceback.format_exc()[-1200:]))
        return res

    # seat 0 is whoever goes first; swap alternates which side sits there.
    sides = [(fb, deck_b, 1), (fa, deck_a, 0)] if swap else [(fa, deck_a, 0), (fb, deck_b, 1)]
    fns = [s[0] for s in sides]
    owner = [s[2] for s in sides]  # seat -> which side (0=A, 1=B)

    obs, _ = battle_start(sides[0][1], sides[1][1])
    if obs is None:
        res["fail"].append(("start_refused", "engine refused the deck pair"))
        return res
    try:
        for step in range(max_steps):
            res["steps"] = step + 1
            oc = to_observation_class(obs)
            cur = oc.current
            r = cur.result if cur is not None else -1
            if r is not None and r >= 0:
                # r is the seat index of the winner (2 = draw).
                res["winner"] = "draw" if r == 2 else ("A" if owner[r] == 0 else "B")
                return res
            if obs.get("select") is None:
                return res
            who = cur.yourIndex if cur is not None else 0
            side = owner[who]
            t0 = time.monotonic()
            try:
                sel = fns[who](obs)
            except Exception:
                res["exc"][side] += 1
                if len(res["fail"]) < 4:
                    res["fail"].append((f"exc_{'AB'[side]}", traceback.format_exc()[-700:]))
                sd = obs["select"]
                sel = list(range(min(sd.get("minCount", 0) or 0, len(sd.get("option") or []))))
            lat = time.monotonic() - t0
            res["time"][side] += lat
            res["max_lat"][side] = max(res["max_lat"][side], lat)
            if lat > LATENCY_BUDGET_S:
                res["over_budget"][side] += 1
            obs = battle_select(sel)
            if obs is None:
                res["fail"].append((f"reject_{'AB'[side]}", f"engine rejected {sel!r}"))
                return res
    finally:
        try:
            battle_finish()
        except Exception:
            pass
    return res


def _wilson(k, n):
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="dir with main.py + deck.csv")
    ap.add_argument("--b", required=True)
    ap.add_argument("--entry-a", default="agent")
    ap.add_argument("--entry-b", default="agent")
    ap.add_argument("--label-a", default=None)
    ap.add_argument("--label-b", default=None)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    la = args.label_a or os.path.basename(os.path.abspath(args.a))
    lb = args.label_b or os.path.basename(os.path.abspath(args.b))
    print(f"A = {la}  ({os.path.abspath(args.a)})")
    print(f"B = {lb}  ({os.path.abspath(args.b)})")
    print(f"games={args.games} workers={args.workers} (seats alternated)")

    tasks = [(os.path.abspath(args.a), args.entry_a, os.path.abspath(args.b), args.entry_b,
              g % 2 == 1, args.max_steps, args.seed + g) for g in range(args.games)]

    t0 = time.monotonic()
    ctx = get_context("spawn")
    with ctx.Pool(args.workers) as pool:
        out = pool.map(_play_one, tasks)
    dt = time.monotonic() - t0

    wa = sum(1 for r in out if r["winner"] == "A")
    wb = sum(1 for r in out if r["winner"] == "B")
    draws = sum(1 for r in out if r["winner"] == "draw")
    unfinished = sum(1 for r in out if r["winner"] is None)
    exc_a = sum(r["exc"][0] for r in out)
    exc_b = sum(r["exc"][1] for r in out)
    ob_a = sum(r["over_budget"][0] for r in out)
    ob_b = sum(r["over_budget"][1] for r in out)
    mx_a = max((r["max_lat"][0] for r in out), default=0.0)
    mx_b = max((r["max_lat"][1] for r in out), default=0.0)
    tm_a = max((r["time"][0] for r in out), default=0.0)
    tm_b = max((r["time"][1] for r in out), default=0.0)

    decided = wa + wb
    lo, hi = _wilson(wa, decided)
    print(f"\nelapsed {dt:.1f}s   decided={decided} draws={draws} unfinished={unfinished}")
    print(f"{la}: {wa} wins   {lb}: {wb} wins")
    if decided:
        print(f"A win-rate = {100.0 * wa / decided:.2f}%  95% CI [{100 * lo:.2f}, {100 * hi:.2f}]")
    print(f"exceptions: A={exc_a} B={exc_b}   moves>1s: A={ob_a} B={ob_b}")
    print(f"max single-move latency: A={mx_a * 1000:.1f}ms B={mx_b * 1000:.1f}ms")
    print(f"worst cumulative agent time in one game (of {GAME_CLOCK_S:.0f}s): A={tm_a:.1f}s B={tm_b:.1f}s")

    fails = [f for r in out for f in r["fail"]]
    if fails:
        print(f"\n{len(fails)} failure records; first 5:")
        for kind, detail in fails[:5]:
            print(f"  [{kind}] {str(detail)[:600]}")


if __name__ == "__main__":
    main()

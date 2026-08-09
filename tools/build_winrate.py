"""Does a packed build actually WIN games? (`--src`, same contract as tools/robust_probe.)

robust_probe proves a build is legal and fast; it never proves it is any good. This measures the
one thing that decides ladder score: win rate, of the deploy entry point, against a named
opponent pilot+deck. Use it before shipping any artifact whose live score you cannot explain.

  ./scripts/run.sh -m tools.build_winrate --src experiments/proven_src \
      --opp random --opp-deck data/decks/crustle.csv --games 40 --workers 10
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _one(task):
    src, opp_kind, opp_src, deck_me, deck_opp, seed, me_first, max_steps = task
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    random.seed(seed)
    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class
        import agent.main as M
    except Exception:
        return ("import_fail", traceback.format_exc()[-500:])

    mine = M.agent

    if opp_kind == "random":
        def theirs(obs_dict):
            o = to_observation_class(obs_dict)
            if o.select is None:
                return []
            if o.select.option is None:                     # deck-selection frame
                return deck_opp
            n, k = len(o.select.option), o.select.maxCount or 1
            lo = o.select.minCount or 1
            return random.sample(range(n), min(max(lo, 1), n)) if k else []
    elif opp_kind == "self":
        theirs = mine
    else:                                                   # another packed build
        sys.path.insert(0, os.path.join(opp_src, "agent"))
        sys.path.insert(0, opp_src)
        import importlib
        theirs = importlib.import_module("agent.main").agent

    a0, a1 = (mine, theirs) if me_first else (theirs, mine)
    d0, d1 = (deck_me, deck_opp) if me_first else (deck_opp, deck_me)
    me_idx = 0 if me_first else 1
    try:
        obs_dict, _ = battle_start(d0, d1)
        if obs_dict is None:
            return ("start_fail", None)
        errs = 0
        for step in range(max_steps):
            obs = to_observation_class(obs_dict)
            cur = obs.current
            if cur is not None and getattr(cur, "result", -1) != -1:
                r = cur.result
                return ("win" if r == me_idx else "draw" if r == 2 else "loss", step)
            if obs.select is None:
                return ("unfinished", step)
            who = cur.yourIndex if cur is not None else 0
            try:
                sel = [a0, a1][who](obs_dict)
            except Exception:
                errs += 1
                sel = list(range(min(obs.select.minCount, len(obs.select.option))))
            obs_dict = battle_select(sel)
        return ("timeout", max_steps)
    finally:
        try:
            battle_finish()
        except Exception:
            pass


def main():
    import multiprocessing as mp
    from collections import Counter

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--opp", default="random", help="random | self | <path to another build>")
    ap.add_argument("--opp-deck", default=None, help="defaults to our own deck (mirror)")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    deck_me = _read_deck(os.path.join(src, "agent", "deck.csv"))
    assert len(deck_me) == 60
    deck_opp = _read_deck(a.opp_deck) if a.opp_deck else list(deck_me)
    opp_src = os.path.abspath(a.opp) if a.opp not in ("random", "self") else ""
    opp_kind = a.opp if a.opp in ("random", "self") else "build"

    jobs = [(src, opp_kind, opp_src, deck_me, deck_opp, a.seed + i, i % 2 == 0, a.max_steps)
            for i in range(a.games)]
    label = a.label or f"{os.path.basename(src)} vs {a.opp}"
    ctx = mp.get_context("spawn")
    with ctx.Pool(a.workers) as pool:
        out = pool.map(_one, jobs)

    tally = Counter(r[0] for r in out)
    decided = tally["win"] + tally["loss"]
    wr = 100.0 * tally["win"] / decided if decided else float("nan")
    print(f"[{label}] games={a.games}  {dict(tally)}")
    print(f"[{label}] WIN RATE (decided) = {wr:.1f}%  ({tally['win']}/{decided})")
    for r in out:
        if r[0] in ("import_fail", "start_fail"):
            print("FAILURE:", r)
            break


if __name__ == "__main__":
    main()

"""Local self-play harness over the real cg engine (battle_start / battle_select).

Drives full games between two agent callables and reports win-rate, errors, and timing.
This is the honest offline arena (per docs/plans/05-eval-methodology.md). The real engine ships
a precompiled libcg.so; on NixOS, run via scripts/run.sh which sets LD_LIBRARY_PATH for libstdc++.

Usage:
    python -m arena.selfplay --games 20 --p0 floor --p1 random
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402


def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _DECK
    n = len(obs.select.option)
    k = obs.select.maxCount
    if k <= 0 or n == 0:
        return []
    return random.sample(range(n), min(k, n))


def _load_floor():
    import main as floor  # agent/main.py
    return floor.floor_agent


def _load_deploy():
    import main as m  # the real submission entry (MCTS + clock + fallback)
    return m.agent


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def play_game(agent0, agent1, deck0, deck1, max_steps=2000):
    """Returns (result, steps, error_count). result: 0/1 winner, 2 draw, -1 unfinished."""
    agents = [agent0, agent1]
    obs_dict, start = battle_start(deck0, deck1)
    if obs_dict is None:
        return -1, 0, 1  # engine refused to start (illegal deck?)
    errors = 0
    try:
        for step in range(max_steps):
            obs = to_observation_class(obs_dict)
            cur = obs.current
            if cur is not None and getattr(cur, "result", -1) != -1:
                return cur.result, step, errors
            if obs.select is None:
                return -1, step, errors
            who = cur.yourIndex if cur is not None else 0
            try:
                sel = agents[who](obs_dict)
            except Exception:
                errors += 1
                sel = list(range(min(obs.select.minCount, len(obs.select.option))))
            obs_dict = battle_select(sel)
        return -1, max_steps, errors
    finally:
        battle_finish()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--p0", choices=["floor", "random", "mcts", "deploy"], default="floor")
    ap.add_argument("--p1", choices=["floor", "random", "mcts", "deploy"], default="random")
    ap.add_argument("--deck", default=os.path.join(_ROOT, "agent", "deck.csv"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=60)
    args = ap.parse_args()

    random.seed(args.seed)
    global _DECK
    _DECK = _read_deck(args.deck)

    def _make(name, seed):
        if name == "random":
            return random_agent
        if name == "floor":
            return _load_floor()
        if name == "mcts":
            from search.mcts import MctsAgent
            return MctsAgent(_DECK, iters=args.iters, seed=seed, fallback=_load_floor())
        if name == "deploy":
            return _load_deploy()
        raise ValueError(name)

    a0, a1 = _make(args.p0, 10), _make(args.p1, 20)

    wins = [0, 0, 0]  # p0, p1, draw
    unfinished = total_steps = total_errors = 0
    t0 = time.time()
    for g in range(args.games):
        res, steps, errs = play_game(a0, a1, _DECK, _DECK)
        total_steps += steps
        total_errors += errs
        if res in (0, 1):
            wins[res] += 1
        elif res == 2:
            wins[2] += 1
        else:
            unfinished += 1
    dt = time.time() - t0

    print(f"games={args.games}  p0={args.p0} p1={args.p1}")
    print(f"  p0 wins={wins[0]}  p1 wins={wins[1]}  draws={wins[2]}  unfinished={unfinished}")
    decided = wins[0] + wins[1]
    if decided:
        print(f"  p0 win-rate (decided) = {wins[0]/decided:.1%}")
    print(f"  errors={total_errors}  avg steps/game={total_steps/max(1,args.games):.0f}")
    print(f"  time={dt:.1f}s  ({dt/max(1,args.games)*1000:.0f} ms/game, "
          f"{total_steps/max(1e-9,dt):.0f} steps/s)")


if __name__ == "__main__":
    main()

"""Head-to-head: greedy heuristic scorer (agent/scorer.best_options) vs vanilla Rust MCTS.

Both pilot the same deck (data/decks/starmie.csv). Seats alternate each game so neither side
gets a permanent first/second-player edge. Reports the scorer's win-rate; >55% means the
scorer is the stronger no-search policy (the whole point — frontier bots beat search with it).

Run:  ./scripts/run.sh -m tools.validate_scorer --games 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402
from scorer import best_options  # noqa: E402

import engine_rs  # noqa: E402
engine_rs.init(os.path.abspath(os.path.join(_ROOT, "cg", "libcg.so")))


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def make_mcts_agent(deck, budget_s, seed):
    def mcts_agent(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        try:
            sel = engine_rs.choose(json.dumps(obs_dict), deck, deck, budget_s, 10**9, 1.4, seed, False)
            if isinstance(sel, list) and len(sel) >= 1:
                return sel
        except Exception:
            pass
        # robust fallback identical in spirit to the scorer's
        return best_options(obs_dict)
    return mcts_agent


def scorer_agent(deck):
    def a(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        return best_options(obs_dict)
    return a


def play_game(a0, d0, a1, d1, max_steps=4000):
    """Returns winner index (0/1), 2 for draw/unfinished."""
    try:
        obs, start = battle_start(d0, d1)
        if obs is None:
            return 2
        agents = [a0, a1]
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                return res
            who = oc.current.yourIndex
            obs = battle_select(agents[who](obs))
        battle_finish()
        return 2
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data", "decks", "starmie.csv"))
    ap.add_argument("--budget", type=float, default=0.3, help="MCTS seconds/move")
    args = ap.parse_args()

    deck = _read_deck(args.deck)
    scorer = scorer_agent(deck)

    w = l = d = 0
    t0 = time.time()
    for g in range(args.games):
        mcts = make_mcts_agent(deck, args.budget, seed=g + 1)
        if g % 2 == 0:
            # scorer = seat 0
            res = play_game(scorer, deck, mcts, deck)
            scorer_seat = 0
        else:
            res = play_game(mcts, deck, scorer, deck)
            scorer_seat = 1
        if res == 2:
            d += 1
        elif res == scorer_seat:
            w += 1
        else:
            l += 1
        wr = 100.0 * (w + 0.5 * d) / (g + 1)
        print(f"[{g+1:3d}/{args.games}] scorer W{w} L{l} D{d}  winrate={wr:5.1f}%  ({time.time()-t0:5.1f}s)",
              flush=True)

    wr = 100.0 * (w + 0.5 * d) / max(1, args.games)
    print(f"\n=== scorer vs vanilla MCTS ({args.budget}s/move): "
          f"W{w} L{l} D{d}  scorer winrate = {wr:.1f}% over {args.games} games ===")


if __name__ == "__main__":
    main()

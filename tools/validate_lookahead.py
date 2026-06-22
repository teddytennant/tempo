"""Head-to-head: scorer-guided lookahead (agent/lookahead) vs the pure greedy scorer.

Both pilot the SAME deck (data/decks/crustle.csv). Seats alternate each game so neither side
gets a permanent first/second-player edge. The lookahead must win >53% to justify the extra
compute (the AlphaGo claim: strong prior + lookahead > the prior alone).

Run:  ./scripts/run.sh -m tools.validate_lookahead --games 30
"""
from __future__ import annotations

import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402
import scorer  # noqa: E402
import lookahead  # noqa: E402

import engine_rs  # noqa: E402
engine_rs.init(os.path.abspath(os.path.join(_ROOT, "cg", "libcg.so")))


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def scorer_agent(deck):
    def a(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        return scorer.best_options(obs_dict)
    return a


def lookahead_agent(deck):
    # per-decision timing accumulates on the closure for reporting
    stats = {"n": 0, "t": 0.0, "qualified": 0}

    def a(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        sel = obs_dict.get("select") or {}
        is_main = sel.get("context") == 0 and sel.get("maxCount") == 1 and len(sel.get("option") or []) > 1
        t0 = time.perf_counter()
        out = lookahead.best_options(obs_dict, deck)
        dt = time.perf_counter() - t0
        if is_main:
            stats["n"] += 1
            stats["t"] += dt
            stats["qualified"] += 1
        return out

    a.stats = stats
    return a


def play_game(a0, d0, a1, d1, max_steps=4000):
    """Returns winner index (0/1), 2 for draw/unfinished."""
    try:
        obs, _ = battle_start(d0, d1)
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
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data", "decks", "crustle.csv"))
    args = ap.parse_args()

    deck = _read_deck(args.deck)
    scorer_a = scorer_agent(deck)
    look_a = lookahead_agent(deck)

    w = l = d = 0
    t0 = time.time()
    for g in range(args.games):
        if g % 2 == 0:
            res = play_game(look_a, deck, scorer_a, deck)  # lookahead seat 0
            look_seat = 0
        else:
            res = play_game(scorer_a, deck, look_a, deck)  # lookahead seat 1
            look_seat = 1
        if res == 2:
            d += 1
        elif res == look_seat:
            w += 1
        else:
            l += 1
        wr = 100.0 * (w + 0.5 * d) / (g + 1)
        st = look_a.stats
        per = (st["t"] / st["n"] * 1000.0) if st["n"] else 0.0
        print(f"[{g+1:3d}/{args.games}] lookahead W{w} L{l} D{d}  winrate={wr:5.1f}%  "
              f"({per:5.1f} ms/qualified-decision, {time.time()-t0:5.1f}s)", flush=True)

    wr = 100.0 * (w + 0.5 * d) / max(1, args.games)
    st = look_a.stats
    per = (st["t"] / st["n"] * 1000.0) if st["n"] else 0.0
    print(f"\n=== lookahead vs pure scorer: W{w} L{l} D{d}  "
          f"lookahead winrate = {wr:.1f}% over {args.games} games ===")
    print(f"=== {st['n']} qualified lookahead decisions, {per:.1f} ms avg/decision ===")


if __name__ == "__main__":
    main()

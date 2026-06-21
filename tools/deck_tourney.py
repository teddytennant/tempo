"""Deck-vs-deck round-robin with a fixed pilot — local signal for DECK strength.

Unlike self-play-vs-random (which doesn't predict the ladder), pitting candidate decks against
each other with the SAME pilot isolates deck quality. Still imperfect (generic pilot), but the right
local lens for "which deck", to combine with PTCG domain knowledge. The ladder is the final judge.

Run: ./scripts/run.sh -m tools.deck_tourney --decks-dir data/decks --games 12
"""
from __future__ import annotations

import argparse
import glob
import os
import random
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.game import battle_start, battle_finish  # noqa: E402
from arena.selfplay import play_game, _read_deck  # noqa: E402


def _pilot(name):
    if name == "floor":
        import main as m
        return m.floor_agent
    if name == "mcts":
        from search.mcts import MctsAgent
        # NB: MCTS determinization uses one deck; for a fair tourney we make a fresh pilot per deck.
        return "mcts"
    raise ValueError(name)


def _valid(deck):
    try:
        obs, start = battle_start(deck, deck)
        battle_finish()
        return obs is not None
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "decks"))
    ap.add_argument("--games", type=int, default=12)  # games per ordered pair (split first/second)
    ap.add_argument("--pilot", default="floor", choices=["floor", "mcts"])
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed)

    files = sorted(glob.glob(os.path.join(args.decks_dir, "*.csv")))
    decks = {}
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        d = _read_deck(f)
        if len(d) != 60:
            print(f"SKIP {name}: {len(d)} cards (need 60)"); continue
        if not _valid(d):
            print(f"SKIP {name}: engine rejected deck (illegal?)"); continue
        decks[name] = d
    names = list(decks)
    print(f"valid decks: {names}\n")
    if len(names) < 2:
        print("need >=2 valid decks"); return

    def pilot_for(deck):
        if args.pilot == "floor":
            import main as m
            return m.floor_agent
        from search.mcts import MctsAgent
        import main as m
        return MctsAgent(deck, iters=args.iters, fallback=m.floor_agent)

    wins = {n: 0 for n in names}
    played = {n: 0 for n in names}
    grid = {(a, b): 0 for a in names for b in names}
    half = max(1, args.games // 2)
    for a in names:
        for b in names:
            if a == b:
                continue
            pa, pb = pilot_for(decks[a]), pilot_for(decks[b])
            for g in range(half):  # a as p0
                res, _, _ = play_game(pa, pb, decks[a], decks[b])
                if res == 0:
                    wins[a] += 1; grid[(a, b)] += 1
                elif res == 1:
                    wins[b] += 1
                played[a] += 1; played[b] += 1

    print("=== overall win-rate (as p0 vs all others) ===")
    rank = sorted(names, key=lambda n: wins[n] / max(1, played[n]), reverse=True)
    for n in rank:
        print(f"  {n:24s}  {wins[n]:3d}/{played[n]:<3d}  {wins[n]/max(1,played[n]):.1%}")
    print("\n=== win grid (row beats col, p0) ===")
    print("            " + "".join(f"{b[:10]:>11s}" for b in names))
    for a in names:
        row = "".join(f"{grid[(a,b)]:>11d}" if a != b else f"{'-':>11s}" for b in names)
        print(f"{a[:11]:11s} {row}")


if __name__ == "__main__":
    main()

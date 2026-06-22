"""Deck-vs-deck round-robin piloted by the rule-based scorer — which DECK wins.

Both seats are driven by agent/scorer.best_options (deck-agnostic, no search), so the only
variable across matchups is the decklist. For each ordered pair (deckA as p0, deckB as p1) we
play N games and record the winner. Summing each deck's wins across every matchup it appears in
gives an overall win-rate per deck — the local lens for "which deck should the scorer pilot".

Games run in a multiprocessing pool (spawn context): the cg engine keeps process-global battle
state, so each worker plays one game at a time, but many workers run in parallel.

Run: ./scripts/run.sh -m tools.deck_tourney --games 16 --workers 12
"""
from __future__ import annotations

import argparse
import glob
import multiprocessing as mp
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _play_one(args):
    """Worker: play deckA (p0) vs deckB (p1), both piloted by the scorer.

    Returns (name_a, name_b, result) where result is 0 (p0/A wins), 1 (p1/B wins),
    2 (draw/unfinished), or -1 (engine refused / error).
    """
    name_a, deck_a, name_b, deck_b, max_steps = args
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "agent"))
    from cg.api import to_observation_class
    from cg.game import battle_start, battle_finish, battle_select
    from scorer import best_options

    def agent(obs_dict):
        if obs_dict.get("select") is None:
            return []  # no decision pending
        return best_options(obs_dict)

    try:
        obs, _start = battle_start(deck_a, deck_b)
        if obs is None:
            return (name_a, name_b, -1)
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                return (name_a, name_b, res)
            if oc.select is None:
                battle_finish()
                return (name_a, name_b, 2)
            who = oc.current.yourIndex
            sel = agent(obs)
            obs = battle_select(sel)
        battle_finish()
        return (name_a, name_b, 2)  # unfinished
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return (name_a, name_b, -1)


def _valid(name, deck):
    """Cheap sanity check (length + engine accepts a mirror start) in the parent."""
    if len(deck) != 60:
        print(f"SKIP {name}: {len(deck)} cards (need 60)")
        return False
    sys.path.insert(0, _ROOT)
    from cg.game import battle_start, battle_finish
    try:
        obs, _ = battle_start(deck, deck)
        battle_finish()
        if obs is None:
            print(f"SKIP {name}: engine refused deck (illegal?)")
            return False
        return True
    except Exception as e:
        print(f"SKIP {name}: engine error {e!r}")
        return False


CANDIDATES = ["starmie", "lucario_praxel", "crustle", "dragapult", "dunsparce"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "decks"))
    ap.add_argument("--games", type=int, default=16, help="games per ordered pair")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--decks", nargs="*", default=CANDIDATES,
                    help="deck names (csv stem) to include")
    args = ap.parse_args()

    decks = {}
    for name in args.decks:
        path = os.path.join(args.decks_dir, f"{name}.csv")
        if not os.path.exists(path):
            print(f"SKIP {name}: {path} missing")
            continue
        d = _read_deck(path)
        if _valid(name, d):
            decks[name] = d
    names = list(decks)
    print(f"\nvalid decks ({len(names)}): {names}")
    if len(names) < 2:
        print("need >=2 valid decks")
        return

    # Build the job list: every ordered pair, N games each.
    jobs = []
    for a in names:
        for b in names:
            if a == b:
                continue
            for _ in range(args.games):
                jobs.append((a, decks[a], b, decks[b], args.max_steps))
    print(f"total games: {len(jobs)}  (workers={args.workers})\n")

    wins = {n: 0 for n in names}
    losses = {n: 0 for n in names}
    draws = {n: 0 for n in names}
    errors = {n: 0 for n in names}
    games = {n: 0 for n in names}
    grid = {(a, b): 0 for a in names for b in names}  # grid[(a,b)] = A's wins as p0 vs B

    t0 = time.time()
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(processes=args.workers) as pool:
        for (na, nb, res) in pool.imap_unordered(_play_one, jobs, chunksize=1):
            done += 1
            if res == -1:
                errors[na] += 1
                errors[nb] += 1
            elif res == 2:
                draws[na] += 1
                draws[nb] += 1
                games[na] += 1
                games[nb] += 1
            else:
                games[na] += 1
                games[nb] += 1
                if res == 0:
                    wins[na] += 1
                    losses[nb] += 1
                    grid[(na, nb)] += 1
                else:
                    wins[nb] += 1
                    losses[na] += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  [{done:4d}/{len(jobs)}] {time.time()-t0:6.1f}s", flush=True)

    dt = time.time() - t0
    print(f"\n=== ranked deck win-rate (scorer pilot, {args.games}/ordered-pair) ===")
    print(f"{'deck':18s} {'wins':>5s} {'loss':>5s} {'draw':>5s} {'games':>6s} {'winrate':>8s} {'err':>4s}")

    def wr(n):
        return wins[n] / max(1, games[n])

    for n in sorted(names, key=wr, reverse=True):
        print(f"{n:18s} {wins[n]:5d} {losses[n]:5d} {draws[n]:5d} {games[n]:6d} "
              f"{wr(n):8.1%} {errors[n]:4d}")

    print("\n=== win grid (row deck as p0 wins vs col deck as p1) ===")
    print("            " + "".join(f"{b[:10]:>11s}" for b in names))
    for a in names:
        row = "".join(f"{grid[(a,b)]:>11d}" if a != b else f"{'-':>11s}" for b in names)
        print(f"{a[:11]:11s} {row}")

    best = max(names, key=wr)
    print(f"\n=== RECOMMENDATION: {best} (win-rate {wr(best):.1%}) ===")
    print(f"time={dt:.1f}s over {len(jobs)} games ({dt/max(1,len(jobs))*1000:.0f} ms/game)")


if __name__ == "__main__":
    main()

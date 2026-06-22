"""Head-to-head: the IMPROVED Mega-Lucario-aware scorer vs the CURRENT (git HEAD) scorer.

Both pilot data/decks/lucario_praxel.csv; seats alternate each game so neither side gets a
permanent first/second-player edge. The "current" baseline is loaded from `git show HEAD:agent/
scorer.py` so we compare against the committed generic scorer without a stash.

Also runs a STRICT no-regression check: on data/decks/dragapult.csv (generic path) and
data/decks/crustle.csv (Crustle path), the improved scorer must return *byte-identical* selections
to the HEAD scorer for every decision of a real game — i.e. the new Lucario branch must be inert on
those decks.

Run:  ./scripts/run.sh -m tools.validate_lucario --games 40
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402
from scorer import best_options as improved_best  # noqa: E402  (the edited scorer)


def _load_baseline_best():
    """Materialize the committed (HEAD) scorer as a standalone module and return its best_options."""
    src = subprocess.check_output(["git", "-C", _ROOT, "show", "HEAD:agent/scorer.py"]).decode()
    mod = types.ModuleType("scorer_baseline")
    mod.__file__ = os.path.join(_ROOT, "agent", "scorer_baseline.py")
    sys.modules["scorer_baseline"] = mod
    exec(compile(src, "scorer_baseline.py", "exec"), mod.__dict__)
    return mod.best_options


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _agent(best, deck):
    def a(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        return best(obs_dict)
    return a


def play_game(a0, d0, a1, d1, max_steps=6000):
    """Returns winner index (0/1), or 2 for draw/unfinished."""
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
            if oc.select is None:
                battle_finish()
                return 2
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


def regression_identical(deck_path, baseline_best, games=6):
    """Play a self-play game with the BASELINE scorer; at every decision also run the IMPROVED
    scorer on the SAME obs and assert the selection is byte-identical. Confirms the Lucario branch
    is inert on a non-Lucario deck (generic path on dragapult, Crustle path on crustle)."""
    deck = _read_deck(deck_path)
    base = _agent(baseline_best, deck)
    decisions = mismatches = decided = 0
    first_mismatch = None
    for g in range(games):
        try:
            obs, _ = battle_start(deck, deck)
            if obs is None:
                continue
            for _ in range(6000):
                oc = to_observation_class(obs)
                res = oc.current.result if oc.current is not None else -1
                if res is not None and res >= 0:
                    decided += 1
                    battle_finish()
                    break
                if oc.select is None:
                    battle_finish()
                    break
                sel_base = base(obs)
                if obs.get("select") is not None:
                    sel_imp = improved_best(obs)
                    decisions += 1
                    if list(sel_imp) != list(sel_base):
                        mismatches += 1
                        if first_mismatch is None:
                            first_mismatch = (sel_base, sel_imp)
                obs = battle_select(sel_base)
        except Exception:
            try:
                battle_finish()
            except Exception:
                pass
    return decisions, mismatches, decided, games, first_mismatch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data", "decks", "lucario_praxel.csv"))
    args = ap.parse_args()

    deck = _read_deck(args.deck)
    baseline_best = _load_baseline_best()
    improved = _agent(improved_best, deck)
    current = _agent(baseline_best, deck)

    w = l = d = 0
    t0 = time.time()
    for g in range(args.games):
        if g % 2 == 0:
            res = play_game(improved, deck, current, deck)
            improved_seat = 0
        else:
            res = play_game(current, deck, improved, deck)
            improved_seat = 1
        if res == 2:
            d += 1
        elif res == improved_seat:
            w += 1
        else:
            l += 1
        wr = 100.0 * (w + 0.5 * d) / (g + 1)
        print(f"[{g+1:3d}/{args.games}] tuned W{w} L{l} D{d}  winrate={wr:5.1f}%  "
              f"({time.time()-t0:5.1f}s)", flush=True)

    wr = 100.0 * (w + 0.5 * d) / max(1, args.games)
    print(f"\n=== tuned-Lucario vs generic-Lucario: W{w} L{l} D{d}  "
          f"tuned winrate = {wr:.1f}% over {args.games} games ===")

    print("\n--- no-regression (improved must == HEAD selection on non-Lucario decks) ---")
    for name in ("dragapult", "crustle"):
        path = os.path.join(_ROOT, "data", "decks", f"{name}.csv")
        dec, mm, decided, tot, fm = regression_identical(path, baseline_best)
        status = "IDENTICAL" if mm == 0 else f"MISMATCH({fm})"
        print(f"{name:10s}: {dec} decisions, {mm} mismatches -> {status}  "
              f"({decided}/{tot} games reached a clean result)")


if __name__ == "__main__":
    main()

"""Head-to-head: the Dunsparce-aware scorer vs the SAME scorer with the Dunsparce specialist disabled.

Both pilot data/decks/dunsparce.csv (Alakazam "Powerful Hand" / Dudunsparce draw-combo); seats
alternate each game so neither side gets a permanent first/second-player edge. The "generic" baseline
is just `scorer.best_options` with the module's `_dunsparce` hook temporarily set to None — i.e.
byte-for-byte the generic scorer path. This isolates the specialist from other specialists / edits.

No-regression: on data/decks/crustle.csv and data/decks/lucario_praxel.csv the Dunsparce hook never
fires (no Abra/Kadabra/Alakazam or Dunsparce/Dudunsparce on our side), so enabling vs disabling it
must yield IDENTICAL selections on every decision of a replayed game. We assert exactly that and
report the mismatch count (expect 0).

Run:  ./scripts/run.sh -m tools.validate_dunsparce --games 40
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


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def tuned_best(obs_dict):
    return scorer.best_options(obs_dict)


def generic_best(obs_dict):
    """best_options with the Dunsparce specialist disabled -> the generic scorer path."""
    saved = scorer._dunsparce
    scorer._dunsparce = None
    try:
        return scorer.best_options(obs_dict)
    finally:
        scorer._dunsparce = saved


def _agent(best, deck):
    def a(obs_dict):
        if obs_dict.get("select") is None:
            return deck
        return best(obs_dict)
    return a


def play_game(a0, d0, a1, d1, max_steps=6000):
    """Returns winner index (0/1), or 2 for draw/unfinished."""
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


def regression_check(deck_path, games=4, max_steps=6000):
    """Replay self-play games; at every decision compare tuned vs generic best_options. The Dunsparce
    hook must not fire on this deck, so selections must be identical. Returns (mismatches, decisions).
    """
    deck = _read_deck(deck_path)
    agent = _agent(tuned_best, deck)
    mism = 0
    decisions = 0
    for _ in range(games):
        try:
            obs, _s = battle_start(deck, deck)
            if obs is None:
                continue
            for _ in range(max_steps):
                oc = to_observation_class(obs)
                res = oc.current.result if oc.current is not None else -1
                if res is not None and res >= 0:
                    break
                if oc.select is None:
                    break
                sel_tuned = tuned_best(obs)
                sel_generic = generic_best(obs)
                decisions += 1
                if list(sel_tuned) != list(sel_generic):
                    mism += 1
                obs = battle_select(agent(obs))
            battle_finish()
        except Exception:
            try:
                battle_finish()
            except Exception:
                pass
    return mism, decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data", "decks", "dunsparce.csv"))
    args = ap.parse_args()

    deck = _read_deck(args.deck)
    tuned = _agent(tuned_best, deck)
    generic = _agent(generic_best, deck)

    w = l = d = 0
    t0 = time.time()
    for g in range(args.games):
        if g % 2 == 0:
            res = play_game(tuned, deck, generic, deck)
            tuned_seat = 0
        else:
            res = play_game(generic, deck, tuned, deck)
            tuned_seat = 1
        if res == 2:
            d += 1
        elif res == tuned_seat:
            w += 1
        else:
            l += 1
        wr = 100.0 * (w + 0.5 * d) / (g + 1)
        print(f"[{g+1:3d}/{args.games}] tuned W{w} L{l} D{d}  winrate={wr:5.1f}%  "
              f"({time.time()-t0:5.1f}s)", flush=True)

    wr = 100.0 * (w + 0.5 * d) / max(1, args.games)
    print(f"\n=== tuned-Dunsparce vs generic-Dunsparce: W{w} L{l} D{d}  "
          f"tuned winrate = {wr:.1f}% over {args.games} games ===")

    print("\n--- no-regression: identical selections off-archetype (Dunsparce hook must not fire) ---")
    for name in ("crustle.csv", "lucario_praxel.csv"):
        try:
            mism, dec = regression_check(os.path.join(_ROOT, "data", "decks", name))
            status = "OK" if mism == 0 else f"REGRESSION ({mism} differ)"
            print(f"{name:18s}: {mism} mismatches / {dec} decisions  [{status}]")
        except Exception as e:
            print(f"{name:18s}: ERROR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

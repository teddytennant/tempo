"""Does answering YES to "would you like to go first?" actually win more games in THIS engine?

SelectContext.IS_FIRST (41) is asked once per game, to whichever player wins the opening flip.
It is the single highest-leverage tempo decision available: one bit, decided before any card is
played. The repo disagrees with itself about it —

  agent/scorer.py     _score_sub: NO  +100   ("going second is often better for a setup deck")
  agent/lucario_rules.py score_sub: YES +150 ("aggro wants the Riolu->Mega clock a turn sooner")
  agent/main.py       fallback  : YES

— and the scorer wins, so we answer NO in 100% of real positions while 91 of 93 real ladder
Lucario players answer YES.

This measures the choice causally instead of arguing about it: mirror games, identical deck and
identical policy on both seats, with ONLY the IS_FIRST answer forced (YES on even seeds, NO on odd
seeds). Reports the win rate of the player who was asked, split by what they were made to answer.
Any first-player advantage in the engine shows up as a gap between the two rows.

  ./scripts/run.sh -m tools.first_turn_ab --src experiments/luc_majkel_v2_src --games 200
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from collections import Counter
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IS_FIRST = 41
YES = 1
NO = 2


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _play_one(task):
    src, deck_a, deck_b, force_yes, max_steps = task
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    c = Counter()
    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class
        import agent.main as M
    except Exception:
        c["import_fail"] += 1
        return c, traceback.format_exc()[-400:]

    asked = None
    try:
        obs, _ = battle_start(deck_a, deck_b)
        if obs is None:
            c["start_refused"] += 1
            return c, ""
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            if oc.current is not None and oc.current.result is not None and oc.current.result >= 0:
                break
            sel = obs.get("select")
            if sel is None:
                break
            opts = sel.get("option") or []

            if sel.get("context") == IS_FIRST and asked is None:
                asked = oc.current.yourIndex
                want = YES if force_yes else NO
                pick = [i for i, o in enumerate(opts) if o.get("type") == want][:1]
                if not pick:
                    c["no_such_option"] += 1
                    pick = [0]
            else:
                try:
                    pick = M.agent(obs)
                except Exception:
                    pick = [0] if opts else []
                if not isinstance(pick, list):
                    pick = [0] if opts else []
            try:
                obs = battle_select(pick)
            except Exception:
                try:
                    obs = battle_select([0] if opts else [])
                except Exception:
                    c["stuck"] += 1
                    break

        oc = to_observation_class(obs)
        res = oc.current.result if oc.current is not None else None
        try:
            battle_finish()
        except Exception:
            pass
    except Exception:
        c["game_exc"] += 1
        return c, traceback.format_exc()[-400:]

    arm = "YES(first)" if force_yes else "NO(second)"
    if asked is None:
        c[f"{arm}/never_asked"] += 1
        return c, ""
    if res is None or res < 0:
        c[f"{arm}/undecided"] += 1
        return c, ""
    # result is the winning player index (2 == draw in this engine's encoding is not used here)
    c[f"{arm}/games"] += 1
    if res == asked:
        c[f"{arm}/wins"] += 1
    return c, ""


def _ci(w, n):
    if not n:
        return 0.0, 0.0
    p = w / n
    return 100.0 * p, 100.0 * 1.96 * (p * (1 - p) / n) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--deck", default="")
    ap.add_argument("--opp-deck", default="")
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=4000)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    deck_path = a.deck
    if not deck_path:
        for cand in (os.path.join(src, "deck.csv"), os.path.join(src, "agent", "deck.csv"),
                     os.path.join(_ROOT, "agent", "deck.csv")):
            if os.path.exists(cand):
                deck_path = cand
                break
    deck = _read_deck(deck_path)
    opp = _read_deck(a.opp_deck) if a.opp_deck else deck
    print(f"src={src}\ndeck={deck_path}\nopp={a.opp_deck or deck_path}")

    tasks = []
    for g in range(a.games):
        # seat-swap as well as arm-swap so a raw seat bias cannot masquerade as the effect
        da, db = (deck, opp) if (g // 2) % 2 == 0 else (opp, deck)
        tasks.append((src, da, db, g % 2 == 0, a.max_steps))

    ctx = get_context("spawn")
    agg = Counter()
    fails = []
    with ctx.Pool(a.workers) as pool:
        for c, f in pool.imap_unordered(_play_one, tasks):
            agg.update(c)
            if f:
                fails.append(f)

    print(f"\n{'answer':<14} {'n':>6} {'wins':>6} {'winrate of the ASKED player':>30}")
    for arm in ("YES(first)", "NO(second)"):
        n, w = agg[f"{arm}/games"], agg[f"{arm}/wins"]
        p, ci = _ci(w, n)
        print(f"{arm:<14} {n:>6} {w:>6}      {p:>6.1f}% +/- {ci:.1f}")
    for k in sorted(agg):
        if not k.endswith("/games") and not k.endswith("/wins"):
            print(f"  [{k}] {agg[k]}")
    if fails:
        print(f"\n{len(fails)} failures, first:\n{fails[0]}")


if __name__ == "__main__":
    main()

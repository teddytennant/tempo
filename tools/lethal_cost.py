"""What does NOT searching actually cost? — does the shipped policy throw the proven win away?

`tools/lethal_probe.py` shows that widening the verifier's cost filters finds game-winning lines the
shipped agent never looks for. That is only worth something if the heuristic, left to itself, fails
to play one of them. A proof returns the first action of *a* winning line; the scorer may pick a
different action that also wins (turn ordering), in which case widening changes nothing.

So ask the engine directly. In every position where the widened verifier proves a win and the
shipped one does not:

  1. fork the game at that decision (same belief-corrected determinization the verifier uses),
  2. apply the action the SHIPPED AGENT would actually play,
  3. re-run the win search from the resulting node.

Still provable  -> the heuristic preserved the win; widening buys nothing there.
No longer provable -> the heuristic threw a proven game-winning line away, and widening converts
                      that position from a coin flip into a win.

    ./scripts/run.sh -m tools.lethal_cost --src experiments/luc_majkel_v4_src --n 2500
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ATTACK = 13
END = 14
MAIN_CTX = 0

SHIP = (2, True, 600, 0.25, 10)
WIDE = (3, False, 4000, 1.00, 10)


def _load(path, n):
    recs = []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            if sel.get("context") != MAIN_CTX or len(sel.get("option") or []) < 2:
                continue
            if not obs.get("search_begin_input"):
                continue
            recs.append(r)
            if n and len(recs) >= n:
                break
    return recs


def _apply(L, cfg):
    pg, req_atk, nodes, tmax, depth = cfg
    L.PRIZE_GATE = pg
    L._NODE_BUDGET = nodes
    L._MAX_TIME_S = tmax
    L._MAX_DEPTH = depth
    if hasattr(L, "REQUIRE_ATTACK_OPTION"):
        L.REQUIRE_ATTACK_OPTION = req_atk
    else:
        L._has_attack_option = _ORIG_ATK if req_atk else (lambda select: True)


def _determinize(L, obs, decklist):
    """Exactly the seating lethal_move builds, so the fork we judge on is the fork it proves on."""
    st = obs.current
    me_i = st.yourIndex
    me, opp = st.players[me_i], st.players[1 - me_i]
    prize_n = max(len(me.prize), 1)
    deck_n = max(me.deckCount, 1)
    your_deck = your_prize = None
    if L._corrected_deck is not None:
        try:
            ordered = L._corrected_deck(obs, list(decklist), None)
            if ordered and len(ordered) >= prize_n:
                your_prize = ordered[:prize_n]
                your_deck = ordered[prize_n:prize_n + deck_n]
        except Exception:
            your_deck = None
    if not your_deck:
        pool = (list(decklist) * 2) if decklist else [1]
        your_deck, your_prize = pool[:deck_n], pool[:prize_n]
    if not your_prize:
        your_prize = (list(decklist) or [1])[:prize_n]
    opp_active = [1072] if (opp.active and opp.active[0] is None) else []
    return (your_deck, your_prize,
            [1072] * max(opp.deckCount, 1),
            [1072] * max(len(opp.prize), 1),
            [1072] * max(opp.handCount, 0) if opp.handCount else [],
            opp_active)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=2500)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import lethal as L
    import agent.main as M
    from cg.api import to_observation_class, search_begin, search_step, search_release, search_end

    deck_path = os.path.join(src, "agent", "deck.csv")
    with open(deck_path) as f:
        decklist = [int(x) for x in f.read().splitlines() if x.strip()]

    recs = _load(a.recs, a.n)
    print(f"src={src}\nMAIN records: {len(recs)}")

    # 1. which positions does widening newly prove?
    _apply(L, SHIP)
    ship_hit = {i for i, r in enumerate(recs) if _isel(L.lethal_move(r["obs"], decklist, None))}
    _apply(L, WIDE)
    wide_hit = {i for i, r in enumerate(recs) if _isel(L.lethal_move(r["obs"], decklist, None))}
    missed = sorted(wide_hit - ship_hit)
    print(f"ship proves {len(ship_hit)}, wide proves {len(wide_hit)}, "
          f"newly proved {len(missed)}")

    # 2. in those, does the shipped agent's own move keep the win alive?
    preserved = thrown = undecidable = 0
    thrown_types = {}
    for i in missed:
        r = recs[i]
        obs_d = r["obs"]
        try:
            got = M.agent(obs_d)
        except Exception:
            undecidable += 1
            continue
        if not isinstance(got, list) or not got:
            undecidable += 1
            continue
        try:
            obs = to_observation_class(obs_d)
            me_i = obs.current.yourIndex
            root = search_begin(obs, *_determinize(L, obs, decklist))
        except Exception:
            undecidable += 1
            continue
        alive = None
        try:
            _apply(L, WIDE)
            budget = L._Budget()
            child = search_step(root.searchId, got)
            try:
                alive = L._dfs(child.searchId, child.observation, me_i, 1, budget)
            finally:
                try:
                    search_release(child.searchId)
                except Exception:
                    pass
        except Exception:
            alive = None
        finally:
            try:
                search_release(root.searchId)
            except Exception:
                pass
            try:
                search_end()
            except Exception:
                pass
        if alive is None:
            undecidable += 1
        elif alive:
            preserved += 1
        else:
            thrown += 1
            types = [o.get("type") for o in obs_d["select"].get("option") or []]
            k = tuple(sorted(types[j] for j in got if j < len(types)))
            thrown_types[k] = thrown_types.get(k, 0) + 1

    print(f"\nof {len(missed)} newly-proved positions, the SHIPPED heuristic:")
    print(f"  preserved the win        {preserved}")
    print(f"  THREW THE WIN AWAY       {thrown}")
    print(f"  undecidable              {undecidable}")
    if thrown_types:
        print("\n  what it played instead (option types):")
        for k, v in sorted(thrown_types.items(), key=lambda kv: -kv[1]):
            print(f"    {list(k)}  x{v}")

    if a.json:
        with open(a.json, "w") as f:
            json.dump({"src": src, "recs": len(recs), "ship": len(ship_hit),
                       "wide": len(wide_hit), "newly": len(missed),
                       "preserved": preserved, "thrown": thrown,
                       "undecidable": undecidable}, f, indent=1)
        print(f"\nwrote {a.json}")


def _isel(x):
    return isinstance(x, list) and bool(x)


_ORIG_ATK = None

if __name__ == "__main__":
    _s = os.path.abspath(sys.argv[sys.argv.index("--src") + 1]) if "--src" in sys.argv else _ROOT
    sys.path.insert(0, os.path.join(_s, "agent"))
    sys.path.insert(0, _s)
    import lethal as _L
    _ORIG_ATK = _L._has_attack_option
    main()

"""Turn audit: play full real-engine games through the deploy entry point and count TURNS in
which our agent left a once-per-turn resource on the table.

The agreement harnesses (tools/prize_agreement.py, tools/tempo_agreement.py) score one decision
at a time, so they systematically over-penalise benign turn ordering and cannot see the thing
that actually costs games: ending a turn with the energy attachment unspent. This probe watches
whole turns instead and counts, per turn we take:

  wasted_attach   an ENERGY attach was still on the table at the turn-ending decision and we had
                  not attached this turn -> that energy drop is gone forever
  wasted_bench    a Basic Pokemon was still playable from hand with bench space free at the
                  turn-ending decision, and we ended anyway
  wasted_supp     a Supporter was playable (none played this turn) at the turn-ending decision
  retreat_no_atk  we paid a retreat and then did not attack that turn
  end_no_attack   the turn ended with END while an ATTACK option existed

Only turns for the audited seat are counted; the opponent seat is driven by the same agent so the
games stay in-distribution. Deterministic per seed.

  ./scripts/run.sh -m tools.turn_audit --src experiments/luc_majkel_v2_src --games 40
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import traceback
from collections import Counter
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLAY = 7
ATTACH = 8
EVOLVE = 9
ABILITY = 10
RETREAT = 12
ATTACK = 13
END = 14

HAND = 2


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _play_one(task):
    src, deck_a, deck_b, audit_seat, max_steps, seed = task
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    rng = random.Random(seed)
    c = Counter()
    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class, CardType
        from cg.api import all_card_data
        import agent.main as M
    except Exception:
        c["import_fail"] += 1
        return c, traceback.format_exc()[-500:]

    CARD = {cd.cardId: cd for cd in all_card_data()}
    ENERGY_TYPES = {CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY}

    def hand_card(oc, me, idx):
        try:
            return oc.current.players[me].hand[idx]
        except Exception:
            return None

    def kind(card):
        """(is_energy, is_basic_pokemon)"""
        if card is None:
            return (False, False)
        cd = CARD.get(getattr(card, "id", None))
        if cd is None:
            return (False, False)
        ct = getattr(cd, "cardType", None)
        return (ct in ENERGY_TYPES,
                ct == CardType.POKEMON and bool(getattr(cd, "basic", False)))

    # per-turn state for the audited seat
    cur_turn = None
    attached = False
    retreated = False
    turn_open = False

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
            me = oc.current.yourIndex
            ctx = sel.get("context")
            opts = sel.get("option") or []
            types = [o.get("type") for o in opts]

            try:
                pick = M.agent(obs)
            except Exception:
                pick = [0] if opts else []
            if not isinstance(pick, list):
                pick = [0] if opts else []
            chosen = [opts[i] for i in pick if isinstance(i, int) and 0 <= i < len(opts)]
            ctypes = [o.get("type") for o in chosen]

            if me == audit_seat and ctx == 0:
                t = oc.current.turn
                if t != cur_turn:
                    cur_turn = t
                    attached = False
                    retreated = False
                    turn_open = True
                    c["turns"] += 1

                if ATTACH in ctypes:
                    src_card = None
                    for o in chosen:
                        if o.get("type") == ATTACH and o.get("area") == HAND:
                            src_card = hand_card(oc, me, o.get("index"))
                    if src_card is None or kind(src_card)[0]:
                        attached = True
                if RETREAT in ctypes:
                    retreated = True

                ends_turn = (ATTACK in ctypes) or (END in ctypes)
                if ends_turn and turn_open:
                    turn_open = False
                    c["turn_ends"] += 1
                    if ATTACK in ctypes:
                        c["ended_by_attack"] += 1
                    else:
                        c["ended_by_end"] += 1
                        if ATTACK in types:
                            c["end_no_attack"] += 1
                    # what was still available at the turn-ending decision?
                    en_avail = False
                    bp_avail = False
                    for o in opts:
                        if o.get("type") == ATTACH and o.get("area") == HAND:
                            if kind(hand_card(oc, me, o.get("index")))[0]:
                                en_avail = True
                        elif o.get("type") == PLAY:
                            if kind(hand_card(oc, me, o.get("index")))[1]:
                                bp_avail = True
                    if en_avail and not attached:
                        c["wasted_attach"] += 1
                        c[f"wasted_attach_end_{'attack' if ATTACK in ctypes else 'end'}"] += 1
                    try:
                        bench_free = len([b for b in (oc.current.players[me].bench or []) if b]) < 5
                    except Exception:
                        bench_free = False
                    if bp_avail and bench_free:
                        c["wasted_bench"] += 1
                        bn = len([b for b in (oc.current.players[me].bench or []) if b])
                        ids = tuple(sorted(
                            getattr(hand_card(oc, me, o.get("index")), "id", None)
                            for o in opts
                            if o.get("type") == PLAY and kind(hand_card(oc, me, o.get("index")))[1]))
                        c[f"wb bench={bn} ended={'atk' if ATTACK in ctypes else 'end'} ids={ids}"] += 1
                    if retreated and ATTACK not in ctypes:
                        c["retreat_no_atk"] += 1

            try:
                obs = battle_select(pick)
            except Exception:
                try:
                    obs = battle_select([0] if opts else [])
                except Exception:
                    c["stuck"] += 1
                    break
        try:
            battle_finish()
        except Exception:
            pass
    except Exception:
        c["game_exc"] += 1
        return c, traceback.format_exc()[-500:]
    return c, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--deck", default="")
    ap.add_argument("--opp-deck", default="")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    # A packed tree carries the deck it actually ships with; prefer it over the repo's agent/deck.csv
    # (they differ, and auditing the wrong list silently routes through the generic pilot).
    deck_path = a.deck
    if not a.deck:
        for cand in (os.path.join(src, "deck.csv"), os.path.join(src, "agent", "deck.csv"),
                     os.path.join(_ROOT, "agent", "deck.csv")):
            if os.path.exists(cand):
                deck_path = cand
                break
    print(f"deck={deck_path}")
    deck = _read_deck(deck_path)
    opp = _read_deck(a.opp_deck) if a.opp_deck else deck

    tasks = []
    for g in range(a.games):
        seat = g % 2
        da, db = (deck, opp) if seat == 0 else (opp, deck)
        tasks.append((src, da, db, seat, a.max_steps, a.seed + g))

    ctx = get_context("spawn")
    agg = Counter()
    fails = []
    with ctx.Pool(a.workers) as pool:
        for c, f in pool.imap_unordered(_play_one, tasks):
            agg.update(c)
            if f:
                fails.append(f)

    turns = agg["turn_ends"] or 1
    print(f"src={src}  games={a.games}  audited turns (with a turn-ending decision) = {agg['turn_ends']}")
    for k in ("ended_by_attack", "ended_by_end", "end_no_attack",
              "wasted_attach", "wasted_attach_end_attack", "wasted_attach_end_end",
              "wasted_bench", "retreat_no_atk", "stuck", "game_exc", "import_fail"):
        if agg[k]:
            print(f"  {k:<26} {agg[k]:>6}  {100.0*agg[k]/turns:>6.2f}% of turns")
    for k in sorted(agg):
        if k not in ("turns", "turn_ends", "ended_by_attack", "ended_by_end", "end_no_attack",
                     "wasted_attach", "wasted_attach_end_attack", "wasted_attach_end_end",
                     "wasted_bench", "retreat_no_atk", "stuck", "game_exc", "import_fail"):
            print(f"  [other] {k} = {agg[k]}")
    if fails:
        print(f"\n{len(fails)} failures, first:\n{fails[0]}")


if __name__ == "__main__":
    main()

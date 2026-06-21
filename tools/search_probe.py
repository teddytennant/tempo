"""Empirically probe the engine's native search API (search_begin/search_step).

Goal: confirm we can (1) begin a search from a real agent observation with a sampled
determinization, (2) step through hypothetical selections, and (3) roll out to a terminal result.
This de-risks the MCTS design (docs/plans/02-forward-model.md) before we build it.

Run: ./scripts/run.sh -m tools.search_probe
"""
from __future__ import annotations

import os
import random
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from cg.api import all_card_data, to_observation_class, search_begin, search_step, search_release, search_end  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402

CARDS = {c.cardId: c for c in all_card_data()}


def read_deck():
    with open(os.path.join(_ROOT, "agent", "deck.csv")) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def a_basic_pokemon(deck):
    for cid in deck:
        c = CARDS.get(cid)
        if c is not None and c.cardType == 0 and getattr(c, "basic", False):
            return cid
    return deck[0]


def random_select(obs):
    n = len(obs.select.option)
    k = obs.select.maxCount
    return random.sample(range(n), min(k, n)) if k and n else []


def determinize(obs, deck):
    """Build a minimally-valid determinization from a real observation."""
    st = obs.current
    yi = st.yourIndex
    me = st.players[yi]
    opp = st.players[1 - yi]
    pool = deck  # any valid card IDs from our known card universe
    your_deck = (pool * 2)[: max(me.deckCount, 0)]
    your_prize = (pool * 2)[: len(me.prize)]
    opp_deck = (pool * 2)[: max(opp.deckCount, 0)]
    opp_prize = (pool * 2)[: len(opp.prize)]
    opp_hand = (pool * 2)[: max(opp.handCount, 0)]
    # opp_active only needed if their active is face-down (None)
    opp_active = []
    if opp.active and opp.active[0] is None:
        opp_active = [a_basic_pokemon(deck)]
    return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active


def main():
    random.seed(0)
    deck = read_deck()
    obs_dict, _ = battle_start(deck, deck)

    # Advance to a mid-game MAIN decision (turn >= 3) so the board is developed.
    for _ in range(400):
        obs = to_observation_class(obs_dict)
        if obs.current is not None and obs.current.result != -1:
            print("game ended before probe; retrying not implemented"); battle_finish(); return
        if obs.select is None:
            break
        if obs.current is not None and obs.current.turn >= 3 and obs.select.context == 0:  # MAIN
            break
        obs_dict = battle_select(random_select(obs))

    obs = to_observation_class(obs_dict)
    print(f"probe point: turn={obs.current.turn} ctx={obs.select.context} "
          f"options={len(obs.select.option)} sbi={'yes' if obs.search_begin_input else 'NO'}")

    det = determinize(obs, deck)
    print(f"determinization sizes: your_deck={len(det[0])} your_prize={len(det[1])} "
          f"opp_deck={len(det[2])} opp_prize={len(det[3])} opp_hand={len(det[4])} opp_active={len(det[5])}")

    root = search_begin(obs, *det)
    print(f"search_begin OK -> searchId={root.searchId} "
          f"root options={len(root.observation.select.option)}")

    # Roll out one random line to terminal inside the search.
    cur = root
    steps = 0
    for _ in range(2000):
        o = cur.observation
        if o.current is not None and o.current.result != -1:
            print(f"ROLLOUT reached terminal in {steps} steps -> result={o.current.result}")
            break
        if o.select is None:
            print(f"rollout hit None select after {steps} steps"); break
        sel = random_select(o)
        cur = search_step(cur.searchId, sel)
        steps += 1
    else:
        print(f"rollout did not terminate in 2000 steps (last result={cur.observation.current.result})")

    # Branch check: step the ROOT again with a different option -> distinct searchId?
    if len(root.observation.select.option) > 1:
        b = search_step(root.searchId, [min(1, len(root.observation.select.option) - 1)])
        print(f"branch from root: new searchId={b.searchId} (root still {root.searchId}) "
              f"-> {'DISTINCT (persistent tree)' if b.searchId != root.searchId else 'same id'}")

    search_release(root.searchId)
    search_end()
    battle_finish()
    print("PROBE COMPLETE — native search usable for MCTS" )


if __name__ == "__main__":
    main()

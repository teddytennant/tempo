"""Belief-corrected determinization for the search.

Subtracts every card we can see (hand, board, pre-evolutions, attached energy, tools, discard, our
stadium) from the static decklist to get the true hidden pool, then orders it [prized..., deck...]
using PrizeTracker's inference. engine_rs slices this non-overlapping (first prize_count = prizes,
next deck_count = draw pile), so the search only explores reproducible lines.
"""
from collections import Counter


def corrected_deck(obs, decklist, prized_counter=None):
    yi = obs.current.yourIndex
    p = obs.current.players[yi]
    remaining = Counter(decklist)

    def sub(card):
        if card is not None:
            remaining[card.id] -= 1

    for c in p.hand or []:
        sub(c)
    for pk in (list(p.active or []) + list(p.bench or [])):
        if pk is None:
            continue
        sub(pk)
        for c in getattr(pk, "preEvolution", None) or []:
            sub(c)
        for c in getattr(pk, "energyCards", None) or []:
            sub(c)
        for c in getattr(pk, "tools", None) or []:
            sub(c)
    for c in p.discard or []:
        sub(c)
    for c in obs.current.stadium or []:
        if c is not None and getattr(c, "playerIndex", None) == yi:
            remaining[c.id] -= 1

    hidden = Counter({cid: cnt for cid, cnt in remaining.items() if cnt > 0})
    prize_n = len(p.prize)

    if prized_counter is not None:
        prized = list(prized_counter.elements())[:prize_n]
        deckpool = hidden.copy()
        deckpool.subtract(Counter(prized))
        deck_cards = [cid for cid, cnt in deckpool.items() for _ in range(max(0, cnt))]
        ordered = prized + deck_cards
    else:
        # Unknown prizes: still send the visible-subtracted hidden pool (engine splits the front
        # prize_count off as prizes). Far better than the old "first N of the full decklist".
        ordered = list(hidden.elements())

    return ordered

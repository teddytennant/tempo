"""Independent opponent: the Day-1 #1 "Crustle wall" bot (dashimaki360, ~1140 LB).

Faithful port of the published notebook
  dashimaki360__beating-the-day-1-1-crustle-bot
to tempo's `cg.api`. The notebook was already written against this exact engine,
so the scoring logic below is a *verbatim* reproduction of its `agent()` — only
the deck-loading was rewired to read this bot's own decklist (deck_crustle.csv).

This is a genuinely independent policy: it does NOT call tempo's scorer. Its whole
brain is a fixed priority order on the MAIN turn (do all setup, attack last) plus a
handful of card-id special cases, and a "always make a valid choice" rule for every
forced sub-selection.

  ATTACH 1000 > EVOLVE 800 > PLAY 600 > ABILITY 400 > ATTACK 100 > RETREAT -1

Special cases (card ids verified against all_card_data):
  1159 Hero's Cape -> 2100 only onto the Active (never bench)
  1147 Jumbo Ice Cream -> 2000 only when Active is damaged AND has >=3 energy
  1212 Cook -> 1500 only when Active is damaged
  1224 Cheren -> 1400 (draw 3)
  1264 Battle Cage -> 1300 (stadium)
"""
from __future__ import annotations

import os

from cg.api import (
    AreaType, OptionType, SelectContext, Pokemon, Card, to_observation_class,
)

_DECK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_crustle.csv")


def read_deck_csv() -> list[int]:
    with open(_DECK_PATH) as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    return [int(lines[i]) for i in range(60)]


DECK = read_deck_csv()


def get_card(obs, area, index, player_index):
    """Safely extract a Card or Pokemon object from a specific zone."""
    ps = obs.current.players[player_index]
    if area == AreaType.DECK:
        return obs.select.deck[index]
    elif area == AreaType.HAND:
        return ps.hand[index]
    elif area == AreaType.DISCARD:
        return ps.discard[index]
    elif area == AreaType.ACTIVE:
        return ps.active[index]
    elif area == AreaType.BENCH:
        return ps.bench[index]
    elif area == AreaType.PRIZE:
        return ps.prize[index]
    elif area == AreaType.STADIUM:
        return obs.current.stadium[index]
    elif area == AreaType.LOOKING:
        return obs.current.looking[index]
    else:
        return None


def best_options(obs_dict: dict) -> list[int]:
    """A simple rule-based Pokemon TCG agent (dashimaki360 Crustle bot).

    1. Do all your setup first (Attach -> Evolve -> Play -> Ability)
    2. Attack last
    3. Always make a valid choice for any forced sub-selection
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return DECK

    select = obs.select
    options = select.option
    context = select.context

    scores = []
    for o in options:
        score = 0

        if context == SelectContext.MAIN:
            if o.type == OptionType.ATTACH:
                score = 1000
                card = get_card(obs, o.area, o.index, obs.current.yourIndex)
                if card is not None and card.id == 1159:  # Hero's Cape
                    if o.inPlayArea == AreaType.ACTIVE:
                        score = 2100
                    else:
                        score = 0  # never attach it to the bench
            elif o.type == OptionType.EVOLVE:
                score = 800
            elif o.type == OptionType.PLAY:
                score = 600
                card = get_card(obs, AreaType.HAND, o.index, obs.current.yourIndex)
                if card is not None:
                    if card.id == 1147:  # Jumbo Ice Cream: heal if damaged AND 3+ energy
                        active = obs.current.players[obs.current.yourIndex].active
                        if len(active) > 0 and active[0] is not None:
                            pokemon = active[0]
                            if pokemon.hp < pokemon.maxHp and len(pokemon.energies) >= 3:
                                score = 2000
                            else:
                                score = 0
                    elif card.id == 1212:  # Cook: heal if damaged
                        active = obs.current.players[obs.current.yourIndex].active
                        if len(active) > 0 and active[0] is not None:
                            pokemon = active[0]
                            if pokemon.hp < pokemon.maxHp:
                                score = 1500
                            else:
                                score = 0
                    elif card.id == 1224:  # Cheren: draw 3
                        score = 1400
                    elif card.id == 1264:  # Battle Cage: stadium
                        score = 1300
            elif o.type == OptionType.ABILITY:
                score = 400
            elif o.type == OptionType.ATTACK:
                score = 100
            elif o.type == OptionType.RETREAT:
                score = -1

        else:
            score = 2000
            if o.type == OptionType.CARD:
                card = get_card(obs, o.area, o.index, o.playerIndex)
                if card is not None:
                    if context == SelectContext.EVOLVE or context == SelectContext.TO_BENCH:
                        score += 500
                    if isinstance(card, Pokemon):
                        if o.playerIndex != obs.current.yourIndex:
                            score += 500 if o.area == AreaType.ACTIVE else 100
                            score += len(card.energies) * 50
                        else:
                            score += card.hp
            elif o.type == OptionType.YES:
                score += 100
            elif o.type == OptionType.NUMBER:
                score += o.number

        scores.append(score)

    sorted_options = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    output = []
    for i in range(min(len(sorted_options), select.maxCount)):
        idx = sorted_options[i]
        if scores[idx] >= 0 or len(output) < select.minCount:
            output.append(idx)
    return output


# Faithful alias to the notebook's public name.
agent = best_options

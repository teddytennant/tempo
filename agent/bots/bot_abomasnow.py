"""Independent opponent: a Mega Abomasnow ex control/tank deck (kiyotah).

Faithful port of the published notebook
  kiyotah__a-sample-rule-based-agent-mega-abomasnow-ex-deck
to tempo's `cg.api`. The notebook was written against this exact engine, so the
single-function `agent()` scorer below is a *verbatim* reproduction of its
`main.py` — only the deck-loading was rewired to read this bot's own decklist
(deck_abomasnow.csv) and the public entry point was aliased to `best_options`
(with the original `agent` name kept as an alias).

This is a genuinely independent policy and does NOT call tempo's scorer. It is a
new *axis* of opponent next to the existing pool: a control/tank archetype. It
grinds with Mega Abomasnow ex's Hammer-lanche (a high-HP wall that hits for a
big flat number), banks Basic Water Energy into the discard, and snipes with
Kyogre's Riptide (damage scales with discarded Water Energy) once it can KO.
Where Crustle stalls and Dragapult races prizes, this deck out-tanks you.

Card / attack ids verified against all_card_data() / all_attack():
  721 Kyogre, 722 Snover, 723 Mega Abomasnow ex (megaEx), 1121 Ultra Ball,
  1126 Precious Trolley, 1192 Carmine, 1227 Lillie's Determination,
  1262 Surfing Beach (stadium ability), 3 Basic {W} Energy,
  attack 1042 Riptide, attack 1046 Hammer-lanche.

The agent recomputes everything from the observation each call (no per-game
module state), so reset() is a documented no-op kept for the eval harness's
uniform reset hook.
"""
from __future__ import annotations

import os
from collections import defaultdict

from cg.api import (
    AreaType, CardType, Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, to_observation_class,
)

_DECK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_abomasnow.csv")


def read_deck_csv() -> list[int]:
    with open(_DECK_PATH) as f:
        csv = f.read().split("\n")
    return [int(csv[i]) for i in range(60)]


my_deck = read_deck_csv()
DECK = my_deck

# Fetch card metadata database and create an ID-to-Card lookup table
all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

# Decklist
Kyogre = 721  # x2
Snover = 722  # x4
Mega_Abomasnow_ex = 723  # x4
Ultra_Ball = 1121  # x4
Precious_Trolley = 1126  # x1
Carmine = 1192  # x4
Lillie_Determination = 1227  # x4
Surfing_Beach = 1262  # x3
Basic_Water_Energy = 3  # x34


def reset():
    """No-op: this bot keeps no per-game module state (kept for the eval hook)."""
    return None


def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
    """Helper function to safely extract a Card or Pokemon object from specific zones."""
    ps = obs.current.players[player_index]
    try:
        match area:
            case AreaType.DECK:
                return obs.select.deck[index]
            case AreaType.HAND:
                return ps.hand[index]
            case AreaType.DISCARD:
                return ps.discard[index]
            case AreaType.ACTIVE:
                return ps.active[index]
            case AreaType.BENCH:
                return ps.bench[index]
            case AreaType.PRIZE:
                return ps.prize[index]
            case AreaType.STADIUM:
                return obs.current.stadium[index]
            case AreaType.LOOKING:
                return obs.current.looking[index]
            case _:
                return None
    except (TypeError, IndexError):
        # The notebook assumed every option indexed a populated zone; some engine
        # contexts hand back an index into an empty/other zone. Guard the lookup so
        # the bot plays a full game instead of crashing mid-match.
        return None


def _safe_fallback(obs: Observation) -> list[int]:
    """Legal, minimal selection used if the heuristic ever raises mid-game."""
    select = obs.select
    n = len(select.option)
    if select.maxCount == 0 or n == 0:
        return []
    k = max(select.minCount, 1)
    k = min(k, select.maxCount, n)
    return list(range(k))


def agent(obs_dict: dict) -> list[int]:
    """Main Agent Function (verbatim port of the notebook's scorer)."""
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        # In the initial selection, obs.select is None and we return the 60-card deck.
        return my_deck

    state = obs.current
    select = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]

    field_counts = defaultdict(int)  # Cards per id on Bench + Active
    hand_counts = defaultdict(int)   # Cards per id in hand
    discard_counts = defaultdict(int)  # Cards per id in discard

    # A Pokemon ready to attack immediately
    bench_attacker_index0 = -1  # Mega Abomasnow ex
    bench_attacker_index1 = -1  # Kyogre
    for i, card in enumerate(my_state.bench):
        field_counts[card.id] += 1
        if card.id == Mega_Abomasnow_ex and len(card.energies) >= 2:
            bench_attacker_index0 = i
        elif card.id == Kyogre and len(card.energies) >= 1:
            bench_attacker_index1 = i

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    op_active_hp = 0  # Remaining HP of opponent's Active Pokemon
    for card in state.players[1 - my_index].active:
        if card is None:  # During setup
            continue
        op_active_hp = card.hp

    # If opponent HP <= (Basic Water Energy in discard * 20), Kyogre can KO.
    prefer_ky = op_active_hp <= 20 * discard_counts[Basic_Water_Energy]
    switch_index = -1
    for card in my_state.active:
        if card is None:  # During setup
            continue
        field_counts[card.id] += 1
        if card.id == Mega_Abomasnow_ex and len(card.energies) >= 2:
            if prefer_ky and bench_attacker_index1 >= 0:
                switch_index = bench_attacker_index1  # Switching to Kyogre is preferable.
        elif card.id == Kyogre and len(card.energies) >= 1:
            if not prefer_ky and bench_attacker_index0 >= 0:
                switch_index = bench_attacker_index0  # Switch to Mega Abomasnow ex.
        elif bench_attacker_index0 >= 0:
            switch_index = bench_attacker_index0  # Switch to Mega Abomasnow ex.

    # Score every option.
    scores = []
    for o in select.option:
        score = 0
        if o.type == OptionType.NUMBER:
            score = o.number  # e.g. "draw X cards"
        elif o.type == OptionType.YES:
            score = 1  # Prefer "Yes"
        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is not None:
                energy_count = 0
                if isinstance(card, Pokemon):
                    energy_count = len(card.energies)
                if (context == SelectContext.SWITCH
                        or context == SelectContext.TO_ACTIVE
                        or context == SelectContext.SETUP_ACTIVE_POKEMON):
                    # Pokemon to send to the Active Spot
                    score += energy_count * 2  # Prefer Pokemon with Energy.
                    if o.index == switch_index:
                        score += 100
                    if card.id == Mega_Abomasnow_ex:
                        score += 20
                    elif card.id == Kyogre:
                        score += 10
                elif context == SelectContext.TO_BENCH or context == SelectContext.TO_HAND:
                    # Card to Bench or add to hand
                    if card.id == Snover:
                        if field_counts[card.id] >= 1:
                            score += 5
                        elif field_counts[Mega_Abomasnow_ex] >= 1:
                            score += 15
                        else:
                            score += 30
                    elif card.id == Mega_Abomasnow_ex:
                        if field_counts[Snover] >= 1 and field_counts[card.id] + hand_counts[card.id] == 0:
                            score += 100
                        else:
                            score += 10
                    elif card.id == Kyogre:
                        if field_counts[card.id] >= 1:
                            score += 1
                        else:
                            score += 20
                elif context == SelectContext.DISCARD:
                    # Card to discard
                    if card.id == Basic_Water_Energy:
                        score += 100  # Prioritize Water Energy for discard (fuels Riptide).
                    elif card.id == Mega_Abomasnow_ex:
                        score += 10
                    elif card.id == Carmine:
                        if hand_counts[Lillie_Determination] >= 1:
                            score += 30
                    elif card.id == Lillie_Determination:
                        score -= 20

                    if hand_counts[card.id] >= 2:
                        score += 500  # Prefer discarding duplicates.
                    hand_counts[card.id] -= 1
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            score = 10000
            if card is None:
                score = -1
            elif card.id == Ultra_Ball:
                if hand_counts[Basic_Water_Energy] >= 3 or (my_state.handCount >= 4 and (field_counts[Mega_Abomasnow_ex] + hand_counts[Mega_Abomasnow_ex] == 0 or field_counts[Mega_Abomasnow_ex] + field_counts[Snover] == 0 or field_counts[Kyogre] == 0)):
                    score = 4000
                else:
                    score = -1
            elif card.id == Carmine:
                if field_counts[Snover] >= 1 and hand_counts[Mega_Abomasnow_ex] >= 1:
                    score = -1
                else:
                    score = 3000
            elif card.id == Lillie_Determination:
                if field_counts[Snover] >= 1 and field_counts[Mega_Abomasnow_ex] == 0 and hand_counts[Mega_Abomasnow_ex] >= 1:
                    score = -1
                else:
                    score = 3100  # Prefer over Carmine.
        elif o.type == OptionType.ATTACH:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            if pokemon is None:
                score = -1
            else:
                score = 5000
                energy_count = len(pokemon.energies)
                if energy_count == 0:
                    if o.inPlayArea == AreaType.BENCH:
                        score += 1
                if pokemon.id == Snover:
                    score += 1
                    if energy_count == 1:
                        score -= 100
                    elif energy_count >= 2:
                        score -= 400
                    if bench_attacker_index0 >= 0:
                        score -= 300
                elif pokemon.id == Mega_Abomasnow_ex:
                    score += 10
                    if energy_count == 1:
                        score += 30
                    elif energy_count >= 2:
                        score -= 300
                    if bench_attacker_index0 >= 0:
                        score -= 200
                elif pokemon.id == Kyogre:
                    score += 5
                    if len(pokemon.energies) >= 1:
                        score -= 200
                    if bench_attacker_index1 >= 0:
                        score -= 200
                if o.inPlayArea == AreaType.ACTIVE:
                    if bench_attacker_index0 >= 0 and bench_attacker_index1 >= 0 and energy_count <= 2:
                        score += 200
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = 10000 + (len(pokemon.energies) if pokemon is not None else 0)
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card is not None and card.id == Surfing_Beach and switch_index >= 0:
                score = 2000  # Prefer over retreating.
            else:
                score = -1
        elif o.type == OptionType.RETREAT:
            if switch_index >= 0:
                score = 1500
            else:
                score = -1
        elif o.type == OptionType.ATTACK:
            score = 1000
            if o.attackId == 1042:  # Riptide
                score += discard_counts[Basic_Water_Energy] * 20 - 90
            elif o.attackId == 1046:  # Hammer-lanche
                if op_active_hp <= 200:
                    score -= 100
                else:
                    score += 100

        scores.append(score)

    # Select in descending order of score
    desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
    return desc_indices[:select.maxCount]


def best_options(obs_dict: dict) -> list[int]:
    """Public entry point. Faithful to agent(); falls back to a legal move on error."""
    try:
        out = agent(obs_dict)
    except Exception:
        out = None
    if out is None:
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            return my_deck
        return _safe_fallback(obs)
    return out

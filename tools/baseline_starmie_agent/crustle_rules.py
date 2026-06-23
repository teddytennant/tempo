"""Crustle wall-deck specialist scoring (id-gated), consulted by agent/scorer.best_options.

The generic scorer pilots most decks well, but the Crustle wall (Dwebble 344 -> Crustle 345, a
150HP Stage-1 that negates all damage from opponent Pokémon-ex attacks) wants *wall-specific*
play: greedily evolve and armour the wall, heal it only when the heal does something, draw to
keep the engine flowing, shield the bench, and otherwise stall until the opponent decks out —
it barely attacks. These are exactly the card-id-gated rules the reference 1140-Elo Crustle bots
(dashimaki360 / biohack44) used.

`is_crustle_deck(state, me_i)` detects we are piloting the wall (our side shows a Dwebble/Crustle
— the deck's only Pokémon, and the only legal Basic, so it is always visible). `score_main` /
`score_sub` then produce a *self-consistent* score for every option (same scale as the reference
bot), so best_options can rank the whole turn with this table instead of the generic one. For any
other deck none of this fires (no 344/345 on board), so the generic path is untouched.
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_card_data

# ── deck card IDs (verified present in data/decks/crustle.csv + engine card data) ─────────────
DWEBBLE = 344
CRUSTLE = 345
BUDDY_POFFIN = 1086
JUMBO_ICE_CREAM = 1147
HEROS_CAPE = 1159
COOK = 1212
CHEREN = 1224
BATTLE_CAGE = 1264
BASIC_GRASS = 1
GROW_GRASS = 18
MIST = 11
SPIKY = 14

# The full 60-card decklist (used by the lethal verifier's determinization when piloting Crustle).
CRUSTLE_DECK = (
    [DWEBBLE] * 4 + [CRUSTLE] * 4 + [HEROS_CAPE]
    + [JUMBO_ICE_CREAM] * 4 + [COOK] * 4 + [BATTLE_CAGE] * 4 + [CHEREN] * 4 + [BUDDY_POFFIN] * 4
    + [GROW_GRASS] * 4 + [MIST] * 4 + [SPIKY] * 4 + [BASIC_GRASS] * 19
)
assert len(CRUSTLE_DECK) == 60

# Wall pieces that uniquely identify the deck. 344/345 are the deck's *only* Pokémon (and the
# only legal Basic), so at least one is always in our active/bench/hand — detection is reliable.
_SIGNATURE = {DWEBBLE, CRUSTLE}

KEY_PIECES = {CRUSTLE, DWEBBLE, HEROS_CAPE}                       # never discard if avoidable
USEFUL_PIECES = {JUMBO_ICE_CREAM, COOK, CHEREN, BUDDY_POFFIN, BATTLE_CAGE}

PLACEMENT_CTX = {
    SelectContext.EVOLVE, SelectContext.EVOLVES_FROM, SelectContext.EVOLVES_TO,
    SelectContext.TO_BENCH, SelectContext.TO_FIELD, SelectContext.TO_ACTIVE,
    SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON,
}
GIVE_UP_CTX = {
    SelectContext.DISCARD, SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
    SelectContext.DISCARD_CARD_OR_ATTACHED_CARD, SelectContext.TO_PRIZE,
}
HEAL_CTX = {SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER}

# ── card metadata (loaded once) ───────────────────────────────────────────────────────────────
try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}


def _meta(card_id):
    return _CARD.get(card_id)


def _is_basic_pokemon(card_id) -> bool:
    cd = _meta(card_id)
    if cd is not None:
        try:
            return bool(cd.basic) and cd.cardType == CardType.POKEMON
        except Exception:
            pass
    return card_id == DWEBBLE


def _get(obs, area, index, player_index):
    """Safely fetch a Card/Pokemon from a zone; never raises."""
    try:
        if area is None or index is None:
            return None
        ps = obs.current.players[player_index]
        if area == AreaType.DECK:
            return obs.select.deck[index]
        if area == AreaType.HAND:
            return ps.hand[index]
        if area == AreaType.DISCARD:
            return ps.discard[index]
        if area == AreaType.ACTIVE:
            return ps.active[index]
        if area == AreaType.BENCH:
            return ps.bench[index]
        if area == AreaType.PRIZE:
            return ps.prize[index]
        if area == AreaType.STADIUM:
            return obs.current.stadium[index]
        if area == AreaType.LOOKING and obs.current.looking:
            return obs.current.looking[index]
    except Exception:
        return None
    return None


def _id(card):
    return getattr(card, "id", None) if card is not None else None


def is_crustle_deck(state, me_i: int) -> bool:
    """True if our side is piloting the Crustle wall (a Dwebble/Crustle is visible on our side)."""
    try:
        me = state.players[me_i]
        if me.active:
            for p in me.active:
                if _id(p) in _SIGNATURE:
                    return True
        for p in (me.bench or []):
            if _id(p) in _SIGNATURE:
                return True
        for c in (me.hand or []):
            if _id(c) in _SIGNATURE:
                return True
        for c in (me.discard or []):
            if _id(c) in _SIGNATURE:
                return True
    except Exception:
        return False
    return False


def _my_active(state, me_i):
    try:
        a = state.players[me_i].active
        if a and a[0] is not None:
            return a[0]
    except Exception:
        pass
    return None


def _my_bench_count(state, me_i):
    try:
        return len([b for b in state.players[me_i].bench if b is not None])
    except Exception:
        return 99


def _bench_has_id(state, me_i, card_id):
    try:
        for b in state.players[me_i].bench:
            if _id(b) == card_id:
                return True
    except Exception:
        pass
    return False


def _opp_active(state, me_i):
    try:
        op = state.players[1 - me_i]
        if op.active and op.active[0] is not None:
            return op.active[0]
    except Exception:
        pass
    return None


def _opponent_value(p) -> float:
    """How tempting an opponent Pokémon is as a target (prize value + investment)."""
    v = 0.0
    cd = _meta(_id(p))
    if cd is not None:
        if getattr(cd, "megaEx", False):
            v += 300
        elif getattr(cd, "ex", False):
            v += 200
        if getattr(cd, "stage2", False):
            v += 120
        elif getattr(cd, "stage1", False):
            v += 60
    try:
        v += len(p.energies or []) * 40
    except Exception:
        pass
    try:
        v += len(p.tools or []) * 30
    except Exception:
        pass
    v += (getattr(p, "hp", 0) or 0) // 10
    return v


# ── MAIN-turn scoring (priority order: ATTACH > EVOLVE > PLAY > ABILITY > ATTACK > END > RETREAT)
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type

    if t == OptionType.ATTACH:
        card = _get(obs, o.area, o.index, me_i)
        # Hero's Cape: only ever onto the ACTIVE wall (+100 HP, active-only).
        if _id(card) == HEROS_CAPE:
            return 2100.0 if o.inPlayArea == AreaType.ACTIVE else 0.0
        # Energy gradient. The active wall needs 3 energy (Superb Scissors AND Jumbo Ice Cream);
        # once it has them, the marginal energy is worth far more on a benched Crustle, so a
        # promoted backup is immediately battle-ready — board presence is the whole game here
        # (every mirror loss is "no Active Pokémon"). So: under-fuelled active first, then pre-fuel
        # a benched Crustle, then a topped-up active, then anything.
        active = _my_active(state, me_i)
        active_energy = len(active.energies or []) if active is not None else 0
        if o.inPlayArea == AreaType.ACTIVE:
            return 1060.0 if active_energy < 3 else 1005.0
        if o.inPlayArea == AreaType.BENCH:
            tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            if _id(tgt) == CRUSTLE:
                tgt_energy = len(tgt.energies or [])
                return 1030.0 if tgt_energy < 3 else 1008.0
            return 1010.0
        return 1000.0

    if t == OptionType.EVOLVE:
        return 800.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        # Jumbo Ice Cream: heal 80, only when damaged AND 3+ energy attached — else it does nothing.
        if cid == JUMBO_ICE_CREAM:
            if active is not None and (active.hp or 0) < (active.maxHp or 0) and len(active.energies or []) >= 3:
                return 2000.0
            return -2.0   # wasted heal scores BELOW end-turn
        # Cook: heal 70, only when damaged.
        if cid == COOK:
            if active is not None and (active.hp or 0) < (active.maxHp or 0):
                return 1500.0
            return -2.0
        if cid == CHEREN:        # draw 3 — keep the engine flowing
            return 1400.0
        if cid == BATTLE_CAGE:   # stadium — shield the bench from damage counters
            return 1300.0
        # Buddy-Buddy Poffin: fetches up to 2 Basic (<=70HP) Pokémon straight to the bench —
        # Dwebble is 70HP, so this is THE board engine. With only 8 Pokémon in the deck, board
        # presence decides every mirror (loss = "no Active Pokémon"), so when the bench is thin
        # this outranks even setup: fill the bench before anything else.
        if cid == BUDDY_POFFIN:
            bench_n = _my_bench_count(state, me_i)
            if bench_n <= 0:
                return 1900.0
            if bench_n < 3:
                return 1650.0    # still want a deep bench of backups
            return 200.0         # bench already deep -> save it
        # Bench insurance: a benched backup is what prevents a "no Active Pokémon" loss.
        if _is_basic_pokemon(cid):
            bench_n = _my_bench_count(state, me_i)
            if bench_n <= 0:
                return 1700.0    # empty bench -> securing a backup is urgent
            if bench_n == 1:
                return 1250.0    # thin bench -> keep stocking it (a backup is a saved game)
            return 700.0         # deep bench -> still a body, but no rush
        return 600.0

    if t == OptionType.ABILITY:
        return 400.0

    if t == OptionType.ATTACK:
        # Attack last (it ends the turn) but pick the best one; stays below ABILITY(400).
        score = 100.0
        oa = _opp_active(state, me_i)
        try:
            from scorer import _attack_damage  # reuse weakness/resistance-aware damage
            dmg = _attack_damage(_my_active(state, me_i), o.attackId, oa)
        except Exception:
            dmg = 0
        score += min(max(dmg, 0), 250) * 0.2
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 150.0
        return score

    if t == OptionType.RETREAT:
        # The wall stays put — unless we're stuck with Dwebble active while a Crustle is benched.
        active = _my_active(state, me_i)
        if _id(active) == DWEBBLE and _bench_has_id(state, me_i, CRUSTLE):
            return 120.0
        return -1.0

    if t == OptionType.END:
        return 0.0
    return 0.0


# ── forced sub-selection scoring (base high so we always make a legal move) ─────────────────────
def score_sub(obs, o, me_i, context) -> float:
    state = obs.current
    t = o.type
    score = 2000.0

    if t == OptionType.CARD:
        card = _get(obs, o.area, o.index, getattr(o, "playerIndex", me_i))
        cid = _id(card)
        if card is not None:
            if context in PLACEMENT_CTX:
                score += 500.0
                if cid == CRUSTLE:
                    score += 120.0
                elif cid == DWEBBLE:
                    score += 80.0
                if _is_basic_pokemon(cid) and _my_bench_count(state, me_i) <= 0:
                    score += 400.0   # empty bench -> a benchable Basic is the priority fetch
            elif context == SelectContext.TO_HAND and cid in (CRUSTLE, DWEBBLE):
                score += 100.0
                if cid == DWEBBLE and _my_bench_count(state, me_i) <= 0:
                    score += 200.0

            if isinstance(card, Pokemon):
                if getattr(o, "playerIndex", me_i) != me_i:
                    score += 500.0 if o.area == AreaType.ACTIVE else 100.0
                    score += _opponent_value(card)
                else:
                    if context in HEAL_CTX:
                        score += max(0, (getattr(card, "maxHp", 0) or 0) - (getattr(card, "hp", 0) or 0))
                    else:
                        score += getattr(card, "hp", 0) or 0
                        if cid == CRUSTLE:
                            score += 60.0
            else:
                if context in GIVE_UP_CTX:
                    if cid in KEY_PIECES:
                        score -= 300.0      # protect the wall line + Hero's Cape
                    elif cid in USEFUL_PIECES:
                        score -= 80.0
                    elif cid == BASIC_GRASS:
                        score += 60.0       # spare basic energy is the cheapest pitch

    elif t in (OptionType.ENERGY_CARD, OptionType.ENERGY):
        cid = getattr(o, "cardId", None)
        if context in (SelectContext.DISCARD_ENERGY_CARD, SelectContext.DISCARD_ENERGY,
                       SelectContext.TO_HAND_ENERGY, SelectContext.TO_DECK_ENERGY,
                       SelectContext.DETACH_FROM):
            if cid == BASIC_GRASS:
                score += 40.0
            elif cid in (GROW_GRASS, MIST, SPIKY):
                score -= 40.0

    elif t == OptionType.YES:
        # Default yes — except turn order: a slow wall/heal deck prefers to go SECOND.
        if context == SelectContext.IS_FIRST:
            score += 0.0
        else:
            score += 100.0

    elif t == OptionType.NO:
        if context == SelectContext.IS_FIRST:
            score += 150.0     # go second
        else:
            score += 0.0

    elif t == OptionType.NUMBER:
        score += getattr(o, "number", 0) or 0

    elif t == OptionType.SPECIAL_CONDITION:
        score = 2000.0

    return score

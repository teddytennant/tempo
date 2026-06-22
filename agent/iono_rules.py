"""Iono's Bellibolt ex specialist scoring (id-gated), consulted by agent/scorer.best_options.

The generic scorer pilots most decks well, but the Iono's Bellibolt ex Lightning-stacking engine
wants *archetype-specific* play that the generic priority table does not capture: evolve the
Voltorb / Tadbulb->Bellibolt ex / Wattrel->Kilowattrel lines, pile Basic Lightning Energy onto the
board (Bellibolt ex's Electromagnetic Circuit ability + Kilowattrel + Levincia / Energy Retrieval /
Max Rod recursion), keep the active fuelled, and only swing with Voltaic Chain once the energy is
high (its damage scales with total attached Energy). Iono disruption + careful deck searches keep
the engine flowing.

This is the SAME archetype that empirically beats all four of our other decks as an opponent
(agent/bots/bot_iono.py, the kiyotah notebook port). This specialist is a faithful reproduction of
that winning policy, refactored into the scorer's per-option score_main / score_sub contract so
`best_options` can rank the whole turn with this table (and run the verified multi-step lethal
check) instead of the generic one.

`is_iono_deck(state, me_i)` detects we are piloting the Iono line (an Iono Pokémon — the deck's only
Pokémon, and the only legal Basics — is always visible on our side). `score_main` / `score_sub` then
produce a self-consistent score for every option. For any other deck none of this fires (no Iono
signature cards on our side), so the generic path is byte-identical.
"""
from __future__ import annotations

from collections import defaultdict

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_card_data

# ── deck card IDs (verified present in data/decks/iono.csv + engine card data) ────────────────────
IONO_VOLTORB = 265        # x3  Basic
IONO_TADBULB = 268        # x3  Basic
IONO_BELLIBOLT_EX = 269   # x3  Stage 1 ex (Electromagnetic Circuit: load Lightning; Voltaic Chain)
IONO_WATTREL = 270        # x3  Basic
IONO_KILOWATTREL = 271    # x3  Stage 1 (energy-accel ability)
BUDDY_BUDDY_POFFIN = 1086  # x3  fetch 2 small Basics to bench
NIGHT_STRETCHER = 1097    # x2  recover Pokémon/Energy from discard
MAX_ROD = 1110            # x1  shuffle Lightning back from discard
ENERGY_RETRIEVAL = 1118   # x1  recover 2 Basic Energy from discard
ULTRA_BALL = 1121         # x3  search any Pokémon (discard 2)
POKE_PAD = 1152           # x2  draw / dig
LILLIE_DETERMINATION = 1227  # x4  supporter draw
CANARI = 1233             # x4  supporter (search line)
LEVINCIA = 1254           # x3  stadium (Lightning recursion / ability)
BASIC_LIGHTNING = 4       # x22 Basic {L} Energy

# Full 60-card decklist (used by the lethal verifier's determinization when piloting Iono).
IONO_DECK = (
    [IONO_VOLTORB] * 3 + [IONO_TADBULB] * 3 + [IONO_BELLIBOLT_EX] * 3
    + [IONO_WATTREL] * 3 + [IONO_KILOWATTREL] * 3
    + [BUDDY_BUDDY_POFFIN] * 3 + [NIGHT_STRETCHER] * 2 + [MAX_ROD] + [ENERGY_RETRIEVAL]
    + [ULTRA_BALL] * 3 + [POKE_PAD] * 2 + [LILLIE_DETERMINATION] * 4 + [CANARI] * 4
    + [LEVINCIA] * 3 + [BASIC_LIGHTNING] * 22
)
assert len(IONO_DECK) == 60

# The five Iono Pokémon uniquely identify the deck — they are the deck's *only* Pokémon (and the
# only legal Basics), so at least one is always in our active/bench/hand/discard. The set is disjoint
# from Crustle (344/345), Lucario, Starmie, and Dunsparce signatures, so the id-gated paths never
# overlap.
_SIGNATURE = {IONO_VOLTORB, IONO_TADBULB, IONO_BELLIBOLT_EX, IONO_WATTREL, IONO_KILOWATTREL}

# ── card metadata (loaded once) ───────────────────────────────────────────────────────────────────
try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}

# `can_attack` persists across the calls of a single MAIN turn (recomputed at the start of every MAIN
# selection by scanning the menu for an ATTACK option). It deprioritises piling more energy onto an
# already-loaded active when an attack is available this turn — exactly the reference policy.
_can_attack = False

# Single-entry per-decision context cache. The scorer builds one Observation per decision and then
# calls score_main / score_sub once per option (in option order), so we compute the heavy field/hand
# state once and keep mutating `id_counts` in option order across that one decision (matching the
# reference bot's single scoring loop).
_CACHE_KEY = None
_CACHE_CTX = None


def _id(card):
    return getattr(card, "id", None) if card is not None else None


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


def _energies(p) -> int:
    try:
        return len(p.energies or [])
    except Exception:
        return 0


def is_iono_deck(state, me_i: int) -> bool:
    """True if our side is piloting the Iono line (an Iono Pokémon is visible on our side)."""
    try:
        me = state.players[me_i]
        for p in (me.active or []):
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


class _Ctx:
    __slots__ = (
        "field_counts", "field_hand_counts", "hand_counts", "hand_scores",
        "unused_hand_count", "discard_counts", "energy_count", "can_ability",
        "active_attacker", "bench_attacker", "field_pokemon1", "field_pokemon2",
        "no_more_pokemon", "stadium_id", "op_prize", "op_active_hp", "no_draw",
        "turn", "id_counts", "my_index",
    )


def _build(obs, me_i: int) -> _Ctx:
    """Compute the per-decision board/hand state (faithful to the reference bot's pre-pass)."""
    global _can_attack
    state = obs.current
    select = obs.select
    my_state = state.players[me_i]
    op_state = state.players[1 - me_i]

    c = _Ctx()
    c.my_index = me_i
    c.turn = getattr(state, "turn", 0)
    c.op_prize = len(op_state.prize)

    field_counts = defaultdict(int)
    field_hand_counts = defaultdict(int)
    active_attacker = False
    bench_attacker = False
    energy_count = 0
    can_ability = False

    for p in my_state.active:
        if p is None:
            continue
        field_counts[p.id] += 1
        field_hand_counts[p.id] += 1
        energy_count += _energies(p)
        if p.id == IONO_KILOWATTREL and _energies(p) > 0:
            can_ability = True
        if p.id == IONO_VOLTORB and _energies(p) >= 2:
            active_attacker = True
    for p in my_state.bench:
        if p is None:
            continue
        field_counts[p.id] += 1
        field_hand_counts[p.id] += 1
        energy_count += _energies(p)
        if p.id == IONO_KILOWATTREL and _energies(p) > 0:
            can_ability = True
        if p.id == IONO_VOLTORB and _energies(p) >= 2:
            bench_attacker = True

    field_pokemon1 = field_counts[IONO_TADBULB] + field_counts[IONO_BELLIBOLT_EX]
    field_pokemon2 = field_counts[IONO_WATTREL] + field_counts[IONO_KILOWATTREL]
    no_more_pokemon = (len(my_state.bench) >= 5)
    if field_counts[IONO_TADBULB] + field_counts[IONO_WATTREL] >= 1:
        no_more_pokemon = False

    stadium_id = 0
    for s in state.stadium:
        stadium_id = s.id

    hand_counts = defaultdict(int)
    hand_scores = []
    unused_hand_count = 0
    for card in my_state.hand:
        score = -10000
        cid = card.id
        if cid == IONO_VOLTORB:
            score = 100
        elif cid == IONO_BELLIBOLT_EX:
            if field_counts[cid] <= 1:
                score = 120
        elif cid == IONO_KILOWATTREL:
            if field_counts[cid] <= 1:
                score = 140
        elif cid == ULTRA_BALL:
            if not no_more_pokemon:
                score = 10
        elif cid == NIGHT_STRETCHER:
            score = 50
        elif cid == ENERGY_RETRIEVAL:
            score = 20
        elif cid == MAX_ROD:
            score = 1000
        elif cid == LILLIE_DETERMINATION:
            score = 150
        elif cid == CANARI:
            score = 160
        elif cid == LEVINCIA:
            if stadium_id != LEVINCIA:
                score = 30
        elif cid == BASIC_LIGHTNING:
            score = -10
        score -= hand_counts[cid] * 100
        hand_scores.append(score)
        if score < 0:
            unused_hand_count += 1
        hand_counts[cid] += 1
        field_hand_counts[cid] += 1

    discard_counts = defaultdict(int)
    for card in my_state.discard:
        discard_counts[card.id] += 1

    op_active_hp = 10000
    if len(op_state.active) >= 1 and op_state.active[0] is not None:
        op_active_hp = op_state.active[0].hp

    # `can_attack` is recomputed at the start of every MAIN selection and then carried through the
    # turn's sub-selections (matching the reference bot's module global).
    if select.context == SelectContext.MAIN:
        _can_attack = any(o.type == OptionType.ATTACK for o in select.option)

    c.field_counts = field_counts
    c.field_hand_counts = field_hand_counts
    c.hand_counts = hand_counts
    c.hand_scores = hand_scores
    c.unused_hand_count = unused_hand_count
    c.discard_counts = discard_counts
    c.energy_count = energy_count
    c.can_ability = can_ability
    c.active_attacker = active_attacker
    c.bench_attacker = bench_attacker
    c.field_pokemon1 = field_pokemon1
    c.field_pokemon2 = field_pokemon2
    c.no_more_pokemon = no_more_pokemon
    c.stadium_id = stadium_id
    c.op_active_hp = op_active_hp
    c.no_draw = (my_state.deckCount <= 5)
    c.id_counts = defaultdict(int)
    return c


def _ctx(obs, me_i: int) -> _Ctx:
    global _CACHE_KEY, _CACHE_CTX
    select = obs.select
    me = obs.current.players[me_i]
    # Fingerprint that is stable within one decision but changes between decisions (so id_counts is
    # rebuilt fresh per decision and accumulates correctly across that decision's options).
    key = (
        id(obs), me_i, getattr(select, "context", None), len(select.option),
        getattr(me, "handCount", len(me.hand or [])), getattr(me, "deckCount", 0),
        getattr(obs.current, "turn", 0),
    )
    if _CACHE_KEY == key and _CACHE_CTX is not None:
        return _CACHE_CTX
    c = _build(obs, me_i)
    _CACHE_KEY = key
    _CACHE_CTX = c
    return c


# ── attach-target valuation (shared by MAIN OptionType.ATTACH and ATTACH_FROM sub-selection) ───────
def _score_attach_target(p, in_play_area, C: _Ctx) -> float:
    score = 40000.0
    if p is None:
        return -1.0
    pid = p.id
    e = _energies(p)
    if pid == IONO_VOLTORB:
        if e >= 2:
            if in_play_area == AreaType.ACTIVE and not _can_attack:
                score += 3000
        else:
            if in_play_area == AreaType.ACTIVE:
                score += 5000
            elif C.bench_attacker or C.active_attacker:
                score += 100
            else:
                score += 1000
    elif pid == IONO_TADBULB:
        score += 10 - e
    elif pid == IONO_BELLIBOLT_EX:
        if e >= 4:
            if in_play_area == AreaType.ACTIVE and not _can_attack:
                score += 500
        else:
            if in_play_area == AreaType.ACTIVE:
                score += 800
            elif C.bench_attacker or C.active_attacker:
                score += 14 - e
            else:
                score += 100
    elif pid == IONO_WATTREL:
        if e >= 1 or in_play_area == AreaType.ACTIVE:
            score += 10 - e
        else:
            score += 6000
    elif pid == IONO_KILOWATTREL:
        if e >= 1:
            score += 11 - e
        else:
            score += 8000
    return score


# ── MAIN-turn scoring (priority order: setup / attach / evolve / ability before the attack) ────────
def score_main(obs, o, me_i) -> float:
    C = _ctx(obs, me_i)
    t = o.type

    if t == OptionType.NUMBER:
        return float(o.number or 0)
    if t == OptionType.YES:
        return 1.0

    if t == OptionType.ATTACH:
        p = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
        return _score_attach_target(p, o.inPlayArea, C)

    if t == OptionType.EVOLVE:
        return 110000.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        if card is None:
            return -1.0
        data = _CARD.get(card.id)
        cid = card.id
        if data is not None and data.cardType == CardType.STADIUM:
            if C.discard_counts[BASIC_LIGHTNING] >= 1 or C.can_ability:
                return 85000.0
            return -1.0
        if data is not None and data.cardType == CardType.SUPPORTER:
            score = 25000.0
            if cid == LILLIE_DETERMINATION:
                return score + 1000.0
            if C.no_draw:
                return -1.0
            if cid == CANARI:
                if C.no_more_pokemon:
                    return -1.0
                if (C.field_counts[IONO_VOLTORB] > 0 and C.field_counts[IONO_BELLIBOLT_EX] > 0
                        and C.field_counts[IONO_KILOWATTREL] > 0):
                    return score + 100.0
                return score + 2000.0
            return score
        if data is not None and data.cardType == CardType.POKEMON:
            if cid == IONO_VOLTORB and C.field_counts[IONO_VOLTORB] >= 2:
                return -1.0
            if cid == IONO_TADBULB and C.field_pokemon1 >= 2:
                return -1.0
            if cid == IONO_WATTREL and C.field_pokemon2 >= 2:
                if (C.op_prize >= 2 or C.field_counts[IONO_VOLTORB] == 0
                        or C.field_counts[IONO_BELLIBOLT_EX] == 0):
                    return -1.0
            return 100000.0
        # Items / tools.
        if cid == NIGHT_STRETCHER:
            if (C.discard_counts[IONO_VOLTORB] > 0
                    or (C.discard_counts[IONO_BELLIBOLT_EX] > 0 and C.field_counts[IONO_TADBULB] > 0)
                    or (C.discard_counts[IONO_KILOWATTREL] > 0 and C.field_counts[IONO_WATTREL] > 0)):
                return 75000.0
            return -1.0
        if cid == ENERGY_RETRIEVAL:
            return 61000.0
        if cid == MAX_ROD:
            if C.turn >= 3 and C.discard_counts[BASIC_LIGHTNING] >= 2:
                return 55000.0
            return -1.0
        if C.no_draw:
            return -1.0
        if cid == BUDDY_BUDDY_POFFIN:
            return 80000.0
        if cid == ULTRA_BALL:
            if C.no_more_pokemon or C.turn <= 2:
                return -1.0
            if C.field_hand_counts[IONO_BELLIBOLT_EX] > 0 and C.field_hand_counts[IONO_KILOWATTREL] > 0:
                return 45000.0 if C.unused_hand_count >= 2 else -1.0
            return 62000.0 if C.unused_hand_count >= 1 else -1.0
        if cid == POKE_PAD:
            return 79000.0
        return 0.0

    if t == OptionType.ABILITY:
        card = _get(obs, o.area, o.index, me_i)
        if card is not None:
            if card.id == IONO_BELLIBOLT_EX:
                return 50000.0
            if card.id == LEVINCIA:
                return 8000.0
            if card.id == IONO_KILOWATTREL and not C.no_draw:
                return 30000.0
        return -1.0

    if t == OptionType.RETREAT:
        return 10000.0 if (C.bench_attacker and not C.active_attacker) else -1.0

    if t == OptionType.ATTACK:
        return float(o.attackId)

    return 0.0  # END and anything else: end the turn only when nothing better remains.


# ── forced sub-selection scoring ──────────────────────────────────────────────────────────────────
# A large positive base so the scorer's positive-threshold selection takes the top-`maxCount`
# options in score order — identical to the reference bot's `desc_indices[:maxCount]`.
_SUB_BASE = 1_000_000.0


def score_sub(obs, o, me_i, context) -> float:
    C = _ctx(obs, me_i)
    t = o.type

    if t == OptionType.NUMBER:
        return _SUB_BASE + float(o.number or 0)
    if t == OptionType.YES:
        return _SUB_BASE + 1.0

    if t == OptionType.ATTACH or context == SelectContext.ATTACH_FROM:
        if t == OptionType.ATTACH:
            p = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            return _SUB_BASE + _score_attach_target(p, o.inPlayArea, C)
        p = _get(obs, o.area, o.index, getattr(o, "playerIndex", me_i))
        return _SUB_BASE + _score_attach_target(p, getattr(o, "inPlayArea", None), C)

    if t == OptionType.CARD:
        card = _get(obs, o.area, o.index, getattr(o, "playerIndex", me_i))
        score = 0.0
        if card is None:
            return _SUB_BASE + score
        cid = card.id
        if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                       SelectContext.SETUP_ACTIVE_POKEMON):
            energy = 0
            if isinstance(card, Pokemon):
                energy = _energies(card)
                score -= card.hp
                score -= energy * 100
            if cid == IONO_VOLTORB:
                if 20 + C.energy_count * 20 >= C.op_active_hp:
                    score += 100000
                else:
                    score += 1500
                if energy >= 1:
                    score += 200
                    if energy >= 2:
                        score += 10000
            elif cid == IONO_BELLIBOLT_EX:
                score += 1000
                if energy >= 4:
                    score += 1000
            elif cid == IONO_TADBULB:
                score += 10
            return _SUB_BASE + score

        if context in (SelectContext.TO_HAND, SelectContext.TO_BENCH):
            if cid == BASIC_LIGHTNING:
                score += 1
            elif cid == IONO_VOLTORB:
                if o.area == AreaType.DISCARD:
                    score += 100000
                if C.field_counts[cid] == 0:
                    score += 110
                elif C.field_counts[cid] == 1 and C.op_prize >= 2:
                    score += 5
            elif cid == IONO_TADBULB:
                if C.field_pokemon1 == 0:
                    score += 200
                elif C.field_pokemon1 == 1:
                    if C.op_prize >= 3 or (C.op_prize >= 2 and C.field_counts[IONO_BELLIBOLT_EX] == 0):
                        score += 20
            elif cid == IONO_BELLIBOLT_EX:
                if C.field_hand_counts[cid] == 0:
                    score += 250
                    if C.field_counts[IONO_TADBULB] > 0:
                        score += 300
                elif C.field_hand_counts[cid] == 1:
                    if C.op_prize >= 3:
                        score += 30
                        if C.field_counts[IONO_TADBULB] > 0:
                            score += 30
            elif cid == IONO_WATTREL:
                if C.field_pokemon2 == 0:
                    score += 320
                elif C.field_pokemon2 == 1:
                    score += 15
            elif cid == IONO_KILOWATTREL:
                if C.field_hand_counts[cid] == 0:
                    score += 300
                    if C.field_counts[IONO_WATTREL] > 0:
                        score += 250
                elif C.field_hand_counts[cid] == 1:
                    score += 25
                    if C.field_counts[IONO_WATTREL] > 0:
                        score += 25
            if cid != BASIC_LIGHTNING:
                if C.hand_counts[cid] >= 2:
                    score -= 20000
                elif C.hand_counts[cid] >= 1:
                    score -= 2000
                if C.id_counts[cid] == 1:
                    score -= 1000
                elif C.id_counts[cid] >= 2:
                    score -= 10000
            C.id_counts[cid] += 1
            return _SUB_BASE + score

        if context == SelectContext.DISCARD:
            if o.area == AreaType.HAND and getattr(o, "playerIndex", me_i) == me_i:
                idx = o.index
                if 0 <= idx < len(C.hand_scores):
                    score = -C.hand_scores[idx]
            return _SUB_BASE + score

        return _SUB_BASE + score

    return _SUB_BASE

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

v7 hardening (measured vs the public dashimaki mirror bot + the wall-breaker field):
  - Go FIRST, not second: Superb Scissors is energy-gated (3 attachments), so the first player
    reaches it a half-round earlier and stays a full hit ahead for the whole race. The mirror is
    decided by that KO race (0 deck-outs across the baseline matrix), not by patience.
  - Energy routing: Grow Grass provides {G} AND +20 HP -> stack it on the wall; Spiky reflects
    20 onto every attacker that touches the active; Basic {G} guarantees the attack's {G} cost;
    Mist is the last filler. Backup Crustles still get fuelled to 3 before the active is topped.
  - Heal discipline: never burn a 70/80-point heal on chip damage smaller than the heal (the
    heal budget IS the wall's effective HP), except in emergencies (active would die to the
    opponent's best data-visible attack).
  - Deck-race governors: Cheren/Poffin are optional deck burn. Stop them near the deck-out floor,
    and in true stall states (our Crustle active blanks a non-piercing opponent ex) never draw
    ourselves below the opponent's deck count — the deck-out war is won by whoever draws less.
  - Promotion: after a KO, promote the most battle-ready backup (energy + tools), not the
    biggest HP number.
"""
from __future__ import annotations

from cg.api import (
    AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext, all_attack, all_card_data,
)

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

try:
    _ATK = {a.attackId: a for a in all_attack()}
except Exception:
    _ATK = {}

# Attacks carrying this phrase (Nebula Beam 210, Destructive Drill 150, ...) pierce Mysterious
# Rock Inn; every other Pokémon-ex attack is blanked while a Crustle is the target.
_PIERCE = "any effects on your opponent"


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


def _opp_threat(state, me_i) -> int:
    """Best data-visible attack damage the opponent's active can put on our active.

    Weakness-doubled; zeroed when our active Crustle's Mysterious Rock Inn blanks a non-piercing
    Pokémon-ex attacker. Text-scaling attacks (Powerful Hand, Work Rush, ...) carry damage=0 in
    the card data, so this is a LOWER bound — it drives emergency heals only, never heal denial.
    """
    op = _opp_active(state, me_i)
    ocd = _meta(_id(op)) if op is not None else None
    if ocd is None:
        return 0
    mine = _my_active(state, me_i)
    mcd = _meta(_id(mine)) if mine is not None else None
    is_ex = bool(getattr(ocd, "ex", False) or getattr(ocd, "megaEx", False))
    op_energy = len(getattr(op, "energies", None) or [])
    best = 0
    for aid in (getattr(ocd, "attacks", None) or []):
        a = _ATK.get(aid)
        if a is None:
            continue
        # Only a payable attack is a threat: they attach at most 1 energy before striking, so an
        # attacker sitting 2+ energy short of the cost cannot hit us next turn. (Without this the
        # opening Dwebble reads "doomed" against an unfuelled wall and never gets its Ascension
        # energy — the exact line the whole deck is built on.)
        if op_energy + 1 < len(a.energies or []):
            continue
        dmg = a.damage or 0
        if aid == 1072:
            # Alakazam "Powerful Hand": 2 damage counters per card in their hand — counter
            # placement, so no weakness and Rock Inn does NOT stop it. This is THE wall-breaker
            # (one-shots every wall once their hand is 8+), invisible in the damage data.
            try:
                hand_n = state.players[1 - me_i].handCount or 0
            except Exception:
                hand_n = 0
            best = max(best, 20 * hand_n)
            continue
        if dmg <= 0:
            continue
        text = a.text or ""
        if mcd is not None and _PIERCE not in text:
            atype = getattr(ocd, "energyType", None)
            if getattr(mcd, "weakness", None) is not None and atype is not None and mcd.weakness == atype:
                dmg *= 2
        if _id(mine) == CRUSTLE and is_ex and _PIERCE not in text:
            dmg = 0
        best = max(best, dmg)
    return best


def _wall_immune(state, me_i) -> bool:
    """True when our ACTIVE Crustle blanks the opponent's active attacker entirely: they are a
    Pokémon-ex and none of their attacks pierce Mysterious Rock Inn. This is the true stall
    state — they cannot touch the wall, so the game is ours on prizes or their deck-out."""
    if _id(_my_active(state, me_i)) != CRUSTLE:
        return False
    op = _opp_active(state, me_i)
    ocd = _meta(_id(op)) if op is not None else None
    if ocd is None or not (getattr(ocd, "ex", False) or getattr(ocd, "megaEx", False)):
        return False
    for aid in (getattr(ocd, "attacks", None) or []):
        a = _ATK.get(aid)
        if a is not None and _PIERCE in (a.text or ""):
            return False
    return True


def _stall_conserve(state, me_i) -> bool:
    """In a stall the loser is whoever starts a turn with 0 deck cards first: once we cannot
    out-deck the opponent by a safe margin, every optional draw/search is a step toward our own
    deck-out. Only fires in the blanked-ex stall — in live damage races drawing stays correct."""
    try:
        if not _wall_immune(state, me_i):
            return False
        me = state.players[me_i]
        op = state.players[1 - me_i]
        return me.deckCount <= op.deckCount + 4
    except Exception:
        return False


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
        cid = _id(card)
        # Hero's Cape: only ever onto the ACTIVE wall (+100 HP, active-only).
        if cid == HEROS_CAPE:
            return 2100.0 if o.inPlayArea == AreaType.ACTIVE else 0.0
        # Energy gradient. The active wall needs 3 energy (Superb Scissors AND Jumbo Ice Cream);
        # once it has them, the marginal energy is worth far more on a benched Crustle, so a
        # promoted backup is immediately battle-ready — board presence is the whole game here
        # (every mirror loss is "no Active Pokémon"). So: under-fuelled active first, then pre-fuel
        # a benched Crustle, then a topped-up active, then anything.
        # Within the active's fuel, the CARD matters: Grow Grass provides the attack's {G} AND
        # +20 HP on the wall; Spiky reflects 20 onto every attacker that hits us (compounding in
        # the 120-per-hit mirror race); Basic {G} secures the cost; Mist (colorless) fills last.
        active = _my_active(state, me_i)
        active_energy = len(active.energies or []) if active is not None else 0
        if o.inPlayArea == AreaType.ACTIVE:
            has_g = any(int(e) == int(EnergyType.GRASS) for e in (active.energies or [])) \
                if active is not None else False
            # Doomed-wall triage: if the opponent's next hit KOs this active and it still can't
            # reach Superb Scissors (would end the turn below 3 energy), the energy dies with it
            # having never attacked. Route the attachment to the bench instead so the NEXT wall
            # promotes battle-ready — energy attrition is exactly how wall-breakers chain us down.
            if active is not None and active_energy < 2 and _my_bench_count(state, me_i) > 0:
                threat = _opp_threat(state, me_i)
                if threat > 0 and (active.hp or 0) <= threat:
                    return 1009.0
            if active_energy < 3:
                bias = {GROW_GRASS: 8.0, SPIKY: 6.0, BASIC_GRASS: 4.0}.get(cid, 0.0)
                if not has_g and active_energy >= 2 and cid in (GROW_GRASS, BASIC_GRASS):
                    bias += 15.0   # last fuel slot: Superb Scissors needs a {G} source
                return 1060.0 + bias
            if not has_g and cid in (GROW_GRASS, BASIC_GRASS):
                return 1055.0      # 3+ energies but all colorless: fix the {G} line first
            if cid == GROW_GRASS:
                return 1020.0      # +20 max HP on the tank, still below arming a backup
            if cid == SPIKY:
                return 1012.0
            return 1005.0
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
        # Heal discipline: the 8 heal cards are the wall's real HP pool — burning one on chip
        # damage smaller than the heal throws away effective HP the long matchups need. Heal at
        # full value only, EXCEPT when the opponent's best visible attack would KO us as-is.
        if cid in (JUMBO_ICE_CREAM, COOK):
            if active is None:
                return -2.0
            dmg_taken = max(0, (active.maxHp or 0) - (active.hp or 0))
            if dmg_taken <= 0:
                return -2.0
            emergency = (active.hp or 0) <= _opp_threat(state, me_i)
            # Jumbo Ice Cream: heal 80, needs 3+ energy attached — else it does nothing.
            if cid == JUMBO_ICE_CREAM:
                if len(active.energies or []) >= 3 and (dmg_taken >= 80 or emergency):
                    return 2000.0
                return -2.0
            # Cook: heal 70 (supporter — don't spend the slot on a partial heal).
            if dmg_taken >= 70 or emergency:
                return 1500.0
            return -2.0
        if cid == CHEREN:        # draw 3 — keep the engine flowing…
            try:
                my_deck = state.players[me_i].deckCount
            except Exception:
                my_deck = 99
            if my_deck <= 8:
                return -2.0      # …but never draw ourselves toward the deck-out floor
            if _stall_conserve(state, me_i):
                return -2.0      # deck-out war: whoever burns their deck first loses
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
            if _stall_conserve(state, me_i):
                return -2.0      # it thins our deck by 2 and parks snipeable 70HP bodies
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
                        # Battle-readiness: after a KO promote the FUELLED backup (it attacks
                        # immediately), and value attached tools — not just the HP number. The
                        # curve is convex: a 3-energy wall Superbs the turn it lands, while a
                        # half-fuelled one mostly donates its energy to the next KO.
                        e_n = len(getattr(card, "energies", None) or [])
                        score += 100.0 if e_n >= 3 else (30.0 if e_n == 2 else 10.0 * e_n)
                        score += 20.0 * len(getattr(card, "tools", None) or [])
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
        # Default yes — INCLUDING turn order: Superb Scissors is energy-gated (3 attachments),
        # so the first player reaches it a half-round earlier and stays a full hit ahead for the
        # whole race. Measured: the mirror is a KO race (0 deck-outs), and going second meant
        # eating the first 120 in every flip we won. Go FIRST.
        if context == SelectContext.IS_FIRST:
            score += 0.0
        else:
            score += 100.0

    elif t == OptionType.NO:
        if context == SelectContext.IS_FIRST:
            score += 150.0
        else:
            score += 0.0

    elif t == OptionType.NUMBER:
        score += getattr(o, "number", 0) or 0

    elif t == OptionType.SPECIAL_CONDITION:
        score = 2000.0

    return score

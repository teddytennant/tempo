"""Fezandipiti ex / Alakazam "Powerful Hand" draw-combo specialist (id-gated), consulted by
agent/scorer.best_options.

This is the THIRD-place PTCG-Club frontier list (~1323 Elo): the SAME Alakazam "Powerful Hand"
engine our dunsparce specialist pilots, but tuned with a Fezandipiti ex tech, Lillie's
Determination, Wondrous Patch and Xerosic's Machinations swapped in for Battle Cage / two Enhanced
Hammers. The win condition is unchanged — one attack:

  • Alakazam (743, Stage-2 P, 140HP). "Powerful Hand" (1072): {P} -> 2 damage counters on the
    opponent's Active for EACH card in your hand = 20 x (hand size), as fixed damage counters that
    ignore weakness/resistance AND damage-prevention walls. Non-ex, so it cracks the Crustle wall.
  • Abra 741 -> Kadabra 742 -> Alakazam 743 (Rare Candy 1079 skips Kadabra); Kadabra & Alakazam draw
    3 on evolution (Psychic Draw). Dunsparce 305 -> Dudunsparce 66's Run Away Draw is a repeatable +3.
    Dawn 1231 / Hilda 1225 / Poké Pad 1152 / Buddy-Buddy Poffin 1086 are the search engines.

What the Fezandipiti list adds on top of the Powerful Hand core, and why this specialist beats the
generic scorer (and squeezes more than the dunsparce specialist out of this exact 60):
  1. Fezandipiti ex (140, Basic Dark, 210HP). "Flip the Script": once per turn, if any of your
     Pokémon were KO'd during the opponent's last turn, draw 3 — pure card advantage that GROWS the
     next Powerful Hand, AND a 210HP wall that buys the turns the Stage-2 line needs to assemble.
     "Cruel Arrow" (183), {C}{C}{C}: 100 damage to ANY of the opponent's Pokémon (its `damage` field
     is 0 — the snipe is in text — so the generic scorer can't see it) — a backup pick-off attacker.
  2. Lillie's Determination (1227): shuffle hand, draw 6 (8 at exactly 6 prizes). A *refuel*, not a
     grower: it sets the hand to a fixed size, so it is great when our hand is small and is a TRAP
     right before a Powerful Hand swing (it would shrink a fat hand). We play it only when small.
  3. Wondrous Patch (1146): attach a Basic {P} from the discard to a BENCHED {P} Pokémon —
     accelerates the next Alakazam off the discard so it can swing the turn it is promoted.
  4. Xerosic's Machinations (1197): strip the opponent's hand to 3 — a 1-of disruption tech, ranked
     below all of our own hand-growers (our cards are worth more to us than denying theirs).

`is_fezandipiti_deck(state, me_i)` fires only when an Alakazam/Dunsparce-line Pokémon AND a card
unique to THIS list (Fezandipiti ex / Lillie's Determination / Wondrous Patch / Xerosic's) are both
visible on our side. That conjunction is disjoint from every other deck: Iono also runs Lillie's
Determination but never an Abra, the dunsparce list runs the Alakazam core but none of the four
distinguishers, and Crustle/Lucario/Starmie share none of it — so this id-gated path never overlaps
with another specialist and the generic + other paths stay byte-identical for every other deck.
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_attack, all_card_data

# ── deck card IDs (verified via all_card_data against data/decks/fezandipiti.csv) ────────────────
ABRA = 741          # Basic P, 50HP   -> Kadabra
KADABRA = 742       # Stage1 P, 80HP  -> Alakazam; Psychic Draw on evolve
ALAKAZAM = 743      # Stage2 P, 140HP; Powerful Hand (1072). THE attacker; Psychic Draw on evolve
DUNSPARCE = 305     # Basic C, 70HP   -> Dudunsparce
DUDUNSPARCE = 66    # Stage1 C, 140HP; Run Away Draw (draw 3, shuffle self back) — the draw engine
FEZANDIPITI = 140   # Basic Dark, 210HP; Flip the Script (draw 3 on KO); Cruel Arrow (100 snipe)

BUDDY_POFFIN = 1086     # item: up to 2 Basic (<=70HP) Pokémon onto the bench (Abra/Dunsparce)
POKE_PAD = 1152         # item: search a non-Rule-Box Pokémon to hand (net-0 dig)
RARE_CANDY = 1079       # item: Basic -> Stage 2 in hand (Abra -> Alakazam, skipping Kadabra)
HILDA = 1225            # supporter: search an Evolution Pokémon + an Energy to hand (hand +2)
ENHANCED_HAMMER = 1081  # item: discard a Special Energy from an opponent's Pokémon
NIGHT_STRETCHER = 1097  # item: recover a Pokémon or Basic Energy from discard to hand (net-0)
SACRED_ASH = 1129       # item: shuffle up to 5 Pokémon from discard into deck (anti-deckout)
DAWN = 1231             # supporter: search a Basic + Stage1 + Stage2 to hand (hand +3)
BOSS_ORDERS = 1182      # supporter: gust a benched opponent Pokémon to Active
LANA_AID = 1184         # supporter: recover up to 3 non-Rule-Box Pokémon / Basic Energy to hand
LILLIE_DET = 1227       # supporter: shuffle hand, draw 6 (8 at exactly 6 prizes) — a *refuel*
WONDROUS_PATCH = 1146   # item: attach a Basic {P} from discard to a benched {P} Pokémon (accel)
XEROSIC = 1197          # supporter: opponent discards down to 3 cards (disruption tech)
TELEPATH_P = 19         # special energy: provides {P}
BASIC_P = 5             # Basic {P} Energy
ENRICHING = 13          # special energy: provides {C} (does NOT power Powerful Hand's {P})

# Attack IDs (verified via all_attack).
POWERFUL_HAND = 1072    # Alakazam, {P}: 2 damage counters per card in hand = 20 x handCount
SUPER_PSY_BOLT = 1071   # Kadabra, {P}: 30
TELEPORTATION = 1070    # Abra, {P}: 10 + self-switch
LAND_CRUSH = 76         # Dudunsparce, {C}{C}{C}: 90
TRADING_PLACES = 423    # Dunsparce, {C}: self-switch
RAM = 424               # Dunsparce, {C}{C}: 20
CRUEL_ARROW = 183       # Fezandipiti ex, {C}{C}{C}: 100 to ANY of the opponent's Pokémon (text)
CRUEL_ARROW_DAMAGE = 100

ALAKAZAM_LINE = {ABRA, KADABRA, ALAKAZAM}
DRAW_ENGINE = {DUNSPARCE, DUDUNSPARCE}
# Pokémon that anchor the deck to the Powerful Hand engine (none appear in any deck but the sibling
# Alakazam / Dunsparce lists). Used together with a Fezandipiti-list-unique card for detection.
_CORE = {ABRA, KADABRA, ALAKAZAM, DUNSPARCE, DUDUNSPARCE, FEZANDIPITI}
# Cards that uniquely distinguish THIS list from the sibling dunsparce list (which shares the core).
_FEZ_DISTINCT = {FEZANDIPITI, LILLIE_DET, WONDROUS_PATCH, XEROSIC}

ALAKAZAM_ENERGY_GOAL = 1   # Powerful Hand costs exactly one {P}; more energy is just lost card value
P_ENERGY = {BASIC_P, TELEPATH_P}

# Full 60-card decklist for the lethal verifier's determinization while piloting this deck.
FEZANDIPITI_DECK = (
    [ABRA] * 4 + [KADABRA] * 4 + [ALAKAZAM] * 3 + [DUNSPARCE] * 3 + [DUDUNSPARCE] * 3 + [FEZANDIPITI]
    + [BUDDY_POFFIN] * 4 + [POKE_PAD] * 4 + [DAWN] * 4 + [HILDA] * 4 + [RARE_CANDY] * 3
    + [LILLIE_DET] * 4 + [BOSS_ORDERS] * 3 + [NIGHT_STRETCHER] * 2 + [XEROSIC] + [SACRED_ASH]
    + [ENHANCED_HAMMER] * 2 + [WONDROUS_PATCH] + [LANA_AID]
    + [TELEPATH_P] * 4 + [BASIC_P] * 3 + [ENRICHING]
)
assert len(FEZANDIPITI_DECK) == 60, len(FEZANDIPITI_DECK)

KEY_PIECES = {ALAKAZAM, KADABRA, ABRA, DUDUNSPARCE, DUNSPARCE, RARE_CANDY, FEZANDIPITI}
USEFUL_PIECES = {BUDDY_POFFIN, POKE_PAD, HILDA, DAWN, BOSS_ORDERS, NIGHT_STRETCHER, LANA_AID,
                 LILLIE_DET, WONDROUS_PATCH}
BASIC_ENERGY = {BASIC_P}

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

# This combo deck must assemble a Stage-2 line before it can do anything, so the extra setup tempo
# of the first turn outweighs going second's one card (measured better for the sibling list). Go
# first — and the 210HP Fezandipiti wall covers the downside of taking the first hit on turn 2.
_GO_FIRST = True

# Lillie's Determination resets the hand to 6 (8 at exactly 6 prizes). Above this hand size it is a
# net loss of cards, so we only refuel with it when the hand is at or below this threshold.
_LILLIE_REFUEL_AT = 4

# ── engine tables (loaded once) ────────────────────────────────────────────────────────────────
try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}
try:
    _ATK = {a.attackId: a for a in all_attack()}
except Exception:
    _ATK = {}


def _meta(card_id):
    return _CARD.get(card_id)


def _is_basic_pokemon(card_id) -> bool:
    cd = _meta(card_id)
    if cd is not None:
        try:
            return bool(cd.basic) and cd.cardType == CardType.POKEMON
        except Exception:
            pass
    return card_id in (ABRA, DUNSPARCE, FEZANDIPITI)


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


def _energy_count(p) -> int:
    try:
        return len(getattr(p, "energyCards", None) or getattr(p, "energies", None) or [])
    except Exception:
        return 0


def _p_energy_count(p) -> int:
    """Energies attached that provide {P} (i.e. can pay Powerful Hand)."""
    try:
        n = 0
        for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
            if _id(c) in P_ENERGY:
                n += 1
        return n
    except Exception:
        return 0


# Dragapult ex spread/aggro line (Dreepy -> Drakloak -> Dragapult ex). Phantom Dive deals 200 to our
# Active AND spreads 6 damage counters onto our bench, picking off the fragile Abra (50HP) /
# Dunsparce (70HP) pieces before we can assemble + promote Alakazam. We adapt against this.
DRAGAPULT_LINE = {119, 120, 121}


def _facing_spread(state, me_i: int) -> bool:
    """True when the opponent is a bench-spread aggro deck (Dragapult), detected from its revealed
    board/discard. Gated inside this specialist, and keyed only on the Dragapult line, so it can
    never alter how we pilot any other deck or how the deck plays against any other opponent."""
    try:
        opp = state.players[1 - me_i]
        for p in (list(opp.active or []) + list(opp.bench or [])):
            if p is None:
                continue
            if _id(p) in DRAGAPULT_LINE:
                return True
            for c in (getattr(p, "preEvolution", None) or []):
                if _id(c) in DRAGAPULT_LINE:
                    return True
        for c in (opp.discard or []):
            if _id(c) in DRAGAPULT_LINE:
                return True
    except Exception:
        return False
    return False


def is_fezandipiti_deck(state, me_i: int) -> bool:
    """True iff our side is piloting THIS list: an Alakazam/Dunsparce-core Pokémon AND a card unique
    to the Fezandipiti list are both visible on our side. The conjunction is disjoint from every
    other deck (notably the sibling dunsparce list, which has the core but none of the four
    distinguishers, and Iono, which has Lillie's Determination but no core), so this never collides
    with another specialist."""
    try:
        me = state.players[me_i]
        zones = (list(me.active or []) + list(me.bench or [])
                 + list(me.hand or []) + list(me.discard or []))
        has_core = any(_id(c) in _CORE for c in zones)
        if not has_core:
            return False
        return any(_id(c) in _FEZ_DISTINCT for c in zones)
    except Exception:
        return False


def _my_active(state, me_i):
    try:
        a = state.players[me_i].active
        if a and a[0] is not None:
            return a[0]
    except Exception:
        pass
    return None


def _my_bench(state, me_i):
    try:
        return [b for b in state.players[me_i].bench if b is not None]
    except Exception:
        return []


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
        op = state.players[1 - me_i].active
        if op and op[0] is not None:
            return op[0]
    except Exception:
        pass
    return None


def _opp_bench(state, me_i):
    try:
        return [b for b in state.players[1 - me_i].bench if b is not None]
    except Exception:
        return []


def _hand_size(state, me_i) -> int:
    try:
        me = state.players[me_i]
        h = me.hand
        if h is not None:
            return len(h)
        return int(getattr(me, "handCount", 0) or 0)
    except Exception:
        return 0


def _opponent_value(p) -> float:
    """How tempting an opponent Pokémon is as a target (prizes + investment)."""
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
    v += _energy_count(p) * 35
    v += (getattr(p, "hp", 0) or 0) // 10
    return v


def _prize_count_for(p) -> int:
    cd = _meta(_id(p))
    if cd is None:
        return 1
    return 3 if getattr(cd, "megaEx", False) else 2 if getattr(cd, "ex", False) else 1


def _eff_damage(active, attack_id, opp_active, state, me_i) -> int:
    """Effective damage to the opponent's Active. The two attacks whose damage lives in TEXT (field
    `damage` == 0) are special-cased: Powerful Hand (20 x our hand size) and Cruel Arrow (100)."""
    if attack_id == POWERFUL_HAND:
        return 20 * _hand_size(state, me_i)
    if attack_id == CRUEL_ARROW:
        return CRUEL_ARROW_DAMAGE
    try:
        from scorer import _attack_damage
        d = _attack_damage(active, attack_id, opp_active)
        if d:
            return d
    except Exception:
        pass
    atk = _ATK.get(attack_id)
    return (atk.damage or 0) if atk is not None else 0


def _alakazam_ready(state, me_i) -> bool:
    """Alakazam is Active with a {P} energy -> Powerful Hand is online this turn."""
    a = _my_active(state, me_i)
    return _id(a) == ALAKAZAM and _p_energy_count(a) >= ALAKAZAM_ENERGY_GOAL


def _p_available(state, me_i) -> bool:
    """A {P} energy is already in reach for the Alakazam line: attached to a line piece, or sitting
    in hand ready to attach (Powerful Hand needs exactly one)."""
    a = _my_active(state, me_i)
    if _id(a) in ALAKAZAM_LINE and _p_energy_count(a) >= 1:
        return True
    for b in _my_bench(state, me_i):
        if _id(b) in ALAKAZAM_LINE and _p_energy_count(b) >= 1:
            return True
    try:
        return any(_id(c) in P_ENERGY for c in (state.players[me_i].hand or []))
    except Exception:
        return False


def _swing_mode(state, me_i) -> bool:
    """We have an ENERGISED Alakazam in play (Active OR benched) — a fat-handed Powerful Hand is
    imminent. In this mode we STOP playing hand-shrinking cards: every held card is +20 damage."""
    a = _my_active(state, me_i)
    if _id(a) == ALAKAZAM and _p_energy_count(a) >= ALAKAZAM_ENERGY_GOAL:
        return True
    for b in _my_bench(state, me_i):
        if _id(b) == ALAKAZAM and _p_energy_count(b) >= ALAKAZAM_ENERGY_GOAL:
            return True
    return False


def _has_attack_option(obs) -> bool:
    try:
        return any(o.type == OptionType.ATTACK for o in obs.select.option)
    except Exception:
        return False


def _good_gust_target(state, me_i):
    """A benched opponent we can KO with Powerful Hand this turn and that is juicier than their
    Active (a powered-up / multi-prize backup hiding behind a chip body). Else None."""
    active = _my_active(state, me_i)
    if _id(active) != ALAKAZAM:
        return None
    dmg = 20 * _hand_size(state, me_i)
    if dmg <= 0:
        return None
    oa = _opp_active(state, me_i)
    active_val = (_opponent_value(oa) + _prize_count_for(oa) * 100.0) if oa is not None else -1.0
    active_koable = oa is not None and dmg >= (oa.hp or 0)
    best, best_val = None, 0.0
    for b in _opp_bench(state, me_i):
        if dmg >= (b.hp or 0):
            val = _opponent_value(b) + _prize_count_for(b) * 100.0
            if (not active_koable) or val > active_val + 60.0:
                if val > best_val:
                    best, best_val = b, val
    return best


def _wondrous_patch_useful(state, me_i) -> bool:
    """Wondrous Patch helps only when a Basic {P} sits in the discard AND a benched Alakazam-line
    body can receive it (pre-fuelling the next attacker off the discard)."""
    try:
        if not any(_id(c) == BASIC_P for c in (state.players[me_i].discard or [])):
            return False
        for b in _my_bench(state, me_i):
            if _id(b) in ALAKAZAM_LINE and _p_energy_count(b) < ALAKAZAM_ENERGY_GOAL:
                return True
    except Exception:
        return False
    return False


# ── MAIN-turn scoring ─────────────────────────────────────────────────────────────────────────
# Priority: EVOLVE-toward-Alakazam / Rare-Candy > draw-ENGINE (Run Away Draw / Psychic Draw / Flip
# the Script) > hand-GROWING supporters (Dawn/Hilda, Lillie when small) > Boss (for a KO) >
# attach ONE {P} to Alakazam > neutral digs > hand-SHRINKING plays > ATTACK (Powerful Hand at
# 20 x hand) > END. When Alakazam can swing this turn, hand-shrinkers drop below END.
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type
    swing = _alakazam_ready(state, me_i) and _has_attack_option(obs)

    if t == OptionType.EVOLVE:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        if cid == ALAKAZAM:
            return 2600.0   # the attacker (and Psychic Draw)
        if cid == KADABRA:
            return 2450.0   # progress toward Alakazam (and Psychic Draw)
        if cid == DUDUNSPARCE:
            return 2350.0   # the repeatable Run Away Draw engine
        return 2300.0

    if t == OptionType.ABILITY:
        # Run Away Draw (+3, recycles) / Psychic Draw (on evolve) / Flip the Script (draw 3 on a KO):
        # pure, repeatable card advantage — the engine only offers a usable ability, and all three
        # GROW Powerful Hand, so fire any of them before committing or attacking.
        return 2280.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        bench_n = len(_my_bench(state, me_i))
        sup_done = bool(getattr(state, "supporterPlayed", False))
        spread = _facing_spread(state, me_i)
        hand_n = _hand_size(state, me_i)
        # Once an energised Alakazam exists, preserve the hand for Powerful Hand: HOLD hand-shrinking
        # cards (score below END) so the imminent swing stays maximal.
        hold = swing or _swing_mode(state, me_i)

        # Rare Candy: Abra -> Alakazam, skipping Kadabra. Best evolve when an Abra is in play and an
        # Alakazam is in hand to land it on; otherwise no target -> don't waste it.
        if cid == RARE_CANDY:
            abra_in_play = _id(active) == ABRA or any(_id(b) == ABRA for b in _my_bench(state, me_i))
            alakazam_in_hand = any(_id(c) == ALAKAZAM for c in (state.players[me_i].hand or []))
            return 2550.0 if (abra_in_play and alakazam_in_hand) else -1.0

        # Hand-GROWING supporters: they net cards INTO hand -> bigger Powerful Hand, good even on the
        # swing turn. One supporter per turn (engine-gated).
        if cid == DAWN:                    # search Basic + Stage1 + Stage2 to hand: +3 (net +2)
            return -1.0 if sup_done else 1950.0
        if cid == HILDA:                   # search Evolution + Energy to hand: +2 (net +1)
            if sup_done:
                return -1.0
            # Vs aggro/spread the race is decided by the FIRST Powerful Hand, usually gated on a
            # missing {P} (only 8 in the deck). Hilda is our energy tutor that also grabs an Alakazam.
            if spread and not _p_available(state, me_i):
                return 2050.0
            return 1850.0
        # Lillie's Determination: a *refuel* to a fixed 6/8 — only when the hand is small (else it
        # SHRINKS our hand), and never right before a swing. When small it is our biggest dig.
        if cid == LILLIE_DET:
            if sup_done or hold:
                return -1.0
            if hand_n <= _LILLIE_REFUEL_AT:
                return 2000.0          # refuel a starved hand: best supporter when we are low
            return -1.0                 # a healthy hand keeps its cards for Powerful Hand
        if cid == LANA_AID:                # recover up to 3 pieces from discard to hand
            if sup_done:
                return -1.0
            try:
                recoverable = sum(1 for c in (state.players[me_i].discard or [])
                                  if _id(c) in _CORE or _id(c) in BASIC_ENERGY)
            except Exception:
                recoverable = 0
            return 1700.0 if recoverable else 80.0

        # Boss's Orders: gust + KO a juicier benched target for the prize race.
        if cid == BOSS_ORDERS:
            if sup_done:
                return -1.0
            return 2000.0 if _good_gust_target(state, me_i) is not None else -1.0

        # Xerosic's Machinations: strip the opponent to 3 cards. Ranked below all of our own
        # hand-growers (our cards beat denying theirs); only worth a supporter when we are already
        # set up, are not refuelling, and the opponent actually has a hand worth stripping.
        if cid == XEROSIC:
            if sup_done or hold:
                return -1.0
            try:
                opp_hand = int(getattr(state.players[1 - me_i], "handCount",
                                       len(state.players[1 - me_i].hand or [])) or 0)
            except Exception:
                opp_hand = 0
            if opp_hand <= 4 or hand_n <= _LILLIE_REFUEL_AT:
                return -1.0            # save the supporter for our own draw when low / no good target
            return 1600.0 if _alakazam_ready(state, me_i) else 1100.0

        # Pokémon from hand develop the board.
        if _is_basic_pokemon(cid):
            # Fezandipiti ex: a single 210HP wall + Flip the Script. Bench it early as the backstop
            # the fragile line hides behind; once an energised Alakazam is online it costs a
            # Powerful-Hand card, so only drop it then if the bench would otherwise be empty.
            if cid == FEZANDIPITI:
                if any(_id(b) == FEZANDIPITI for b in _my_bench(state, me_i)) or _id(active) == FEZANDIPITI:
                    return -1.0        # only one in the deck — never a second copy
                if hold:
                    return 1750.0 if bench_n <= 0 else -1.0
                if bench_n <= 0:
                    return 1800.0      # an empty bench wants a body; the 210HP wall is a fine one
                # A sturdy backstop, but develop the combo basics (Abra/Dunsparce) first — rank it
                # just below them so the Stage-2 line and the draw engine come down ahead of it.
                return 1300.0
            # Bench bodies feed the draw engine (Dunsparce) and the evolution line (Abra).
            if hold:
                if bench_n <= 0:
                    return 1800.0
                if spread and bench_n < 2 and cid == DUNSPARCE:
                    return 900.0       # a tanky 140HP-to-be backup so a spread turn can't wipe us
                return -1.0
            if bench_n <= 0:
                return 1800.0
            if spread:
                if cid == DUNSPARCE:
                    return 1500.0
                abra_n = (1 if _id(active) == ABRA else 0) + sum(
                    1 for b in _my_bench(state, me_i) if _id(b) == ABRA)
                return 1500.0 if abra_n < 2 else 250.0
            if bench_n < 3:
                return 1500.0
            return 500.0

        # Buddy-Buddy Poffin: 2 Basics to BENCH (Abra/Dunsparce) — board engine, but -1 hand.
        if cid == BUDDY_POFFIN:
            if hold:
                return -1.0 if bench_n > 0 else 1750.0
            if bench_n <= 1:
                return 1750.0
            if bench_n <= 3:
                return 1550.0
            return 250.0

        # Poké Pad: dig a Pokémon to hand (net-0 hand) — safe to dig for the line / Dunsparce.
        if cid == POKE_PAD:
            return 1500.0

        # Wondrous Patch: accelerate a Basic {P} from discard onto a benched Alakazam-line body so it
        # can swing the turn it is promoted. -1 hand, so hold it once the swing is already loaded.
        if cid == WONDROUS_PATCH:
            if hold:
                return -1.0
            return 1480.0 if _wondrous_patch_useful(state, me_i) else -1.0

        # Night Stretcher: recover a Pokémon / Basic Energy from discard to hand (net-0).
        if cid == NIGHT_STRETCHER:
            try:
                if any(_id(c) in _CORE or _id(c) in BASIC_ENERGY
                       for c in (state.players[me_i].discard or [])):
                    return 1400.0
            except Exception:
                pass
            return 200.0

        # Enhanced Hammer: discard opponent Special Energy — disruption, but -1 hand.
        if cid == ENHANCED_HAMMER:
            if hold:
                return -1.0
            opp = state.players[1 - me_i]
            has_special = False
            try:
                for p in (list(opp.active or []) + list(opp.bench or [])):
                    if p is None:
                        continue
                    for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
                        cd = _meta(_id(c))
                        if cd is not None and cd.cardType == CardType.SPECIAL_ENERGY:
                            has_special = True
                            break
            except Exception:
                pass
            return 900.0 if has_special else 60.0

        # Sacred Ash: anti-deckout recycling (matters very late) — and -1 hand.
        if cid == SACRED_ASH:
            try:
                if (state.players[me_i].deckCount or 0) <= 6:
                    return 700.0       # imminent deck-out overrides hand preservation
            except Exception:
                pass
            if hold:
                return -1.0
            return 80.0

        return 500.0

    if t == OptionType.ATTACH:
        active = _my_active(state, me_i)
        card = _get(obs, o.area, o.index, me_i)
        is_p = _id(card) in P_ENERGY
        if o.inPlayArea == AreaType.ACTIVE:
            if _id(active) == ALAKAZAM:
                # Need exactly one {P}. Once paid, an extra energy is a wasted Powerful-Hand card.
                if _p_energy_count(active) < ALAKAZAM_ENERGY_GOAL:
                    return 1700.0 if is_p else 200.0
                return 20.0
            if _id(active) in ALAKAZAM_LINE:
                return 1500.0 if is_p else 300.0   # pre-fuel the soon-to-be Alakazam ({P} carries)
            if _id(active) == DUDUNSPARCE:
                return 900.0                       # Land Crush backup (rarely the plan)
            if _id(active) == FEZANDIPITI:
                return 400.0                       # Cruel Arrow backup; secondary to the line
            return 600.0
        if o.inPlayArea == AreaType.BENCH:
            tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            if _id(tgt) in ALAKAZAM_LINE:
                if _p_energy_count(tgt) < ALAKAZAM_ENERGY_GOAL:
                    return 1300.0 if is_p else 200.0
                return 20.0
            return 500.0
        return 500.0

    if t == OptionType.ATTACK:
        active = _my_active(state, me_i)
        oa = _opp_active(state, me_i)
        dmg = _eff_damage(active, o.attackId, oa, state, me_i)
        score = 100.0 + min(max(dmg, 0), 300) * 0.3
        if o.attackId == POWERFUL_HAND:
            score += 30.0   # the deck's win condition: prefer it over the chip / snipe backups
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 200.0  # KO
            try:
                opp = state.players[1 - me_i]
                if len(opp.prize) <= _prize_count_for(oa):
                    return 50000.0  # this KO takes their last prize(s) -> game-winning
            except Exception:
                pass
        return score

    if t == OptionType.RETREAT:
        # Stay put as Alakazam; only retreat to promote a benched, ready Alakazam over a chip body
        # (e.g. swap the Fezandipiti wall out for the loaded attacker).
        active = _my_active(state, me_i)
        if _id(active) != ALAKAZAM and _bench_has_id(state, me_i, ALAKAZAM):
            return 120.0
        return -1.0

    if t == OptionType.END:
        return 0.0
    if t == OptionType.YES:
        return 5.0
    if t == OptionType.NO:
        return 3.0
    return 1.0


# ── forced sub-selection scoring (base high so we always make a legal move) ─────────────────────
def score_sub(obs, o, me_i, context) -> float:
    state = obs.current
    opp_i = 1 - me_i
    t = o.type
    score = 2000.0

    if t == OptionType.NUMBER:
        return score + (getattr(o, "number", 0) or 0)   # take the bigger number (draw more, etc.)

    if t == OptionType.YES:
        if context == SelectContext.IS_FIRST:
            return score + (100.0 if _GO_FIRST else 0.0)
        return score + 100.0
    if t == OptionType.NO:
        if context == SelectContext.IS_FIRST:
            return score + (0.0 if _GO_FIRST else 100.0)
        return score
    if t == OptionType.SPECIAL_CONDITION:
        return 2000.0

    if t in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD, OptionType.ENERGY):
        pidx = getattr(o, "playerIndex", me_i)
        card = _get(obs, o.area, o.index, pidx)
        cid = _id(card)

        # Heal / damage removal: most-damaged friendly mon.
        if context in HEAL_CTX:
            if isinstance(card, Pokemon):
                score += max(0, (getattr(card, "maxHp", 0) or 0) - (getattr(card, "hp", 0) or 0))
            return score

        # Damage / boss / gust / Cruel Arrow targeting: opponent's most valuable, prefer a body we
        # can KO outright (Cruel Arrow snipes for 100), then their Active.
        if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
                       SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET):
            if isinstance(card, Pokemon) and pidx == opp_i:
                score += _opponent_value(card)
                if (getattr(card, "hp", 0) or 0) <= CRUEL_ARROW_DAMAGE:
                    score += 220.0     # a clean snipe KO is worth more than chipping the Active
                if o.area == AreaType.ACTIVE:
                    score += 250.0
            elif isinstance(card, Pokemon):
                score -= _opponent_value(card)
            return score

        # Discard / pitch / give-up: dump spare basic energy first; protect the line + Rare Candy.
        if context in GIVE_UP_CTX:
            cd = _meta(cid)
            if cd is not None:
                if cid in BASIC_ENERGY:
                    return score + 60.0
                if cid in KEY_PIECES or cd.cardType in (CardType.POKEMON, CardType.SUPPORTER):
                    return score - 250.0
                if cd.cardType in (CardType.SPECIAL_ENERGY, CardType.TOOL):
                    return score - 120.0
                if cid in USEFUL_PIECES:
                    return score - 80.0
            return score

        # Search / fetch targets (TO_HAND from deck) + placement: prioritise the engine pieces.
        if isinstance(card, Pokemon):
            if pidx == opp_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 200.0
                return score
            # Our own mon (setup active, evolve, fetch, switch-in).
            if cid == ALAKAZAM:
                score += 320.0     # the attacker is the best fetch / placement
            elif cid == KADABRA:
                score += 200.0
            elif cid == ABRA:
                score += 170.0
                if len(_my_bench(state, me_i)) == 0:
                    score += 200.0  # empty bench -> a body is urgent
            elif cid == DUDUNSPARCE:
                score += 150.0     # the draw engine
            elif cid == DUNSPARCE:
                score += 130.0
                if len(_my_bench(state, me_i)) == 0:
                    score += 200.0
            elif cid == FEZANDIPITI:
                # The 210HP wall + Flip the Script: a benched backstop the fragile Stage-2 line
                # assembles behind. We do NOT lead with it as the opening Active — Fezandipiti can't
                # fire Powerful Hand, so an Abra/Dunsparce start (which evolves / draws) is better;
                # keep it modest so the combo pieces are preferred for the Active slot.
                if context in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.TO_ACTIVE):
                    score += 60.0
                else:
                    score += 140.0
            if context in PLACEMENT_CTX:
                score += 400.0
            return score

        # Non-Pokémon fetch (energy / supporter / item tutoring).
        cd = _meta(cid)
        if cd is not None:
            active = _my_active(state, me_i)
            need_p = _id(active) in ALAKAZAM_LINE and _p_energy_count(active) < ALAKAZAM_ENERGY_GOAL
            if cid in P_ENERGY:
                score += 120.0 if need_p else 30.0
            elif cid == RARE_CANDY:
                score += 90.0
            elif cid in (DAWN, HILDA, POKE_PAD, LILLIE_DET):
                score += 70.0
        return score

    return score

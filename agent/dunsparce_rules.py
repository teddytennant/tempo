"""Alakazam "Powerful Hand" / Dudunsparce draw-engine specialist (id-gated), consulted by
agent/scorer.best_options.

The deck (data/decks/dunsparce.csv, team TrustHub ~1320) is NOT a beatdown — it is a *draw-combo*
deck whose whole win condition is one attack:

  • Alakazam (743, Stage-2 P, 140HP). "Powerful Hand" (1072): {P} -> place 2 damage counters on the
    opponent's Active for EACH card in your hand. So it deals 20 x (hand size) damage, as *damage
    counters* (fixed; ignores weakness/resistance AND damage-prevention walls). Alakazam is non-ex,
    so the Crustle wall's ex-damage immunity does nothing against it — this is the one deck that
    breaks Crustle.
  • The rest of the deck exists to (a) reach Alakazam fast and (b) make the hand HUGE the turn it
    swings: Abra 741 -> Kadabra 742 -> Alakazam 743 (Rare Candy 1079 skips Kadabra), where Kadabra &
    Alakazam each draw on evolution (Psychic Draw); Dunsparce 305 -> Dudunsparce 66 whose Run Away
    Draw ability draws 3 and shuffles itself back (a repeatable +3); plus Dawn 1231 / Hilda 1225 /
    Poké Pad 1152 / Buddy-Buddy Poffin 1086 search engines.

Why the generic scorer misplays it (and why this specialist beats it):
  1. Powerful Hand's `damage` field is 0 (it places damage counters via text), so the generic scorer
     values the *game-winning* attack at its 100.0 base and never sees a KO/lethal — here we score it
     at its true 20 x handCount.
  2. The generic scorer empties the hand every turn (plays every item/supporter) -> a tiny Powerful
     Hand. Here, once Alakazam is the loaded attacker, we HOLD hand-shrinking plays and only fire
     card-DRAWING effects, so the hand (and the damage) stays fat into the swing.
  3. It under-rates the draw engine (abilities at 400) and over-attaches energy. Powerful Hand needs
     exactly one {P}; everything else is card advantage.

`is_dunsparce_deck(state, me_i)` fires only when an Abra/Kadabra/Alakazam or Dunsparce/Dudunsparce is
on OUR side (those Pokémon appear in no other deck except the sibling Alakazam list), so for Crustle,
Lucario, Starmie, etc. none of this triggers — the generic + other specialist paths are untouched.
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_attack, all_card_data

# ── deck card IDs (verified via all_card_data against data/decks/dunsparce.csv) ─────────────────
ABRA = 741          # Basic P, 50HP   -> Kadabra
KADABRA = 742       # Stage1 P, 80HP  -> Alakazam; Psychic Draw on evolve
ALAKAZAM = 743      # Stage2 P, 140HP; Powerful Hand (1072). THE attacker; Psychic Draw on evolve
DUNSPARCE = 305     # Basic C, 70HP   -> Dudunsparce
DUDUNSPARCE = 66    # Stage1 C, 140HP; Run Away Draw (draw 3, shuffle self back) — the draw engine

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
BATTLE_CAGE = 1264      # stadium: prevent damage counters on Benched Pokémon (both sides)
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

ALAKAZAM_LINE = {ABRA, KADABRA, ALAKAZAM}
DRAW_ENGINE = {DUNSPARCE, DUDUNSPARCE}
# Pokémon that uniquely identify the deck — none appear in any deck but the sibling Alakazam lists.
_SIGNATURE = {ABRA, KADABRA, ALAKAZAM, DUNSPARCE, DUDUNSPARCE}

ALAKAZAM_ENERGY_GOAL = 1   # Powerful Hand costs exactly one {P}; more energy is just lost card value
P_ENERGY = {BASIC_P, TELEPATH_P}

# Full 60-card decklist for the lethal verifier's determinization while piloting this deck.
DUNSPARCE_DECK = (
    [ALAKAZAM] * 4 + [KADABRA] * 4 + [ABRA] * 4 + [DUDUNSPARCE] * 3 + [DUNSPARCE] * 4
    + [BUDDY_POFFIN] * 4 + [POKE_PAD] * 4 + [RARE_CANDY] * 4 + [HILDA] * 4 + [ENHANCED_HAMMER] * 4
    + [NIGHT_STRETCHER] * 3 + [SACRED_ASH] * 1 + [DAWN] * 4 + [BOSS_ORDERS] * 3 + [LANA_AID] * 1
    + [BATTLE_CAGE] * 1 + [TELEPATH_P] * 4 + [BASIC_P] * 3 + [ENRICHING] * 1
)
assert len(DUNSPARCE_DECK) == 60, len(DUNSPARCE_DECK)

KEY_PIECES = {ALAKAZAM, KADABRA, ABRA, DUDUNSPARCE, DUNSPARCE, RARE_CANDY}   # never pitch if avoidable
USEFUL_PIECES = {BUDDY_POFFIN, POKE_PAD, HILDA, DAWN, BOSS_ORDERS, NIGHT_STRETCHER, LANA_AID}
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

# This combo deck must assemble a Stage-2 line (Abra -> Kadabra -> Alakazam) before it can do
# anything, so the extra setup tempo of the first turn outweighs going second's one card. Going
# first measured clearly better in self-play (≈63% vs ≈57% over 120/160 games). So: go first.
_GO_FIRST = True

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
    return card_id in (ABRA, DUNSPARCE)


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


def is_dunsparce_deck(state, me_i: int) -> bool:
    """True iff our side is piloting the Alakazam / Dudunsparce line (one of its mons is visible)."""
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
    """Effective damage to the opponent's Active. Powerful Hand is the special case the generic
    scorer cannot see: 20 x our current hand size, as fixed damage counters (no weakness/resist)."""
    if attack_id == POWERFUL_HAND:
        return 20 * _hand_size(state, me_i)
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


# ── MAIN-turn scoring ─────────────────────────────────────────────────────────────────────────
# Priority: EVOLVE-toward-Alakazam / Rare-Candy > draw-ENGINE (Run Away Draw / Psychic Draw) >
# hand-GROWING supporters (Dawn/Hilda) > Boss (for a KO) > attach ONE {P} to Alakazam > neutral digs
# > hand-SHRINKING plays > ATTACK (Powerful Hand, valued at 20 x hand) > END.
# When Alakazam is loaded and can swing this turn, hand-shrinking plays drop below END so the hand
# (and thus Powerful Hand's damage) stays as large as possible into the attack.
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
        # Run Away Draw (+3, recycles) / Psychic Draw (on evolve): pure, repeatable card advantage —
        # this engine is the deck. Fire it before committing or attacking; it GROWS Powerful Hand.
        return 2280.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        bench_n = len(_my_bench(state, me_i))
        sup_done = bool(getattr(state, "supporterPlayed", False))
        stad_done = bool(getattr(state, "stadiumPlayed", False))

        # Rare Candy: Abra -> Alakazam, skipping Kadabra. Treat like the best evolve when an Abra is in
        # play and an Alakazam is in hand to land it on; otherwise it has no target -> don't waste it.
        if cid == RARE_CANDY:
            abra_in_play = _id(active) == ABRA or any(_id(b) == ABRA for b in _my_bench(state, me_i))
            alakazam_in_hand = any(_id(c) == ALAKAZAM for c in (state.players[me_i].hand or []))
            return 2550.0 if (abra_in_play and alakazam_in_hand) else -1.0

        # Hand-GROWING supporters: they net cards INTO hand, so they make Powerful Hand bigger — good
        # even on the swing turn. One supporter per turn (engine-gated).
        if cid == DAWN:                    # search Basic + Stage1 + Stage2 to hand: +3 (net +2)
            return -1.0 if sup_done else 1950.0
        if cid == HILDA:                   # search Evolution + Energy to hand: +2 (net +1)
            return -1.0 if sup_done else 1850.0
        if cid == LANA_AID:                # recover up to 3 pieces from discard to hand
            if sup_done:
                return -1.0
            try:
                recoverable = sum(1 for c in (state.players[me_i].discard or [])
                                  if _id(c) in _SIGNATURE or _id(c) in BASIC_ENERGY)
            except Exception:
                recoverable = 0
            return 1700.0 if recoverable else 80.0

        # Boss's Orders: gust + KO a juicier benched target for the prize race.
        if cid == BOSS_ORDERS:
            if sup_done:
                return -1.0
            return 2000.0 if _good_gust_target(state, me_i) is not None else -1.0

        # Energy from hand is handled under ATTACH; PLAY of a Pokémon develops the board.
        if _is_basic_pokemon(cid):
            # Bench bodies feed the draw engine (Dunsparce) and the evolution line (Abra). Develop
            # early; but on the swing turn a body costs a Powerful-Hand card, so hold it.
            if swing:
                return 40.0
            if bench_n <= 0:
                return 1800.0
            if bench_n < 3:
                return 1500.0
            return 500.0

        # Buddy-Buddy Poffin: 2 Basics to BENCH (Abra/Dunsparce) — the board engine, but -1 hand.
        if cid == BUDDY_POFFIN:
            if swing:
                return 40.0                # don't shrink the hand on the swing turn
            if bench_n <= 1:
                return 1750.0
            if bench_n <= 3:
                return 1550.0
            return 250.0

        # Poké Pad: dig a Pokémon to hand (net-0 hand) — safe to dig for the Alakazam line / Dunsparce.
        if cid == POKE_PAD:
            return 1500.0
        # Night Stretcher: recover a Pokémon / Basic Energy from discard to hand (net-0).
        if cid == NIGHT_STRETCHER:
            try:
                if any(_id(c) in _SIGNATURE or _id(c) in BASIC_ENERGY
                       for c in (state.players[me_i].discard or [])):
                    return 1400.0
            except Exception:
                pass
            return 200.0

        # Enhanced Hammer: discard opponent Special Energy — disruption, but -1 hand.
        if cid == ENHANCED_HAMMER:
            if swing:
                return 40.0
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
            if swing:
                return 30.0
            try:
                if (state.players[me_i].deckCount or 0) <= 6:
                    return 700.0
            except Exception:
                pass
            return 80.0

        # Battle Cage: stadium, shields benches from spread counters. Situational; -1 hand.
        if cid == BATTLE_CAGE:
            if swing or stad_done:
                return -1.0 if stad_done else 30.0
            return 400.0

        return 500.0

    if t == OptionType.ATTACH:
        active = _my_active(state, me_i)
        card = _get(obs, o.area, o.index, me_i)
        is_p = _id(card) in P_ENERGY
        if o.inPlayArea == AreaType.ACTIVE:
            if _id(active) == ALAKAZAM:
                # Need exactly one {P}. Once it's paid, an extra energy is a wasted Powerful-Hand card.
                if _p_energy_count(active) < ALAKAZAM_ENERGY_GOAL:
                    return 1700.0 if is_p else 200.0   # only a {P} energy actually powers the attack
                return 20.0
            if _id(active) in ALAKAZAM_LINE:
                return 1500.0 if is_p else 300.0       # pre-fuel the soon-to-be Alakazam ({P} carries)
            if _id(active) == DUDUNSPARCE:
                return 900.0                           # Land Crush backup (rarely the plan)
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
            score += 30.0   # the deck's win condition: prefer it over the chip backup attacks
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
        # Stay put as Alakazam; only retreat to promote a benched, ready Alakazam over a chip body.
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

        # Damage / boss / gust targeting: opponent's most valuable, prefer their Active.
        if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
                       SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET):
            if isinstance(card, Pokemon) and pidx == opp_i:
                score += _opponent_value(card)
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
            if context in PLACEMENT_CTX:
                score += 400.0
            return score

        # Non-Pokémon fetch (energy / supporter tutoring).
        cd = _meta(cid)
        if cd is not None:
            active = _my_active(state, me_i)
            need_p = _id(active) in ALAKAZAM_LINE and _p_energy_count(active) < ALAKAZAM_ENERGY_GOAL
            if cid in P_ENERGY:
                score += 120.0 if need_p else 30.0
            elif cid == RARE_CANDY:
                score += 90.0
            elif cid in (DAWN, HILDA, POKE_PAD):
                score += 70.0
        return score

    return score

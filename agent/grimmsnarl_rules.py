"""Marnie's Grimmsnarl ex specialist scoring (id-gated), consulted by agent/scorer.best_options.

The deck (data/decks/mined/The_Debauchery_Tea_Party.csv) is the exact 60 cards of the current #1
team, mined from their winning replays — the list ALL of the top-3 teams pilot (July 2026 meta).
Every scoring rule below is calibrated against 2,020 winning games / ~236k decisions by the three
elite Grimmsnarl pilots (Tea Party / tonakaiiii / kazuki0123), mined from the official episode
datasets (see the pattern report in the 2026-07-17 session). The engine is one ability:

  • Marnie's Grimmsnarl ex (648, Stage-2 ex, 320HP). "Punk Up": when played from hand to evolve
    (including via Rare Candy), search the deck for up to 5 Basic {D} Energy and attach them to
    your MARNIE'S Pokémon in any way (the engine offers only 646/647/648 as targets). One evolve
    = a fueled 320HP attacker. Shadow Bullet (937, {D}{D}): 180 + 30 to one benched opponent.
  • Munkidori (112). "Adrena-Brain": with a {D} attached, move up to 3 damage counters from one
    of OUR Pokémon to one of THEIRS, once per turn PER MUNKIDORI. The elite pilots use it ~5.8x
    a game, 81% sourcing from their own Grimmsnarl — it is primarily a HEALING engine (a 320HP
    attacker that sheds 30-90/turn), secondarily a finisher (counters ignore walls/weakness).
    Its own attack needs real {P} the list does not run: manual energy attaches go to Munkidori
    ~95% of the time (Punk Up cannot legally feed it).
  • Dunsparce 305 -> Dudunsparce 66: "Run Away Draw" (draw 3, shuffle self back), used at ≥97%
    whenever available until deckCount <= 3.
  • Support: Poffin / Poké Pad / Dawn / Spikemuth Gym / Lillie / Rare Candy / Boss / Hero's Cape.

Elite-verified priorities encoded here: always go FIRST; stadium down first; evolve BEFORE
attaching (1373:97); Rare Candy the turn it is live (mode: own-turn 2); Morgrem evolve LAST in
the turn (it kills the mon's Rare-Candy line for the turn — supporters/searches first may find
the Candy); Boss -> Adrena-Brain -> attack ordering (456:79, 9871:0); NEVER end the turn with an
attack available (5:9270); Punk Up always accepted, energy count scaled by remaining deck.

`is_grimmsnarl_deck(state, me_i)` fires only on cards unique to this list (Marnie's line 646/647/
648, Spikemuth Gym 1259, Risky Ruins 1260) and LATCHES for the rest of the game, so no other deck
routes through here. It must be consulted BEFORE the cinderace/fezandipiti/dunsparce specialists,
whose gates key on cards this list also plays (Hero's Cape 1159 / Fezandipiti 140 + Lillie 1227 +
Xerosic 1197 / Dunsparce 305/66).
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_attack, all_card_data

# ── deck card IDs (verified via all_card_data against the mined Tea Party list) ────────────────
IMPIDIMP = 646        # Marnie's Impidimp, basic D, 70HP; Filch (draw 1)
MORGREM = 647         # Marnie's Morgrem, stage1, 100HP; Corkscrew Punch {D}{D} 60
GRIMMSNARL = 648      # Marnie's Grimmsnarl ex, stage2 ex, 320HP; Punk Up + Shadow Bullet
DUNSPARCE = 305       # basic C, 70HP; Trading Places (free self-switch)
DUDUNSPARCE = 66      # stage1 C, 140HP; Run Away Draw; Land Crush {C}{C}{C} 90 (non-ex)
BUDEW = 235           # basic G, 30HP; Itchy Pollen (free): 10 + opponent can't play Items
YVELTAL = 689         # basic D, 110HP, FREE retreat; Dark Feather {D}{D}{C} 110 (non-ex)
MUNKIDORI = 112       # basic P, 110HP; Adrena-Brain (needs a {D} attached)
FEZANDIPITI = 140     # basic ex, 210HP; Flip the Script (draw 3 after our KO'd turn)

TOOL_SCRAPPER = 1137  # item: discard up to 2 tools (either side)
BUDDY_POFFIN = 1086   # item: up to 2 Basic (<=70HP) Pokémon onto the bench (Impidimp/Dunsparce)
POKE_PAD = 1152       # item: search a non-Rule-Box Pokémon to hand
HEROS_CAPE = 1159     # tool (ACE SPEC): +100 HP
RARE_CANDY = 1079     # item: Basic -> Stage 2 from hand (Impidimp -> Grimmsnarl ex)
XEROSIC = 1197        # supporter: opponent discards down to 3 cards
LILLIE_DET = 1227     # supporter: shuffle hand, draw 6 (8 if exactly 6 prizes remain)
DAWN = 1231           # supporter: search a Basic + a Stage 1 + a Stage 2 to hand
BOSS_ORDERS = 1182    # supporter: gust a benched opponent Pokémon to Active
SPIKEMUTH = 1259      # stadium: once per turn each player may tutor a Marnie's Pokémon to hand
RISKY_RUINS = 1260    # stadium: benching a Basic non-{D} Pokémon -> 2 damage counters on it
BASIC_DARK = 7        # Basic {D} Energy (x10; Punk Up's fuel — it searches the DECK)

# Attack IDs (verified via all_attack).
FILCH = 934           # Impidimp {C}: 0 dmg, draw a card
CORKSCREW_10 = 935    # Impidimp {D}: 10
CORKSCREW_60 = 936    # Morgrem {D}{D}: 60 (non-ex)
SHADOW_BULLET = 937   # Grimmsnarl {D}{D}: 180 + 30 to one benched opponent (97% of elite attacks)
TRADING_PLACES = 423  # Dunsparce {C}: 0 dmg, switch self with a benched mon
RAM = 424             # Dunsparce {C}{C}: 20
LAND_CRUSH = 76       # Dudunsparce {C}{C}{C}: 90 (non-ex)
ITCHY_POLLEN = 323    # Budew (free): 10 + item-lock next turn (77% of uses on turns 1-2)
CLUTCH = 997          # Yveltal {D}: 20 + no-retreat
DARK_FEATHER = 998    # Yveltal {D}{D}{C}: 110 (non-ex)
CRUEL_ARROW = 183     # Fezandipiti {C}{C}{C}: 100 to ANY opponent Pokémon (ex attack)

MARNIES = {IMPIDIMP, MORGREM, GRIMMSNARL}          # the only legal Punk Up energy targets
EX_ATTACKS = {SHADOW_BULLET, CRUEL_ARROW, CORKSCREW_10, FILCH}  # negated by the Crustle wall
# Cards unique to this list across every specialist/candidate deck -> zero-false-positive gate.
_SIGNATURE = {IMPIDIMP, MORGREM, GRIMMSNARL, SPIKEMUTH, RISKY_RUINS}

# Full 60-card decklist (the mined Tea Party list) for the lethal verifier's determinization.
GRIMMSNARL_DECK = (
    [IMPIDIMP] * 4 + [MORGREM] * 2 + [GRIMMSNARL] * 4
    + [DUNSPARCE] * 3 + [DUDUNSPARCE] * 3 + [BUDEW] + [YVELTAL] + [MUNKIDORI] * 3 + [FEZANDIPITI]
    + [TOOL_SCRAPPER] + [BUDDY_POFFIN] * 4 + [POKE_PAD] * 4 + [HEROS_CAPE] + [RARE_CANDY] * 4
    + [XEROSIC] + [LILLIE_DET] * 4 + [DAWN] * 3 + [BOSS_ORDERS] * 2
    + [SPIKEMUTH] * 3 + [RISKY_RUINS] + [BASIC_DARK] * 10
)
assert len(GRIMMSNARL_DECK) == 60, len(GRIMMSNARL_DECK)

KEY_PIECES = {GRIMMSNARL, MORGREM, IMPIDIMP, RARE_CANDY, MUNKIDORI, DUDUNSPARCE, HEROS_CAPE}
USEFUL_PIECES = {BUDDY_POFFIN, POKE_PAD, DAWN, BOSS_ORDERS, SPIKEMUTH, LILLIE_DET}

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
DMG_CTX = {SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
           SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET}

# Elite pilots took "go first" 1054/1054 times it was offered.
_GO_FIRST = True

# Deck-out governors. The elite discipline: Run Away Draw off at deckCount <= 3; Punk Up energy
# count scaled by deck size; searches declined late only when nothing is needed.
_RAD_FLOOR = 4        # Run Away Draw requires deckCount >= this (elite threshold)
_FILCH_FLOOR = 3      # don't Filch-draw below this deckCount
_SEARCH_FLOOR = 2     # don't deck-search below this deckCount

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


def _has_dark(p) -> bool:
    """A {D} energy attached (Adrena-Brain's requirement). All our energy is Basic {D}."""
    try:
        for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
            if _id(c) == BASIC_DARK:
                return True
    except Exception:
        pass
    return False


def _damage_on(p) -> int:
    try:
        return max(0, (getattr(p, "maxHp", 0) or 0) - (getattr(p, "hp", 0) or 0))
    except Exception:
        return 0


# ── deck detection (latched per seat: early hands can hide every signature card) ───────────────
_LATCH = {}        # me_i -> True once a signature card has been seen on our side this game
_LATCH_PRIZE = {}  # me_i -> last seen own prize count (increase => new game => re-detect)


def is_grimmsnarl_deck(state, me_i: int) -> bool:
    """True iff our side pilots the Marnie's Grimmsnarl list. A sighting of any signature card
    (Marnie's line / Spikemuth Gym / Risky Ruins — unique to this list) latches for the rest of
    the game, so a frame where the hand happens to hide them cannot fall through to the
    fezandipiti/dunsparce/cinderace specialists whose gates overlap this list's cards."""
    try:
        me = state.players[me_i]
        pc = len(me.prize or [])
        if _LATCH.get(me_i) and _LATCH_PRIZE.get(me_i) is not None and pc > _LATCH_PRIZE[me_i]:
            _LATCH[me_i] = False   # prizes grew back: a new game started
        _LATCH_PRIZE[me_i] = pc
        if _LATCH.get(me_i):
            return True
        zones = list(me.hand or []) + list(me.discard or [])
        for p in (list(me.active or []) + list(me.bench or [])):
            if p is None:
                continue
            zones.append(p)
            for c in (getattr(p, "preEvolution", None) or []):
                zones.append(c)
        for c in (state.stadium or []):
            if c is not None and getattr(c, "playerIndex", None) == me_i:
                zones.append(c)
        if any(_id(c) in _SIGNATURE for c in zones):
            _LATCH[me_i] = True
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


def _my_mons(state, me_i):
    a = _my_active(state, me_i)
    return ([a] if a is not None else []) + _my_bench(state, me_i)


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


def _hand(state, me_i):
    try:
        return state.players[me_i].hand or []
    except Exception:
        return []


def _deck_count(state, me_i) -> int:
    try:
        return int(state.players[me_i].deckCount or 0)
    except Exception:
        return 99


def _turn(state) -> int:
    try:
        return int(getattr(state, "turn", 0) or 0)
    except Exception:
        return 99


def _prize_count_for(p) -> int:
    cd = _meta(_id(p))
    if cd is None:
        return 1
    return 3 if getattr(cd, "megaEx", False) else 2 if getattr(cd, "ex", False) else 1


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


# ── prize tracking (search-whiff avoidance, same edge as the starmie specialist) ───────────────
try:
    from prize_tracker import PrizeTracker
except Exception:
    try:
        from agent.prize_tracker import PrizeTracker
    except Exception:
        PrizeTracker = None

from collections import Counter as _Counter

_DECK_COUNTS = _Counter(GRIMMSNARL_DECK)
_TRACKERS = {}       # me_i -> PrizeTracker (per seat so mirror self-play doesn't thrash one)
_TRACK_PRIZE = {}    # me_i -> last own prize count (increase => new game)
_VS_CRU = {}         # me_i -> latched "opponent is the Crustle wall" flag
_CRUSTLE_LINE = {344, 345}   # Dwebble / Crustle — unique to the crustle wall decks


def note_obs(obs, obs_dict, me_i) -> None:
    """Per-frame bookkeeping: prize tracker + the Crustle-wall matchup latch. Never raises."""
    try:
        state = obs.current
        pc = len(state.players[me_i].prize or [])
        if (me_i not in _TRACKERS or
                (_TRACK_PRIZE.get(me_i) is not None and pc > _TRACK_PRIZE[me_i])):
            _TRACKERS[me_i] = PrizeTracker(GRIMMSNARL_DECK) if PrizeTracker else None
            _VS_CRU[me_i] = False
        _TRACK_PRIZE[me_i] = pc
        if _TRACKERS.get(me_i) is not None:
            _TRACKERS[me_i].update(obs, obs_dict)
        if not _VS_CRU.get(me_i):
            op = state.players[1 - me_i]
            seen = []
            for p in (list(op.active or []) + list(op.bench or [])):
                if p is None:
                    continue
                seen.append(_id(p))
                for c in (getattr(p, "preEvolution", None) or []):
                    seen.append(_id(c))
            for c in (op.discard or []):
                seen.append(_id(c))
            if any(cid in _CRUSTLE_LINE for cid in seen):
                _VS_CRU[me_i] = True
    except Exception:
        pass


def _prized(me_i=None):
    tr = None
    if me_i is not None:
        tr = _TRACKERS.get(me_i)
    elif _TRACKERS:
        tr = next(iter(_TRACKERS.values()))
    if tr is None:
        return None
    try:
        return tr.prized_cards()
    except Exception:
        return None


def _vs_crustle(me_i) -> bool:
    return bool(_VS_CRU.get(me_i))


def _deck_available(state, me_i, card_id) -> int:
    """Copies of `card_id` (conservatively) still in our draw pile: total minus visible minus
    known-prized. Unknown prizes count as available (a wrong inference is worse than none)."""
    total = _DECK_COUNTS.get(card_id, 0)
    if total == 0:
        return 0
    visible = 0
    try:
        me = state.players[me_i]
        for c in (me.hand or []):
            if _id(c) == card_id:
                visible += 1
        for c in (me.discard or []):
            if _id(c) == card_id:
                visible += 1
        for p in _my_mons(state, me_i):
            if _id(p) == card_id:
                visible += 1
            for c in (getattr(p, "preEvolution", None) or []):
                if _id(c) == card_id:
                    visible += 1
            for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
                if _id(c) == card_id:
                    visible += 1
            for c in (getattr(p, "tools", None) or []):
                if _id(c) == card_id:
                    visible += 1
        for c in (state.stadium or []):
            if _id(c) == card_id and getattr(c, "playerIndex", None) == me_i:
                visible += 1
    except Exception:
        pass
    pr = 0
    prized = _prized(me_i)
    if prized is not None:
        pr = prized.get(card_id, 0)
    return max(0, total - visible - pr)


def _marnies_available(state, me_i) -> bool:
    return any(_deck_available(state, me_i, cid) > 0 for cid in MARNIES)


def _line_need(state, me_i):
    """Need-aware line completion: which card ids most advance a Grimmsnarl ex THIS/next turn,
    as {card_id: bonus}. A static 'Grimmsnarl is the best fetch' rule hoards 3rd/4th copies
    while the actual missing piece (Morgrem or Rare Candy over a lone Impidimp) rots in the
    deck — the exact failure observed in the pre-calibration wall games."""
    need = {}
    hand_ids = [_id(c) for c in _hand(state, me_i)]
    n648_hand = hand_ids.count(GRIMMSNARL)
    have_candy = RARE_CANDY in hand_ids
    have_morgrem_hand = MORGREM in hand_ids
    mons = _my_mons(state, me_i)
    imp_in_play = any(_id(p) == IMPIDIMP for p in mons)
    mor_in_play = any(_id(p) == MORGREM for p in mons)
    grimm_in_play = any(_id(p) == GRIMMSNARL for p in mons)

    if not (imp_in_play or mor_in_play or grimm_in_play):
        need[IMPIDIMP] = 500.0
    if (imp_in_play or mor_in_play) and n648_hand == 0:
        need[GRIMMSNARL] = 500.0
    if imp_in_play and n648_hand > 0 and not have_candy and not mor_in_play:
        # A Grimmsnarl is stuck in hand over a lone Impidimp: Candy or Morgrem unlocks it.
        need[RARE_CANDY] = 500.0
        if not have_morgrem_hand:
            need[MORGREM] = 450.0
    if grimm_in_play and n648_hand == 0 and imp_in_play:
        need[GRIMMSNARL] = 300.0     # the NEXT attacker, once one is already online
    return need


def _eff_damage(active, attack_id, opp_active, me_i) -> int:
    """Effective damage to the opponent's Active. Zeroes ex-attacks into the Crustle wall (its
    ability negates ALL damage to it from ex/mega-ex attacks) so the scorer pivots to bench-
    snipe/Adrena pressure instead of counting a 180 that will not land."""
    if attack_id in EX_ATTACKS and _vs_crustle(me_i) and _id(opp_active) == 345:
        return 0
    try:
        from scorer import _attack_damage
        d = _attack_damage(active, attack_id, opp_active)
        if d:
            return d
    except Exception:
        pass
    atk = _ATK.get(attack_id)
    return (atk.damage or 0) if atk is not None else 0


def _affordable_damage(state, me_i) -> int:
    """Max effective damage our Active can deal THIS turn with the energy it actually has (the
    Boss's Orders gate must not assume unpayable attacks — gusting a target we then hit for 20
    wastes the supporter)."""
    active = _my_active(state, me_i)
    if active is None:
        return 0
    cd = _meta(_id(active))
    if cd is None:
        return 0
    have = _energy_count(active)
    oa = _opp_active(state, me_i)
    best = 0
    for aid in (getattr(cd, "attacks", None) or []):
        atk = _ATK.get(aid)
        if atk is None or len(getattr(atk, "energies", None) or []) > have:
            continue
        best = max(best, _eff_damage(active, aid, oa, me_i))
    return best


def _affordable_damage_vs(state, me_i, target) -> int:
    """Max affordable raw damage vs a specific (gusted-in) target."""
    active = _my_active(state, me_i)
    if active is None:
        return 0
    cd = _meta(_id(active))
    if cd is None:
        return 0
    have = _energy_count(active)
    best = 0
    for aid in (getattr(cd, "attacks", None) or []):
        atk = _ATK.get(aid)
        if atk is None or len(getattr(atk, "energies", None) or []) > have:
            continue
        if aid in EX_ATTACKS and _vs_crustle(me_i) and _id(target) == 345:
            continue
        best = max(best, (atk.damage or 0))
    return best


def _good_gust_target(state, me_i):
    """Boss's Orders as the elite play it: a KO-enabler. Return a benched opponent Pokémon our
    AFFORDABLE attack KOs this turn — preferred when their Active is not KOable or the benched
    target is worth more (fresh support mons, ex bodies). Else None."""
    aff = _affordable_damage(state, me_i)
    oa = _opp_active(state, me_i)
    active_koable = oa is not None and aff > 0 and aff >= (oa.hp or 0)
    target, target_val = None, 0.0
    for b in _opp_bench(state, me_i):
        dmg_vs_b = _affordable_damage_vs(state, me_i, b)
        if dmg_vs_b <= 0 or dmg_vs_b < (b.hp or 0):
            continue
        val = _opponent_value(b) + _prize_count_for(b) * 100.0
        if (not active_koable) or val > _opponent_value(oa) + _prize_count_for(oa) * 100.0 + 60.0:
            if val > target_val:
                target, target_val = b, val
    return target


def _incoming_threat(state, me_i, target=None) -> int:
    """Max damage the opponent's Active can deal to our Active (or `target`, e.g. a promotion
    candidate) next turn — their energy + 1 more attach, weakness-aware. The Crustle wall's
    Grass-typed Superb Scissors hits our Grass-weak Marnie's line for DOUBLE (240 into a 320HP
    Grimmsnarl) — rotation and promotion decisions must see that."""
    oa = _opp_active(state, me_i)
    mine = target if target is not None else _my_active(state, me_i)
    if oa is None or mine is None:
        return 0
    ocd = _meta(_id(oa))
    mcd = _meta(_id(mine))
    if ocd is None:
        return 0
    have = _energy_count(oa) + 1
    best = 0
    for aid in (getattr(ocd, "attacks", None) or []):
        atk = _ATK.get(aid)
        if atk is None or len(getattr(atk, "energies", None) or []) > have:
            continue
        d = atk.damage or 0
        if d and mcd is not None:
            try:
                if mcd.weakness is not None and mcd.weakness == ocd.energyType:
                    d *= 2
                elif mcd.resistance is not None and mcd.resistance == ocd.energyType:
                    d = max(0, d - 30)
            except Exception:
                pass
        best = max(best, d)
    return best


def _count_in_play(state, me_i, cid) -> int:
    return sum(1 for p in _my_mons(state, me_i) if _id(p) == cid)


def _our_damage_total(state, me_i) -> int:
    """Damage counters currently on OUR side (Adrena-Brain's ammunition)."""
    return sum(_damage_on(p) for p in _my_mons(state, me_i))


def _our_stadium_up(state, me_i) -> bool:
    try:
        return any(c is not None and getattr(c, "playerIndex", None) == me_i
                   for c in (state.stadium or []))
    except Exception:
        return False


# ── MAIN-turn scoring ──────────────────────────────────────────────────────────────────────────
# The elite ladder (mean within-turn position over 236k decisions): stadium down -> evolve
# Dudunsparce -> Flip the Script -> evolve Grimmsnarl / Rare Candy -> Spikemuth tutor -> Poffin /
# Lillie / Dawn / Boss -> bench basics / Run Away Draw -> Poké Pad -> Xerosic -> tools -> energy
# attach -> retreat -> Adrena-Brain -> ATTACK (never skipped) -> END. Morgrem evolve runs LATE
# (searches first may find the Rare Candy that makes Morgrem unnecessary), and Adrena-Brain runs
# after Boss so moved counters can finish the gusted-in target.
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type
    vs_cru = _vs_crustle(me_i)

    if t == OptionType.EVOLVE:
        card = _get(obs, getattr(o, "area", None), getattr(o, "index", None), me_i)
        cid = _id(card)
        if cid == DUDUNSPARCE:
            return 2620.0   # first: its Run Away Draw grows the turn
        if cid == GRIMMSNARL:
            return 2600.0   # Punk Up: the whole engine
        if cid == MORGREM:
            # LAST among free plays: evolving the Impidimp now kills its Rare-Candy line for the
            # turn, and a search may still find the Candy. Still always taken before attacking.
            return 1250.0
        return 2300.0

    if t == OptionType.ABILITY:
        owner = _get(obs, getattr(o, "area", None), getattr(o, "index", None), me_i)
        oid = _id(owner)
        deck_n = _deck_count(state, me_i)
        if oid == FEZANDIPITI:
            return 2610.0 if deck_n >= 4 else -1.0   # Flip the Script: free +3, fired early
        if oid == DUDUNSPARCE:
            # Run Away Draw: elite usage is >=97% at every deck size until deckCount <= 3.
            if deck_n < _RAD_FLOOR:
                return -1.0
            if len(_my_mons(state, me_i)) <= 1:
                return -1.0    # never shuffle away our only Pokémon
            if vs_cru:
                # The wall's endgame is a deck-out grind and our kill-shot on its last Crustle
                # is Adrena burst + Land Crush: never recycle a fueled Dudunsparce, and stop
                # burning deck for cards we don't need.
                if _energy_count(owner) >= 2:
                    return -1.0
                if deck_n < 25 and len(_hand(state, me_i)) > 5:
                    return -1.0
            return 2270.0
        if oid == SPIKEMUTH:
            # Once-per-turn Marnie's tutor. Fetch what the line needs; decline late-game when
            # nothing is missing (the elite decline ~40% from own-turn 7 on).
            if deck_n <= _SEARCH_FLOOR or not _marnies_available(state, me_i):
                return -1.0
            if not _line_need(state, me_i) and deck_n < 20:
                return -1.0
            return 2460.0
        if oid == MUNKIDORI:
            # Adrena-Brain: fired EVERY copy EVERY turn it has ammunition — but late in the turn
            # (after Boss has set the board, before the attack).
            if _our_damage_total(state, me_i) > 0:
                return 950.0
            return -1.0
        if oid == GRIMMSNARL:
            return 2500.0      # Punk Up surfacing as an explicit ability option
        return 1000.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        bench = _my_bench(state, me_i)
        bench_n = len(bench)
        hand_n = len(_hand(state, me_i))
        deck_n = _deck_count(state, me_i)
        sup_done = bool(getattr(state, "supporterPlayed", False))
        stad_done = bool(getattr(state, "stadiumPlayed", False))

        # Rare Candy: Impidimp -> Grimmsnarl ex, triggering Punk Up. Play the turn it is live
        # (elite mode: own-turn 2; 44% of all their Grimmsnarl builds).
        if cid == RARE_CANDY:
            imp_in_play = any(_id(p) == IMPIDIMP for p in _my_mons(state, me_i))
            grimm_in_hand = any(_id(c) == GRIMMSNARL for c in _hand(state, me_i))
            return 2550.0 if (imp_in_play and grimm_in_hand) else -1.0

        # ---- stadiums: down FIRST (elite position 0.19; enables the Spikemuth tutor) ------------
        if cid == SPIKEMUTH:
            if stad_done or _our_stadium_up(state, me_i):
                return -1.0
            return 2450.0
        if cid == RISKY_RUINS:
            if stad_done or _our_stadium_up(state, me_i):
                return -1.0
            # vs the wall: their Dwebbles are Grass (non-{D}) — every Poffin'd Dwebble arrives
            # with 20 damage, and playing it overwrites their Battle Cage. Outranks Spikemuth.
            return 2455.0 if vs_cru else 2430.0

        # ---- supporters (one per turn) ----------------------------------------------------------
        if cid == BOSS_ORDERS:
            if sup_done:
                return -1.0
            return 2030.0 if _good_gust_target(state, me_i) is not None else -1.0
        if cid == LILLIE_DET:
            if sup_done or deck_n < 6:
                return -1.0
            if hand_n <= 6:
                return 2060.0   # elite median hand at play: 6
            if hand_n <= 9:
                return 1200.0
            return -1.0
        if cid == DAWN:
            if sup_done or deck_n <= _SEARCH_FLOOR:
                return -1.0
            need = _line_need(state, me_i)
            return 2020.0 if (need or deck_n >= 20) else 800.0
        if cid == XEROSIC:
            if sup_done:
                return -1.0
            try:
                opp_hand = int(state.players[1 - me_i].handCount or 0)
            except Exception:
                opp_hand = 0
            return 1950.0 if opp_hand >= 4 else 200.0

        # ---- board + dig items ------------------------------------------------------------------
        if cid == BUDDY_POFFIN:
            if deck_n <= _SEARCH_FLOOR:
                return -1.0
            fetchable = (_deck_available(state, me_i, IMPIDIMP)
                         + _deck_available(state, me_i, DUNSPARCE)
                         + _deck_available(state, me_i, BUDEW))
            if fetchable <= 0:
                return -1.0
            if vs_cru and bench_n >= 2 and deck_n < 30:
                return -1.0    # wall endgame = deck-out race: stop thinning for spare bodies
            if bench_n <= 1:
                return 2050.0
            if bench_n <= 3:
                return 1850.0
            return 250.0
        if cid == POKE_PAD:
            if deck_n <= _SEARCH_FLOOR:
                return -1.0
            need = _line_need(state, me_i)
            fetchable = sum(_deck_available(state, me_i, c) for c in
                            (IMPIDIMP, MORGREM, DUNSPARCE, DUDUNSPARCE, MUNKIDORI, YVELTAL, BUDEW))
            if fetchable <= 0:
                return -1.0
            hits_need = any(_deck_available(state, me_i, c) > 0 for c in need
                            if c != RARE_CANDY and c != GRIMMSNARL)
            if hits_need or _count_in_play(state, me_i, MUNKIDORI) < 2:
                return 1900.0
            return 1500.0 if deck_n >= 15 else 300.0
        if cid == TOOL_SCRAPPER:
            opp_tools = 0
            try:
                for p in ([_opp_active(state, me_i)] + _opp_bench(state, me_i)):
                    if p is not None:
                        opp_tools += len(getattr(p, "tools", None) or [])
            except Exception:
                opp_tools = 0
            if opp_tools <= 0:
                return -1.0
            return 1600.0 if vs_cru else 1200.0   # scrapping the wall's Hero's Cape is huge

        # ---- Pokémon from hand ------------------------------------------------------------------
        cd = _meta(cid)
        if cd is not None and cd.cardType == CardType.POKEMON and getattr(cd, "basic", False):
            if bench_n == 0:
                return 2100.0   # never risk a no-Active loss
            if cid == IMPIDIMP:
                return 2000.0 if _count_in_play(state, me_i, IMPIDIMP) < 3 else 1200.0
            if cid == MUNKIDORI:
                # The Adrena engine: elite bench it steadily all game (1-2 copies working).
                return 1990.0 if _count_in_play(state, me_i, MUNKIDORI) < 2 else 400.0
            if cid == DUNSPARCE:
                return 1980.0   # replaces the shuffled-away Dudunsparce line
            if cid == FEZANDIPITI:
                return 900.0    # elite bench it early with no prize gate, but only ~18% of games
            if cid == YVELTAL:
                return 500.0    # elite almost never bench it (70 total in 2,020 games)
            if cid == BUDEW:
                return 250.0    # 30HP liability after turn 1
            return 900.0

        # Hero's Cape under PLAY (some engine paths surface tools here).
        if cid == HEROS_CAPE:
            return 1450.0
        return 500.0

    if t == OptionType.ATTACH:
        card = _get(obs, getattr(o, "area", None), getattr(o, "index", None), me_i)
        cid = _id(card)
        tgt = _get(obs, getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), me_i)
        tid = _id(tgt)
        ten = _energy_count(tgt)
        # Hero's Cape: Grimmsnarl ex only (811/974 elite attaches; Morgrem as a stopgap).
        if cid == HEROS_CAPE:
            if tid == GRIMMSNARL:
                return 1500.0 if getattr(o, "inPlayArea", None) == AreaType.ACTIVE else 1420.0
            if tid == MORGREM:
                return 1350.0
            return 100.0
        # Manual energy: Munkidori at ~95% priority (Punk Up cannot legally feed it, and every
        # copy needs one {D} for Adrena-Brain); then Grimmsnarl. Never Dudunsparce/Yveltal.
        # Prefer a BENCHED Munkidori: an active one pays its retreat by discarding the very
        # {D} the ability needs (observed loss mode).
        if tid == MUNKIDORI and not _has_dark(tgt):
            return 1150.0 + (30.0 if getattr(o, "inPlayArea", None) == AreaType.BENCH else 0.0)
        if vs_cru and tid == DUDUNSPARCE and ten < 3:
            # The burst piece vs the wall: Land Crush 90 (non-ex) + 3x Adrena 90 kills the last
            # Crustle through its heals. Fuel it once the Munkidori are fed.
            return 1050.0
        if tid == GRIMMSNARL:
            if ten < 2:
                bonus = 60.0 if getattr(o, "inPlayArea", None) == AreaType.ACTIVE else 0.0
                return 1100.0 + bonus
            return 700.0 if ten < 3 else 100.0
        if tid in (IMPIDIMP, MORGREM) and ten < 2:
            return 950.0
        return 200.0 if ten < 3 else 50.0

    if t == OptionType.ATTACK:
        active = _my_active(state, me_i)
        oa = _opp_active(state, me_i)
        deck_n = _deck_count(state, me_i)
        aid = getattr(o, "attackId", None)
        dmg = _eff_damage(active, aid, oa, me_i)
        # Elite pilots NEVER end the turn with an attack available (5:9270); base clears END.
        score = 100.0 + min(max(dmg, 0), 300) * 0.25
        if aid == SHADOW_BULLET:
            score += 40.0   # 97% of elite attacks; the 30 bench snipe is real extra value
        if aid == FILCH:
            return 130.0 if deck_n >= _FILCH_FLOOR else -1.0
        if aid == ITCHY_POLLEN:
            return 350.0 if _turn(state) <= 3 else 120.0
        if aid == TRADING_PLACES:
            if any(_id(b) == GRIMMSNARL and _energy_count(b) >= 2 for b in _my_bench(state, me_i)):
                return 200.0
            return 60.0
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 200.0  # KO
            try:
                opp = state.players[1 - me_i]
                if len(opp.prize or []) <= _prize_count_for(oa):
                    return 50000.0  # takes their last prize(s) -> game-winning
            except Exception:
                pass
        if vs_cru and aid in (LAND_CRUSH, DARK_FEATHER, CORKSCREW_60, RAM):
            score += 150.0  # non-ex damage actually lands on the wall
        return score

    if t == OptionType.RETREAT:
        # Positioning (elite: 915 retreats, always pre-attack): promote a powered Grimmsnarl over
        # a stranded support body — and rotate a dying Grimmsnarl out before it hands over 2
        # prizes (the wall's weakness-doubled 240 two-shots a 320HP active; a bench stays safe).
        active = _my_active(state, me_i)
        aid_ = _id(active)
        grim_ready = any(_id(b) == GRIMMSNARL and _energy_count(b) >= 2
                         for b in _my_bench(state, me_i))
        if aid_ != GRIMMSNARL and grim_ready:
            return 1000.0 if aid_ in (MUNKIDORI, BUDEW, DUNSPARCE, IMPIDIMP, YVELTAL) else 800.0
        if aid_ == GRIMMSNARL:
            threat = _incoming_threat(state, me_i)
            hp = getattr(active, "hp", 0) or 0
            if threat >= hp > 0:
                for b in _my_bench(state, me_i):
                    if (_id(b) == GRIMMSNARL and _energy_count(b) >= 2
                            and (getattr(b, "hp", 0) or 0) > threat):
                        return 1005.0   # swap in the healthy powered copy; the hurt one hides
                # vs the gustless wall a damaged Grimmsnarl on the bench is PERMANENTLY safe (and
                # a rich Adrena-Brain source): retreating into any body saves 2 prizes.
                if vs_cru and _my_bench(state, me_i):
                    return 1005.0
        return -1.0

    if t == OptionType.END:
        return 0.0
    if t == OptionType.YES:
        return 5.0
    if t == OptionType.NO:
        return 3.0
    return 1.0


# ── forced sub-selection scoring (base high so we always make a legal move) ────────────────────
def score_sub(obs, o, me_i, context) -> float:
    state = obs.current
    opp_i = 1 - me_i
    t = o.type
    score = 2000.0
    vs_cru = _vs_crustle(me_i)

    if t == OptionType.NUMBER:
        return score + (getattr(o, "number", 0) or 0)   # move/draw the max (84% move 3)

    if t == OptionType.YES:
        if context == SelectContext.IS_FIRST:
            return score + (100.0 if _GO_FIRST else 0.0)   # elite: YES 1054/1054
        return score + 100.0   # includes Punk Up's prompt: never declined (5,243/5,243)
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

        # Heal / damage removal (Adrena-Brain SOURCE included): the elite source from their own
        # Grimmsnarl 81% of the time — Adrena-Brain is first a healing engine for the attacker.
        if context in HEAL_CTX:
            if isinstance(card, Pokemon):
                score += _damage_on(card)
                if cid == GRIMMSNARL and pidx == me_i:
                    score += 200.0
                if o.area == AreaType.ACTIVE and pidx == me_i:
                    score += 120.0
            return score

        # Damage / Adrena-Brain DESTINATION / snipe targeting: FINISH targets (the observed
        # failure was spreading 30s across fresh Dwebbles instead of closing the 40HP one), else
        # their Munkidori / fresh support basics (the elite soften future targets), else value.
        if context in DMG_CTX:
            if isinstance(card, Pokemon) and pidx == opp_i:
                score += _opponent_value(card)
                hp = getattr(card, "hp", 0) or 0
                maxhp = getattr(card, "maxHp", 0) or 0
                if 0 < hp <= 30:
                    score += 450.0          # finishable by moved counters / the 30 snipe
                elif 0 < hp <= 60:
                    score += 260.0          # two snipes / snipe+Adrena closes it
                elif 0 < hp <= 90:
                    score += 120.0
                if cid == MUNKIDORI:
                    score += 180.0          # the elite's favourite snipe target
                elif maxhp and maxhp <= 80 and _meta(cid) is not None and getattr(_meta(cid), "basic", False):
                    score += 120.0          # fresh evolving/support basics
                if o.area == AreaType.ACTIVE:
                    score += 100.0
                if vs_cru:
                    if context == SelectContext.DAMAGE and cid == 345:
                        score -= 600.0      # ex-attack damage cannot land on the wall — never
                                            # waste the Shadow Bullet snipe on a Crustle
                    elif context in (SelectContext.DAMAGE_COUNTER,
                                     SelectContext.DAMAGE_COUNTER_ANY):
                        # Adrena counters DO land on Crustle (ability, not attack) — but their
                        # heals are ACTIVE-only, so counters on the active evaporate while a
                        # benched Crustle/Dwebble keeps every counter until it dies. Exception:
                        # a boardless wall's last mon — chip it toward the Land Crush burst
                        # (its per-turn heal is capped ~150 and Cook competes with Cheren).
                        if not _opp_bench(state, me_i):
                            score += 300.0
                        elif o.area == AreaType.ACTIVE:
                            score -= 150.0
                        else:
                            score += 250.0
            elif isinstance(card, Pokemon):
                score -= _opponent_value(card)
            return score

        # Punk Up target selection (ATTACH_FROM: "attach this energy to which Pokémon?"). The
        # engine surfaces these as CARD options, NOT OptionType.ATTACH — without this branch the
        # 5 searched energies piled onto whichever Grimmsnarl came first (observed: a dying 80HP
        # active) instead of powering the fresh attacker. Selects run one energy at a time, so
        # energy counts refresh between picks and the spread emerges naturally: new/underfueled
        # Grimmsnarl to 2 (Shadow Bullet), then pre-charge Impidimp/Morgrem, never pile past 3.
        if context == SelectContext.ATTACH_FROM and pidx == me_i and isinstance(card, Pokemon):
            ten = _energy_count(card)
            hp = getattr(card, "hp", 0) or 0
            threat = _incoming_threat(state, me_i)
            if cid == GRIMMSNARL:
                if ten < 2:
                    score += 500.0
                elif ten < 3:
                    score += 150.0
                else:
                    score -= 250.0
                if o.area == AreaType.ACTIVE and threat >= hp > 0:
                    score -= 350.0   # don't fuel a body that dies to the next hit
            elif cid in (IMPIDIMP, MORGREM):
                score += 260.0 if ten < 2 else -150.0
            else:
                score -= 50.0
            return score

        # Punk Up energy picks (ATTACH_TO: which energy cards to take from the deck). Elite count
        # discipline: take everything while the deck is fat, shrink to ~1 as it thins (their mode:
        # 4-5 at deck>=30, 1 at 20-29, 0-1 below 15) — Punk Up drains the same {D} pool the manual
        # Munkidori attaches need. Identical options can't be partially selected by score alone,
        # so below the threshold only the FIRST energy option scores positive (ranker takes one).
        if context == SelectContext.ATTACH_TO and cid == BASIC_DARK and o.area == AreaType.DECK:
            deck_n = _deck_count(state, me_i)
            if deck_n >= 18:
                return score + 100.0
            try:
                opts = obs.select.option
                first = next(i for i, opt in enumerate(opts)
                             if getattr(opt, "area", None) == AreaType.DECK
                             and _id(_get(obs, opt.area, opt.index, pidx)) == BASIC_DARK)
                return score + (100.0 if opts[first] is o else -2100.0)
            except Exception:
                return score + 100.0

        # Discard / pitch / give-up: spare {D} first, protect the line + Candy + Cape.
        if context in GIVE_UP_CTX:
            cd = _meta(cid)
            if cd is not None:
                if cid == BASIC_DARK:
                    return score + 60.0
                if cid == SPIKEMUTH:
                    return score + (40.0 if _our_stadium_up(state, me_i) else -60.0)
                if cid in KEY_PIECES or cd.cardType == CardType.POKEMON:
                    return score - 250.0
                if cd.cardType in (CardType.SPECIAL_ENERGY, CardType.TOOL):
                    return score - 120.0
                if cid in USEFUL_PIECES:
                    return score - 80.0
            return score

        # Boss's Orders target (their bench -> active): the elite use it as a KO-enabler on
        # fresh, energyless support mons (61% undamaged, 60% zero energy, 92% KO-able).
        if context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH) and pidx == opp_i:
            if isinstance(card, Pokemon):
                score += _opponent_value(card)
                score -= _energy_count(card) * 30.0
                aff = _affordable_damage_vs(state, me_i, card)
                if aff > 0 and (getattr(card, "hp", 0) or 0) <= aff:
                    score += 500.0
                if vs_cru:
                    if cid == 344:
                        score += 300.0   # pull the unprotected Dwebble, never the wall
                    elif cid == 345:
                        score -= 400.0
            return score

        # Our own Pokémon: setup / evolve / fetch / placement / promote.
        if isinstance(card, Pokemon) or (
                _meta(cid) is not None and _meta(cid).cardType == CardType.POKEMON):
            if pidx == opp_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 200.0
                return score
            bench_n = len(_my_bench(state, me_i))
            need = _line_need(state, me_i)
            hand_ids = [_id(c) for c in _hand(state, me_i)]
            # Fetch-to-hand and placement values, calibrated on the elite picks (Spikemuth:
            # Impidimp t1 then Grimmsnarl>Morgrem>Impidimp; Dawn: Dudunsparce/Grimmsnarl/
            # Munkidori; Poké Pad: Munkidori first; Poffin: Impidimp+Dunsparce).
            if cid == GRIMMSNARL:
                score += 320.0 - 120.0 * hand_ids.count(GRIMMSNARL)
            elif cid == MORGREM:
                score += 200.0
            elif cid == IMPIDIMP:
                score += 210.0 if _turn(state) <= 2 else 160.0
            elif cid == DUDUNSPARCE:
                score += 170.0
            elif cid == DUNSPARCE:
                score += 150.0
            elif cid == MUNKIDORI:
                score += 190.0 if _count_in_play(state, me_i, MUNKIDORI) < 2 else 90.0
            elif cid == YVELTAL:
                score += 60.0
            elif cid == FEZANDIPITI:
                score += 50.0
            elif cid == BUDEW:
                score += 20.0
            score += need.get(cid, 0.0)   # the missing line piece dominates every static value

            # Setup seats (elite: active Impidimp 39% > Munkidori 29% > Dunsparce 17%; bench
            # Munkidori 40% > Impidimp 34% > Dunsparce 24%; Budew/Fezandipiti/Yveltal held).
            if context == SelectContext.SETUP_ACTIVE_POKEMON:
                score += {IMPIDIMP: 260.0, MUNKIDORI: 180.0, DUNSPARCE: 150.0,
                          YVELTAL: 110.0, FEZANDIPITI: 40.0, BUDEW: 30.0}.get(cid, 0.0)
            elif context == SelectContext.SETUP_BENCH_POKEMON:
                score += {MUNKIDORI: 240.0, IMPIDIMP: 220.0, DUNSPARCE: 180.0}.get(cid, -60.0)

            if bench_n == 0 and context in (SelectContext.TO_BENCH, SelectContext.TO_FIELD,
                                            SelectContext.SETUP_BENCH_POKEMON):
                score += 200.0       # a body on the bench prevents the no-Active loss
            if context in PLACEMENT_CTX:
                score += 400.0
            # Promote after a KO (TO_ACTIVE among our mons): powered Grimmsnarl, else the piece
            # about to become one (Impidimp with Candy+Grimmsnarl in hand), never the 30HP Budew.
            if context == SelectContext.TO_ACTIVE and pidx == me_i:
                if cid == GRIMMSNARL and _energy_count(card) >= 2:
                    score += 500.0
                    threat = _incoming_threat(state, me_i, card)
                    if threat >= (getattr(card, "hp", 0) or 0) > 0:
                        score -= 400.0   # promoting a copy that dies next hit feeds 2 prizes
                elif cid == IMPIDIMP and GRIMMSNARL in hand_ids and RARE_CANDY in hand_ids:
                    score += 350.0
                elif cid == YVELTAL:
                    score += 120.0   # free retreat: a safe pivot seat
                elif cid == BUDEW:
                    score -= 300.0
                elif cid == FEZANDIPITI:
                    score -= 100.0   # 2-prize body — keep it off the front line
            return score

        # Non-Pokémon fetch (tutors etc.).
        cd = _meta(cid)
        if cd is not None:
            need = _line_need(state, me_i)
            if cid == BASIC_DARK:
                score += 100.0
            elif cid == RARE_CANDY:
                score += 90.0 + need.get(RARE_CANDY, 0.0)
            elif cid in (DAWN, LILLIE_DET, BOSS_ORDERS):
                score += 70.0
            elif cid in (BUDDY_POFFIN, POKE_PAD, SPIKEMUTH):
                score += 50.0
        return score

    if t == OptionType.ATTACH:
        # Punk Up's attach-target selection. Elite distribution: 59% Grimmsnarl (58% of all
        # energy to the newly-evolved copy), 29% Impidimp, 12% Morgrem — power the new attacker
        # to Shadow Bullet, pre-charge the next Impidimp(s). Energy COUNT shrinks as the deck
        # thins (deck>=30: take ~4-5; 20-29: ~1-2; <15: 0-1): options past the need score <= 0
        # and are dropped by the ranker.
        tgt = _get(obs, getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), me_i)
        tid = _id(tgt)
        ten = _energy_count(tgt)
        deck_n = _deck_count(state, me_i)
        score = 0.0
        if tid == GRIMMSNARL:
            if ten < 2:
                score = 500.0 + (60.0 if getattr(o, "inPlayArea", None) == AreaType.ACTIVE else 0.0)
            elif ten < 3:
                score = 120.0 if deck_n >= 20 else -50.0
            else:
                score = -200.0
        elif tid == IMPIDIMP:
            if ten < 2:
                score = 260.0 if deck_n >= 25 else (60.0 if deck_n >= 15 else -50.0)
            else:
                score = -150.0
        elif tid == MORGREM:
            if ten < 2:
                score = 240.0 if deck_n >= 25 else (40.0 if deck_n >= 15 else -60.0)
            else:
                score = -150.0
        else:
            score = -100.0
        return score

    return score

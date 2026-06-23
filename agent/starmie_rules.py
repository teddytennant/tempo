"""Starmie / Froslass aggro specialist scoring (id-gated), consulted by agent/scorer.best_options.

The deck (data/decks/starmie.csv) is masamikobayashi's Gold-Medal "Mega Starmie ex / Mega Froslass
ex" list. Its game plan is the opposite of the Crustle wall: it is a *proactive prize racer*.

  • Mega Starmie ex (1031, 330HP) is the primary attacker.
       - Jetting Blow  (1487): {W}        -> 120 + 50 to a benched mon. Absurdly cheap; online turn 1-2.
       - Nebula Beam   (1488): {C}{C}{C}  -> 210, IGNORES weakness/resistance AND all effects on the
                                            opponent's Active (bypasses damage-prevention walls).
  • Mega Froslass ex (861, 310HP) is the secondary attacker.
       - Absolute Snow      (1241): {W}{C}{C} -> 150 + Sleep.
       - Resentful Refrain  (1240): {W}       -> 50 x opponent hand size.

The edge (per the writeup) is PRIZE TRACKING: the deck is full of deck-search cards
(Mega Signal / Salvatore / Hilda / Buddy-Buddy Poffin / Energy Search), and a search whiffs if the
card it wants is in the prizes. We reuse agent.prize_tracker.PrizeTracker to deduce which of our
cards are prized, then refuse to play a search whose only target is unavailable (and prefer searches
that *can* hit) — exactly the human "I know that piece is prized" play.

`is_starmie_deck(state, me_i)` fires only when a Snorunt/Froslass/Staryu/Starmie is on OUR side, so
no other deck (Crustle, Dragapult, …) ever routes through here — the generic path is untouched.
"""
from __future__ import annotations

from collections import Counter

from cg.api import (
    AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext, all_attack, all_card_data,
)

# ── deck card IDs (verified via all_card_data against data/decks/starmie.csv) ──────────────────
SNORUNT = 860            # basic, 70HP, evolves -> Mega Froslass ex
MEGA_FROSLASS = 861      # stage1 megaEx, 310HP, weak metal
STARYU = 1030            # basic, 70HP, evolves -> Mega Starmie ex
MEGA_STARMIE = 1031      # stage1 megaEx, 330HP, weak lightning
SALVATORE = 1189         # supporter: search an Evolution (no Ability) and evolve a Pokémon in play
LILLIE_DET = 1227        # supporter: shuffle hand, draw 6 (8 if exactly 6 prizes)
WALLY_COMP = 1229        # supporter: heal a Mega ex fully BUT return all its energy to hand
BOSS_ORDERS = 1182       # supporter: gust a benched opponent Pokémon to Active
HILDA = 1225             # supporter: search an Evolution Pokémon + an Energy to hand
BLACK_BELT = 1211        # supporter: +40 dmg to opp Active ex this turn (before weakness)
ENERGY_SEARCH = 1119     # item: search a Basic Energy to hand
BUDDY_POFFIN = 1086      # item: put up to 2 Basic (<=70HP) Pokémon onto the bench
POKEGEAR = 1122          # item: look top 7, may take a Supporter
MEGA_SIGNAL = 1145       # item: search a Mega Evolution ex to hand
SWITCH = 1123            # item: switch Active with a benched Pokémon
NIGHT_STRETCHER = 1097   # item: recover a Pokémon or Basic Energy from discard
GRAVITY_MOUNTAIN = 1252  # stadium: each Stage-2 in play (both sides) -30 HP (our Megas are Stage-1)
BASIC_WATER = 3
MIST_ENERGY = 11
IGNITION_ENERGY = 17     # provides {C}{C}{C} on an Evolution Pokémon (one attach powers Nebula Beam)
LEGACY_ENERGY = 12

# Attack IDs.
JETTING_BLOW = 1487      # 120 + 50 bench, cost {W}
NEBULA_BEAM = 1488       # 210 fixed, ignores weakness/resistance/effects, cost {C}{C}{C}
WATER_GUN = 1486         # Staryu 20
ABSOLUTE_SNOW = 1241     # 150 + Sleep, cost {W}{C}{C}
RESENTFUL_REFRAIN = 1240 # 50 x opp hand size, cost {W}
CHILLY = 1239            # Snorunt 10

MEGAS = {MEGA_STARMIE, MEGA_FROSLASS}
BASICS = {STARYU, SNORUNT}
_SIGNATURE = {SNORUNT, MEGA_FROSLASS, STARYU, MEGA_STARMIE}

# Weakness-aware lines. Mega Starmie ex (1031) is WEAK TO LIGHTNING -> a Lightning attacker (Iono's
# Bellibolt ex deck) OHKOs it through weakness and banks 3 prizes. Mega Froslass ex (861) is weak to
# METAL, not Lightning, so vs a detected Lightning opponent we race with the Froslass line and keep
# the Lightning-weak Starmie line off the active. These two opposite lines let us dodge the weakness
# without giving up the deck's prize-race plan.
FROSLASS_LINE = {SNORUNT, MEGA_FROSLASS}
STARMIE_LINE = {STARYU, MEGA_STARMIE}
try:
    _LIGHTNING = int(EnergyType.LIGHTNING)
except Exception:
    _LIGHTNING = 4

# Full 60-card decklist for the lethal verifier's determinization.
STARMIE_DECK = (
    [SNORUNT] * 4 + [MEGA_FROSLASS] * 3 + [STARYU] * 4 + [MEGA_STARMIE] * 3
    + [SALVATORE] * 4 + [LILLIE_DET] * 4 + [WALLY_COMP] * 3 + [BOSS_ORDERS] * 2 + [HILDA] * 2
    + [BLACK_BELT] * 1 + [ENERGY_SEARCH] * 4 + [BUDDY_POFFIN] * 4 + [POKEGEAR] * 3
    + [MEGA_SIGNAL] * 2 + [SWITCH] * 2 + [NIGHT_STRETCHER] * 1 + [GRAVITY_MOUNTAIN] * 2
    + [BASIC_WATER] * 9 + [MIST_ENERGY] * 1 + [IGNITION_ENERGY] * 1 + [LEGACY_ENERGY] * 1
)
assert len(STARMIE_DECK) == 60, len(STARMIE_DECK)
_DECK_COUNTS = Counter(STARMIE_DECK)

# Pieces never to pitch if avoidable; the energy we actually attack with.
KEY_PIECES = MEGAS | BASICS | {SALVATORE, MEGA_SIGNAL, HILDA, BOSS_ORDERS}
ATTACK_ENERGY = {BASIC_WATER, IGNITION_ENERGY, MIST_ENERGY, LEGACY_ENERGY}

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

# ── engine tables ─────────────────────────────────────────────────────────────────────────────
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


def _energy_count(pk) -> int:
    try:
        return len(pk.energies or [])
    except Exception:
        try:
            return len(pk.energyCards or [])
        except Exception:
            return 0


def is_starmie_deck(state, me_i: int) -> bool:
    """True iff our side is piloting the Starmie/Froslass line (one of its mons is visible)."""
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


def _opp_active(state, me_i):
    try:
        op = state.players[1 - me_i].active
        if op and op[0] is not None:
            return op[0]
    except Exception:
        pass
    return None


def _my_bench(state, me_i):
    try:
        return [b for b in state.players[me_i].bench if b is not None]
    except Exception:
        return []


def _opp_bench(state, me_i):
    try:
        return [b for b in state.players[1 - me_i].bench if b is not None]
    except Exception:
        return []


def _have_mega_to_play(state, me_i) -> bool:
    """A Mega is already in play, in hand, or on a basic ready to evolve next turn."""
    try:
        me = state.players[me_i]
        for p in (list(me.active or []) + list(me.bench or [])):
            if _id(p) in MEGAS:
                return True
        for c in (me.hand or []):
            if _id(c) in MEGAS:
                return True
    except Exception:
        pass
    return False


def _basic_in_play_evolvable(state, me_i) -> bool:
    try:
        me = state.players[me_i]
        for p in (list(me.active or []) + list(me.bench or [])):
            if _id(p) in BASICS:
                return True
    except Exception:
        pass
    return False


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


# ── opponent archetype: Mega Abomasnow ex tank/control (kiyotah) ────────────────────────────────
# Its line — Kyogre 721 / Snover 722 / Mega Abomasnow ex 723 — and its Surfing Beach stadium are
# disjoint from every other CANDIDATE decklist (agent/opp_decks.py) AND from our own deck, so this
# gate can ONLY fire vs the tank: the mirror and all other matchups are byte-for-byte unchanged.
_ABOMA_SIGNATURE = {721, 722, 723}   # Kyogre / Snover / Mega Abomasnow ex (incl. pre-evolutions)
_SURFING_BEACH = 1262                # the tank's stadium


def _opp_is_aboma(state, me_i) -> bool:
    """True iff the opponent is piloting the Mega Abomasnow ex tank/control deck."""
    try:
        op = state.players[1 - me_i]
        for p in (list(op.active or []) + list(op.bench or [])):
            if p is None:
                continue
            if _id(p) in _ABOMA_SIGNATURE:
                return True
            for c in (getattr(p, "preEvolution", None) or []):
                if _id(c) in _ABOMA_SIGNATURE:
                    return True
        for c in (op.discard or []):
            if _id(c) in _ABOMA_SIGNATURE:
                return True
        for c in (state.stadium or []):
            if _id(c) == _SURFING_BEACH:
                return True
    except Exception:
        return False
    return False


# ── opponent-archetype gating: Dragapult ex spread/aggro matchup ────────────────────────────────
# We lose the Dragapult matchup ~30%: it Phantom-Dives (200 + six spread damage counters onto our
# bench) and races prizes. The id-gated tweaks below only fire when the opponent is *detected* as
# Dragapult, so they can never regress the mirror or any other matchup (default behaviour is
# untouched when _VS_DRAG is False).
try:
    from opp_detect import detect_opp as _detect_opp
except Exception:
    try:
        from agent.opp_detect import detect_opp as _detect_opp
    except Exception:
        _detect_opp = None
try:
    from opp_decks import CANDIDATES as _CANDIDATES
except Exception:
    try:
        from agent.opp_decks import CANDIDATES as _CANDIDATES
    except Exception:
        _CANDIDATES = {}
_DRAGAPULT_LIST = _CANDIDATES.get("dragapult")
# Dreepy/Drakloak/Dragapult ex: this evolution line is unique to the Dragapult candidate deck,
# so a single sighting on the opponent's side is a zero-false-positive archetype tell.
DRAGAPULT_LINE = {119, 120, 121}   # 119 Dreepy(basic,70), 120 Drakloak(s1,90), 121 Dragapult ex(s2,320)

_VS_DRAG = False  # set each frame by note_obs(): True iff opponent detected as Dragapult


def _vs_dragapult(obs, me_i) -> bool:
    """True iff the opponent is the Dragapult ex spread deck. Backstop is a direct sighting of the
    (deck-unique) Dragapult evolution line on the opponent's board/discard; otherwise we defer to the
    shared archetype detector, which sharpens as their discard accumulates."""
    try:
        op = obs.current.players[1 - me_i]
        for pk in (list(op.active or []) + list(op.bench or [])):
            if pk is None:
                continue
            if _id(pk) in DRAGAPULT_LINE:
                return True
            for c in (getattr(pk, "preEvolution", None) or []):
                if _id(c) in DRAGAPULT_LINE:
                    return True
        for c in (op.discard or []):
            if _id(c) in DRAGAPULT_LINE:
                return True
    except Exception:
        pass
    if _detect_opp is not None and _DRAGAPULT_LIST is not None:
        try:
            return _detect_opp(obs, None) is _DRAGAPULT_LIST
        except Exception:
            return False
    return False


# ── opponent-archetype gating: Mega Lucario ex Fighting beatdown matchup ─────────────────────────
# We lose the baseline950 (romanrozen Mega Lucario ex) matchup ~35-38%. It races with a single big
# Fighting attacker (Riolu -> Mega Lucario ex; Aura Jab 130 repeatable + re-attaches energy, Mega
# Brave 270 with a one-turn self-lockout; Hariyama 210 backup; Solrock/Lunatone support). Neither of
# our 3-prize Megas (Starmie 330 / Froslass 310) is weak to Fighting, so it is a prize race.
#
# The decisive lever (see _wally_reset_vs_lucario): because Aura Jab is only 130/turn and Mega Brave
# self-locks, a full-HP Mega can NEVER be KO'd in a single turn. So Wally's Comprehensive Care — full
# heal at the cost of returning all energy (normally a tempo trap) — turns our active into a wall:
# heal once it has soaked a Fighting hit, re-attach one {W}, and keep firing Jetting Blow (120 + 50
# snipe). Holding Wally + an energy, our Mega loops and the bot banks no prizes off it. Empirically
# +~11pt vs baseline950 at N>=1000. (Steering the attacker line / an attack-tempo bump / snipe- and
# Boss-deny-setup levers were all tried and discarded — each tested neutral-to-negative.)
#
# Every branch below is a strict no-op while `_VS_LUC` is False, so the mirror and all other matchups
# are byte-identical. The signature ids are unique to the Lucario shell (disjoint from our deck and
# from every other CANDIDATE / bot deck), so detection is zero-false-positive.
_LUCARIO_LINE = {673, 674, 675, 676, 677, 678}  # Makuhita/Hariyama/Lunatone/Solrock/Riolu/Mega Lucario ex
_VS_LUC = False  # set each frame by note_obs(); latched True once the Lucario shell is seen this game

# Wally heal-loop threshold: heal the active Mega once it has soaked >= this much damage. Grid-searched
# vs baseline950 at N>=1000 (60/90/110/130/150/200/260 all tested; 60-130 ~+11pt over inert, flat in
# that band, decaying above 150). 130 = "soaked exactly one Aura Jab". Strict no-op while _VS_LUC False.
# Line-steer / attack-tempo / snipe / Boss-deny levers were all tried and REMOVED: each tested neutral-
# to-negative at N>=600, so the only shipped lever is this heal-loop (mirrors the Lightning/Dragapult
# Wally gates, which exploit the same "neither Mega dies in one hit" fact).
_LUC_WALLY_DMG = 130.0


def _vs_lucario(obs, me_i) -> bool:
    """True iff the opponent is piloting the Mega Lucario ex Fighting beatdown. A single sighting of
    any card in the (deck-unique) Lucario shell on the opponent's board / pre-evolutions / discard is
    a zero-false-positive tell; reads only opponent-revealed info, like agent/opp_detect.detect_opp."""
    try:
        op = obs.current.players[1 - me_i]
        for pk in (list(op.active or []) + list(op.bench or [])):
            if pk is None:
                continue
            if _id(pk) in _LUCARIO_LINE:
                return True
            for c in (getattr(pk, "preEvolution", None) or []):
                if _id(c) in _LUCARIO_LINE:
                    return True
        for c in (op.discard or []):
            if _id(c) in _LUCARIO_LINE:
                return True
    except Exception:
        return False
    return False


def vs_lucario() -> bool:
    return _VS_LUC


# ── opponent-archetype gating: Crustle damage-prevention wall matchup ────────────────────────────
# Crustle (Dwebble 344 -> Crustle 345, 150HP) carries an Ability that PREVENTS all damage done to it
# by Pokémon-ex / Mega-ex attacks, and the deck runs healing. Our list is 100% Mega-ex (Mega Starmie
# 1031 / Mega Froslass 861), so Jetting Blow / Absolute Snow / Resentful Refrain are ALL negated — a
# 0-prize shutout (confirmed live ladder loss, ep 81516269). Our ONLY out is Mega Starmie ex's NEBULA
# BEAM (1488, {C}{C}{C}, 210) which IGNORES weakness/resistance AND all effects on the opponent's
# Active, so it pierces the negation and two-shots (or one-shots a chipped) 150HP Crustle. The branches
# below steer the entire plan toward "Mega Starmie -> {C}{C}{C} -> Nebula Beam": prioritise the Starmie
# line for fetch / placement / evolve / energy-attach (Ignition Energy 17 = CCC in one attach on an
# Evolution), de-prioritise the negated Jetting Blow / Froslass attacks vs the wall, and rank Nebula
# Beam above the negated attacks once it is online. Crustle/Dwebble (344/345) appear ONLY in the
# crustle / crustle_hardened bot decks — disjoint from our deck and every other CANDIDATE / bot deck —
# so detection is zero-false-positive, and every branch is a strict no-op while `_VS_CRU` is False, so
# the mirror and all other matchups are byte-identical.
_CRUSTLE_LINE = {344, 345}   # Dwebble (basic) / Crustle (stage1, 150HP, ex-damage-prevention wall)
_VS_CRU = False  # set each frame by note_obs(); latched True once the Crustle line is seen this game


def _vs_crustle(obs, me_i) -> bool:
    """True iff the opponent is piloting the Crustle damage-prevention wall. A single sighting of
    Dwebble/Crustle (344/345) on the opponent's board / pre-evolutions / discard is a zero-false-
    positive tell; reads only opponent-revealed info, like agent/opp_detect.detect_opp."""
    try:
        op = obs.current.players[1 - me_i]
        for pk in (list(op.active or []) + list(op.bench or [])):
            if pk is None:
                continue
            if _id(pk) in _CRUSTLE_LINE:
                return True
            for c in (getattr(pk, "preEvolution", None) or []):
                if _id(c) in _CRUSTLE_LINE:
                    return True
        for c in (op.discard or []):
            if _id(c) in _CRUSTLE_LINE:
                return True
    except Exception:
        return False
    return False


def vs_crustle() -> bool:
    return _VS_CRU


# ── prize-tracker integration (the deck's edge) ────────────────────────────────────────────────
try:
    from prize_tracker import PrizeTracker
except Exception:
    try:
        from agent.prize_tracker import PrizeTracker
    except Exception:
        PrizeTracker = None

_TRACKER = None
_LAST_PRIZE = None
_GO_FIRST = True  # aggro deck: set up a turn earlier by going first (A/B-verified +~4pts)
# Sticky-within-a-game flag: have we seen a LIGHTNING-type Pokémon on the opponent's side? This is
# the only matchup where our Mega Starmie's Lightning weakness gets exploited (the Iono / Bellibolt
# deck is the only Lightning deck in the field — Raging Bolt ex is Dragon-typed, Dragapult Dragon,
# Abomasnow Water). Latched True once seen so a transient empty board doesn't flip it back off, and
# reset per game. Every Lightning-gated branch below is a strict no-op while this is False, so other
# matchups (and the mirror) are byte-identical to before.
_OPP_LIGHTNING = False


def _anti_lightning() -> bool:
    """True only when the opponent has revealed a LIGHTNING-type Pokémon. Every Lightning-gated branch
    is a strict no-op while this is False, so no other matchup (and not the mirror) can change. The
    only Lightning deck in the bot field is Iono's Bellibolt ex (Raging Bolt ex is Dragon-typed,
    Dragapult Dragon, Abomasnow Water), so in practice this fires exactly in the Iono matchup."""
    return _OPP_LIGHTNING


def _scan_opp_lightning(state, me_i) -> bool:
    """True iff a revealed opponent Pokémon (active / bench / their pre-evolutions / discard) is a
    LIGHTNING-type card. Reads only opponent-revealed info, exactly like agent/opp_detect.detect_opp,
    so it can never see a card the rules engine is hiding."""
    try:
        op = state.players[1 - me_i]
    except Exception:
        return False
    seen = []
    try:
        for p in (list(op.active or []) + list(op.bench or [])):
            if p is None:
                continue
            seen.append(_id(p))
            for c in (getattr(p, "preEvolution", None) or []):
                if c is not None:
                    seen.append(_id(c))
        for c in (op.discard or []):
            if c is not None:
                seen.append(_id(c))
    except Exception:
        return False
    for cid in seen:
        cd = _meta(cid)
        if cd is None:
            continue
        try:
            if int(getattr(cd, "energyType", -1)) == _LIGHTNING:
                return True
        except Exception:
            continue
    return False


def opp_is_lightning() -> bool:
    return _OPP_LIGHTNING


def note_obs(obs, obs_dict, me_i) -> None:
    """Update the per-game prize tracker + the Lightning/Dragapult opponent flags. Called every frame."""
    global _TRACKER, _LAST_PRIZE, _OPP_LIGHTNING, _VS_DRAG, _VS_LUC, _VS_CRU
    try:
        _VS_DRAG = _vs_dragapult(obs, me_i)
    except Exception:
        _VS_DRAG = False
    try:
        pc = len(obs.current.players[me_i].prize)
        # New game (prizes only decrease within a game; an increase => fresh battle).
        if _TRACKER is None or (_LAST_PRIZE is not None and pc > _LAST_PRIZE):
            if PrizeTracker is not None:
                _TRACKER = PrizeTracker(STARMIE_DECK)
            _OPP_LIGHTNING = False        # fresh game -> re-detect the matchup from scratch
            _VS_LUC = False
            _VS_CRU = False
        _LAST_PRIZE = pc
        if _TRACKER is not None:
            _TRACKER.update(obs, obs_dict)
        if not _OPP_LIGHTNING and _scan_opp_lightning(obs.current, me_i):
            _OPP_LIGHTNING = True         # latch: stays set for the rest of this game
        if not _VS_LUC and _vs_lucario(obs, me_i):
            _VS_LUC = True                # latch: stays set for the rest of this game
        if not _VS_CRU and _vs_crustle(obs, me_i):
            _VS_CRU = True                # latch: stays set for the rest of this game
    except Exception:
        pass


def _prized():
    if _TRACKER is None:
        return None
    try:
        return _TRACKER.prized_cards()
    except Exception:
        return None


def _deck_available(state, me_i, card_id) -> int:
    """How many copies of `card_id` are (conservatively) still in the draw pile, i.e. not visible
    and not known-prized. Unknown prizes count as available — a wrong inference is worse than none.
    """
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
        for p in (list(me.active or []) + list(me.bench or [])):
            if p is None:
                continue
            if _id(p) == card_id:
                visible += 1
            for c in (getattr(p, "preEvolution", None) or []):
                if _id(c) == card_id:
                    visible += 1
            for c in (getattr(p, "energies", None) or getattr(p, "energyCards", None) or []):
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
    prized = _prized()
    if prized is not None:
        pr = prized.get(card_id, 0)
    return max(0, total - visible - pr)


def _mega_available_in_deck(state, me_i) -> bool:
    return _deck_available(state, me_i, MEGA_STARMIE) > 0 or _deck_available(state, me_i, MEGA_FROSLASS) > 0


def _basic_available_in_deck(state, me_i) -> bool:
    return _deck_available(state, me_i, STARYU) > 0 or _deck_available(state, me_i, SNORUNT) > 0


# ── attack evaluation ───────────────────────────────────────────────────────────────────────────
def _eff_damage(active, attack_id, opp_active, opp) -> int:
    """Effective damage to the opponent's Active for a Starmie attack (special-cases the fixed /
    scaling / weakness-ignoring attacks; otherwise weakness-aware via the generic helper)."""
    if attack_id == NEBULA_BEAM:
        return 210  # fixed; ignores weakness/resistance/effects
    if attack_id == RESENTFUL_REFRAIN:
        return 50 * max(0, getattr(opp, "handCount", 0) or 0)
    try:
        from scorer import _attack_damage
        d = _attack_damage(active, attack_id, opp_active)
        if d:
            return d
    except Exception:
        pass
    atk = _ATK.get(attack_id)
    return (atk.damage or 0) if atk is not None else 0


# MAIN priority bands. The proven ordering is DIG/DRAW BEFORE YOU COMMIT: play search/draw
# (Lillie / Salvatore / Hilda / Mega Signal / Buddy Poffin / Energy Search / Pokégear) to see more
# cards, THEN evolve, THEN attach energy, THEN attack (attacking ends the turn). Boss / Black Belt
# are pre-attack setup, so they outrank the draw supporters *only* when they actually do work. The
# id-gated overrides below differ from the generic scorer exactly where the generic scorer misplays
# this deck: it heals with Wally (stripping the attacker's Energy), Switches pointlessly, and under-
# rates the board engine. Everything else mirrors the generic draw-first instinct.
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        bench_n = len(_my_bench(state, me_i))
        sup_done = bool(getattr(state, "supporterPlayed", False))
        stad_done = bool(getattr(state, "stadiumPlayed", False))
        need_fuel = active is not None and _id(active) in (MEGAS | BASICS) and _energy_count(active) < 3

        # ---- pre-attack supporters that do real work outrank the draw engine (one supporter/turn) --
        if cid == BOSS_ORDERS:             # gust + KO a benched target for the prize race
            if sup_done:
                return -1.0
            return 1950.0 if _good_gust_target(obs, state, me_i) is not None else -1.0
        if cid == BLACK_BELT:              # +40 to opp Active ex: only when it converts a KO
            if sup_done:
                return -1.0
            return 1920.0 if _black_belt_enables_ko(state, me_i) else -1.0

        # ---- draw / search engine (dig before committing) -----------------------------------------
        if cid == SALVATORE:               # search-evolve a Pokémon in play straight to a Mega
            if sup_done:
                return -1.0
            if _basic_in_play_evolvable(state, me_i) and _mega_available_in_deck(state, me_i):
                return 1850.0
            return -1.0
        if cid == HILDA:                   # tutor an Evolution + an Energy to hand
            if sup_done:
                return -1.0
            return 1820.0 if _mega_available_in_deck(state, me_i) else 60.0
        if cid == LILLIE_DET:              # shuffle hand, draw 6/8: refuel a thin hand
            if sup_done:
                return -1.0
            hand_n = len(state.players[me_i].hand or [])
            if hand_n <= 4:
                return 1800.0
            if hand_n <= 6:
                return 1500.0
            return -1.0                    # loaded hand -> shuffling it away is a loss
        if cid == MEGA_SIGNAL:             # item: tutor a Mega ex to hand
            if not _mega_available_in_deck(state, me_i):
                return -1.0                # all Megas prized/visible -> whiff
            return 1750.0 if not _have_mega_to_play(state, me_i) else 350.0
        if cid == BUDDY_POFFIN:            # both basics are 70HP -> the whole line; vital when thin
            if not _basic_available_in_deck(state, me_i):
                return -1.0
            if bench_n <= 1:
                return 1780.0
            if bench_n <= 3:
                return 1650.0
            return 250.0
        if cid == ENERGY_SEARCH:           # item: tutor a Basic Energy
            if _deck_available(state, me_i, BASIC_WATER) <= 0:
                return -1.0
            return 1700.0 if need_fuel else 300.0
        if cid == POKEGEAR:                # item: dig for a Supporter
            return 1600.0 if not sup_done else 300.0
        if cid == NIGHT_STRETCHER:         # item: recover a key piece from discard
            try:
                if any(_id(c) in (MEGAS | BASICS) for c in (state.players[me_i].discard or [])):
                    return 1550.0
            except Exception:
                pass
            return 250.0

        # ---- the generic-scorer misplays we override ----------------------------------------------
        if cid == SWITCH:                  # only to promote a ready Mega over a stuck basic active
            if _id(active) in BASICS and any(_id(b) in MEGAS for b in _my_bench(state, me_i)):
                return 1450.0
            # vs Lightning: swap the Lightning-weak Mega Starmie active (a free 3-prize OHKO via
            # weakness) for a benched Mega Froslass (weak Metal -> survives the ~230 hit, and is the
            # mon we keep alive with the Wally heal-loop below). Switch is free and keeps energy.
            if (_anti_lightning() and _id(active) == MEGA_STARMIE
                    and any(_id(b) == MEGA_FROSLASS for b in _my_bench(state, me_i))):
                return 1455.0
            return -1.0                    # generic Switches pointlessly (de-fuels its own attacker)
        if cid == WALLY_COMP:              # heal a Mega BUT strip its Energy -> usually a tempo trap
            if sup_done:
                return -1.0
            # vs Dragapult: Phantom Dive hits our Active for 200 but neither Mega (310/330HP) dies to
            # one — the KO comes from the FOLLOW-UP hit + spread. Wally fully heals (erases the 200 and
            # any spread counters) and the energy it strips is trivially re-attached for our 1-energy
            # {W} nuke (Resentful Refrain / Jetting Blow): they spent a whole turn for nothing while we
            # still attack. Turns our Mega into a wall that also races. Outranks the draw engine here.
            if _VS_DRAG and _wally_reset_vs_spread(state, me_i):
                return 1830.0
            # vs Lucario: the heal-loop wall. Aura Jab only does 130/turn and Mega Brave (270) self-
            # locks, so a full-HP Mega never dies in one turn; Wally fully heals our damaged active and
            # one re-attached {W} re-arms Jetting Blow (120 + 50 snipe). Holding Wally + an energy, our
            # 330HP Starmie loops (330 -> healed) while still racing, so the bot banks no prizes off it.
            if _VS_LUC and _wally_reset_vs_lucario(state, me_i):
                return 1830.0
            if not _wally_worth_it(state, me_i):
                return -1.0
            # vs Lightning the Wally heal-loop is our PRIMARY plan: heal the Mega Froslass tank before
            # the next ~230 hit kills it, then re-attach one {W} for Resentful Refrain. A Froslass at
            # 310 -> 80 -> healed 310 loops while we hold Wally, so the bot banks no prizes off it, so
            # the heal outranks the draw engine here (the single empirically positive anti-Iono lever).
            if _anti_lightning() and _id(_my_active(state, me_i)) == MEGA_FROSLASS:
                return 1830.0
            return 1100.0
        if cid == GRAVITY_MOUNTAIN:        # our Megas are Stage-1 (immune); only chips opp Stage-2s
            if stad_done:
                return -1.0
            return 500.0

        # Bare basic Pokémon from hand: board presence.
        cd = _meta(cid)
        if cd is not None and cd.cardType == CardType.POKEMON and getattr(cd, "basic", False):
            return 1700.0 if bench_n == 0 else 1300.0
        return 600.0

    if t == OptionType.EVOLVE:
        # every evolution here is a Mega ex; evolve after digging, before attaching.
        if _anti_lightning():
            ev = _id(_get(obs, AreaType.HAND, o.index, me_i))
            if ev == MEGA_FROSLASS:
                return 1360.0        # the Lightning-safe tank we want fronting + heal-looping
            if ev == MEGA_STARMIE and o.inPlayArea == AreaType.ACTIVE:
                return 250.0         # don't make the active a 3-prize Lightning-weak Mega
        if _VS_CRU:
            ev = _id(_get(obs, AreaType.HAND, o.index, me_i))
            if ev == MEGA_STARMIE:
                return 1380.0        # the only attacker (Nebula Beam) that pierces the ex-damage wall
        return 1300.0

    if t == OptionType.ATTACH:
        active = _my_active(state, me_i)
        if o.inPlayArea == AreaType.ACTIVE:
            if _id(active) in MEGAS:
                # vs Crustle: rush Mega Starmie to {C}{C}{C} so Nebula Beam (the only attack that
                # pierces the ex-damage-prevention wall) comes online a turn earlier.
                if _VS_CRU and _id(active) == MEGA_STARMIE and _energy_count(active) < 3:
                    return 1320.0
                return 1250.0 if _energy_count(active) < 3 else 1000.0
            if _id(active) in BASICS:
                # Energy carries through evolution: fuel a Staryu that will become the Nebula attacker.
                if _VS_CRU and _id(active) == STARYU and _energy_count(active) < 3:
                    return 1230.0
                return 1200.0  # fuel the soon-to-be Mega (energy carries through evolution)
            return 1050.0
        if o.inPlayArea == AreaType.BENCH:
            tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            if _id(tgt) in MEGAS:
                if _VS_CRU and _id(tgt) == MEGA_STARMIE and _energy_count(tgt) < 3:
                    return 1180.0
                return 1100.0 if _energy_count(tgt) < 3 else 1000.0
            if _id(tgt) in BASICS:
                if _VS_CRU and _id(tgt) == STARYU and _energy_count(tgt) < 3:
                    return 1080.0
                return 1050.0
            return 1000.0
        return 1000.0

    if t == OptionType.ABILITY:
        return 400.0

    if t == OptionType.ATTACK:
        # Attacking ENDS the turn, so the proven ordering is: do all free development first, attack
        # LAST. Keep attack below the develop/draw engine — EXCEPT a game-winning swing (KOs their
        # last prize), which there is never a reason to defer: take it immediately.
        active = _my_active(state, me_i)
        oa = _opp_active(state, me_i)
        score = 100.0
        dmg = _eff_damage(active, o.attackId, oa, state.players[1 - me_i])
        score += min(max(dmg, 0), 300) * 0.2
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 160.0  # KO
            try:                                   # game-winning KO takes their last prize(s)
                opp = state.players[1 - me_i]
                if len(opp.prize or []) <= _prize_count_for(oa):
                    return 50000.0
            except Exception:
                pass
        if o.attackId == JETTING_BLOW:
            score += 12.0    # the 50 bench snipe is real extra value (tiebreak)
        if o.attackId == NEBULA_BEAM and oa is not None:
            cd = _meta(_id(oa))
            if cd is not None and (getattr(cd, "ex", False) or getattr(cd, "megaEx", False)):
                score += 20.0  # effect-ignoring: robust vs damage-prevention walls / big ex
        if _VS_CRU:
            # Crustle negates all damage from our ex/Mega-ex attacks; only Nebula Beam (effect-ignoring)
            # actually lands. Rank it well above the negated Jetting Blow / Froslass attacks so we punch
            # through the wall instead of whiffing. (Strict no-op outside the Crustle matchup.)
            if o.attackId == NEBULA_BEAM:
                score += 300.0
            elif o.attackId in (JETTING_BLOW, ABSOLUTE_SNOW, RESENTFUL_REFRAIN):
                score -= 60.0  # negated vs the wall (kept >= END so the Jetting 50 bench-snipe still fires)
        if _opp_is_aboma(state, me_i):
            # Vs the slow Abomasnow tank our loss mode is durdling: the generic ordering keeps
            # playing marginal cards (a redundant search once a Mega is already set, Gravity
            # Mountain that can't touch our Stage-1s, a minor ability) while the tank out-grinds the
            # prize race. A bounded +250 lifts an available attack above only those low-value
            # develop options — it stays well under the real engine (draw/evolve/attach at 1300+),
            # so we still set up, but we stop wasting the proactive racer's tempo. (+~3pt vs the
            # tank at N=1000, gated so no other matchup or the mirror moves; tuned: +120/+500 both
            # test weaker, and forcing KOs over all development backfires.)
            score += 250.0
        return score

    if t == OptionType.RETREAT:
        # Promote a benched Mega when stuck with a bare basic active.
        active = _my_active(state, me_i)
        if _id(active) in BASICS and any(_id(b) in MEGAS for b in _my_bench(state, me_i)):
            return 120.0
        # vs Lightning, if no Switch is in hand, retreat the Lightning-weak Mega Starmie out for a
        # benched Mega Froslass so we don't hand over a 3-prize OHKO.
        if (_anti_lightning() and _id(active) == MEGA_STARMIE
                and any(_id(b) == MEGA_FROSLASS for b in _my_bench(state, me_i))):
            return 110.0
        return -1.0

    if t == OptionType.END:
        return 0.0
    if t == OptionType.YES:
        return 5.0
    if t == OptionType.NO:
        return 3.0
    return 1.0


def _best_attack_damage(state, me_i):
    """Max effective damage our Active can deal to the opponent's Active this turn (rough; assumes
    its listed attacks are affordable — used only to gate Boss/Black-Belt decisions)."""
    active = _my_active(state, me_i)
    oa = _opp_active(state, me_i)
    if active is None:
        return 0, None
    cd = _meta(_id(active))
    best = 0
    if cd is not None:
        for a in (getattr(cd, "attacks", None) or []):
            aid = getattr(a, "attackId", None)
            best = max(best, _eff_damage(active, aid, oa, state.players[1 - me_i]))
    return best, oa


def _good_gust_target(obs, state, me_i):
    """Return a benched opponent Pokémon worth gusting (one we can KO this turn for a prize, or the
    only KO available when their Active is out of reach), else None."""
    best_dmg, oa = _best_attack_damage(state, me_i)
    if best_dmg <= 0:
        return None
    active_koable = oa is not None and best_dmg >= (oa.hp or 0)
    target = None
    target_val = 0.0
    for b in _opp_bench(state, me_i):
        if best_dmg >= (b.hp or 0):                      # we can KO it after gusting
            val = _opponent_value(b) + _prize_count_for(b) * 100.0
            # Prefer gusting when the active is NOT KOable (otherwise just hit the active) or the
            # benched target is clearly juicier (a powered-up / multi-prize backup).
            if (not active_koable) or val > _opponent_value(oa) + _prize_count_for(oa) * 100.0 + 60.0:
                if val > target_val:
                    target, target_val = b, val
    return target


def _black_belt_enables_ko(state, me_i) -> bool:
    best_dmg, oa = _best_attack_damage(state, me_i)
    if oa is None:
        return False
    cd = _meta(_id(oa))
    is_ex = cd is not None and (getattr(cd, "ex", False) or getattr(cd, "megaEx", False))
    if not is_ex:
        return False  # +40 only applies to an ex active
    hp = oa.hp or 0
    return best_dmg < hp <= best_dmg + 40  # converts a non-KO into a KO


def _wally_worth_it(state, me_i) -> bool:
    """Wally heals fully but returns ALL energy to hand. Only worth it when an active Mega is badly
    hurt (would die soon) AND we can re-power it (energy waiting in hand)."""
    active = _my_active(state, me_i)
    if _id(active) not in MEGAS:
        return False
    hp = active.hp or 0
    maxhp = getattr(active, "maxHp", 0) or 0
    if maxhp <= 0:
        return False
    try:
        hand = state.players[me_i].hand or []
        have_energy = any(_id(c) in ATTACK_ENERGY for c in hand)
    except Exception:
        have_energy = False
    # vs Lightning: heal the Lightning-safe Mega Froslass *before* the opponent's next ~230 hit
    # finishes it (i.e. once it has taken a big hit), not only at <40%. Re-attaching one {W} powers
    # Resentful Refrain, so a Froslass at 310 -> 80 -> healed 310 loops and the bot banks no prize.
    if _anti_lightning() and _id(active) == MEGA_FROSLASS and have_energy:
        if hp <= maxhp - 150:
            return True
    if hp > maxhp * 0.4:
        return False
    return have_energy


def _wally_reset_vs_lucario(state, me_i) -> bool:
    """Vs Lucario: our active is a Mega that has soaked a real Fighting hit (>= _LUC_WALLY_DMG) and we
    can re-power its 1-energy {W} attack from hand. Wally fully heals it; since Aura Jab is only 130 a
    turn (and Mega Brave self-locks), the healed Mega can never be KO'd in the gap — it walls + races.
    Requires a spare {W}/attack energy in hand. Strict no-op outside the Lucario matchup."""
    if _LUC_WALLY_DMG <= 0:
        return False
    active = _my_active(state, me_i)
    if _id(active) not in MEGAS:
        return False
    hp = active.hp or 0
    maxhp = getattr(active, "maxHp", 0) or 0
    if maxhp <= 0:
        return False
    if (maxhp - hp) < _LUC_WALLY_DMG:    # hasn't taken a real hit yet — don't waste the heal
        return False
    try:
        hand = state.players[me_i].hand or []
        return any(_id(c) in ATTACK_ENERGY for c in hand)
    except Exception:
        return False


def _wally_reset_vs_spread(state, me_i) -> bool:
    """Vs Dragapult: our Active is a Mega that has soaked a Phantom Dive (>=120 damage) and we can
    re-power its 1-energy {W} attack from hand — Wally erases the damage AND any spread counters, so
    they wasted a 200-hit while we keep attacking. Requires a spare {W}/attack energy in hand."""
    active = _my_active(state, me_i)
    if _id(active) not in MEGAS:
        return False
    hp = active.hp or 0
    maxhp = getattr(active, "maxHp", 0) or 0
    if maxhp <= 0:
        return False
    if (maxhp - hp) < 120:        # hasn't taken a real hit yet — don't waste the heal
        return False
    try:
        hand = state.players[me_i].hand or []
        return any(_id(c) in ATTACK_ENERGY for c in hand)
    except Exception:
        return False


# ── forced sub-selection scoring ────────────────────────────────────────────────────────────────
def score_sub(obs, o, me_i, context) -> float:
    state = obs.current
    t = o.type
    score = 2000.0

    if t == OptionType.NUMBER:
        return score + (getattr(o, "number", 0) or 0)

    if t == OptionType.YES:
        if context == SelectContext.IS_FIRST:
            # Aggro deck with a 1-Energy attack (Jetting Blow): set up a turn earlier by going first.
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

        # Damage / boss / gust targeting: opponent's most valuable, prefer active.
        if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
                       SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET):
            if isinstance(card, Pokemon) and pidx != me_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 250.0
            elif isinstance(card, Pokemon):
                score -= _opponent_value(card)
            return score

        # Discarding / pitching: dump spare Water energy first; protect the Mega line + tutors.
        if context in GIVE_UP_CTX:
            cd = _meta(cid)
            if cd is not None:
                if cid == BASIC_WATER:
                    return score + 60.0
                if cid in KEY_PIECES or cd.cardType in (CardType.POKEMON, CardType.SUPPORTER):
                    return score - 200.0
                if cd.cardType in (CardType.SPECIAL_ENERGY, CardType.TOOL):
                    return score - 120.0
            return score

        # Search/tutor targets (TO_HAND from deck) + placement: prioritise the engine pieces.
        if isinstance(card, Pokemon):
            if pidx != me_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 200.0
                return score
            # Our own mon (setup, evolve, fetch, switch-in).
            if cid in MEGAS:
                score += 320.0     # a Mega attacker is the best fetch/placement
                # Froslass's Resentful Refrain costs only {W} (online turn 2, fast clock), vs
                # Starmie's Nebula Beam {C}{C}{C} (turn 4). Bias the line toward Froslass so we
                # win the prize race with the cheaper attacker (+2pt mirror win-rate, 5000 games).
                if cid == MEGA_FROSLASS:
                    score += 40.0 if o.area == AreaType.ACTIVE else 20.0
            elif cid in BASICS:
                score += 180.0
                if cid == SNORUNT:
                    score += 40.0 if o.area == AreaType.ACTIVE else 20.0
                if len(_my_bench(state, me_i)) == 0:
                    score += 220.0  # empty bench -> a body is urgent
            # vs a detected Lightning opponent: steer fetch / placement / evolve-target / promote.
            # No-op (score unchanged) outside the Lightning matchup.
            if _anti_lightning():
                # Steer every fetch / placement / evolve-target / promote toward the Lightning-safe
                # Froslass line and keep the Lightning-weak Starmie line off the ACTIVE (a benched
                # Starmie is still a fine backup, so only the active is penalised).
                to_active = (o.area == AreaType.ACTIVE)
                if cid in FROSLASS_LINE:
                    score += 220.0 if to_active else 90.0
                elif cid in STARMIE_LINE and to_active:
                    score -= 700.0
            # vs Crustle: the inverse of the default Froslass bias — only Mega Starmie's Nebula Beam
            # pierces the ex-damage wall, so steer fetch / placement / evolve-target / promote toward
            # the Starmie line and keep the (fully-negated) Froslass attacker off the ACTIVE. No-op
            # outside the Crustle matchup. (Lightning + Crustle are mutually exclusive matchups.)
            if _VS_CRU:
                to_active = (o.area == AreaType.ACTIVE)
                if cid in STARMIE_LINE:
                    score += 220.0 if to_active else 90.0
                elif cid in FROSLASS_LINE and to_active:
                    score -= 200.0
            if context in PLACEMENT_CTX:
                score += 400.0
            return score

        # Non-Pokémon fetch (energy / supporter tutoring).
        cd = _meta(cid)
        if cd is not None:
            active = _my_active(state, me_i)
            need_energy = active is not None and _id(active) in (MEGAS | BASICS) and _energy_count(active) < 3
            if cid in ATTACK_ENERGY:
                score += 120.0 if need_energy else 40.0
                # vs Crustle, Ignition Energy provides {C}{C}{C} on an Evolution in one attach -> it
                # brings Mega Starmie's wall-piercing Nebula Beam online a full turn early.
                if _VS_CRU and cid == IGNITION_ENERGY:
                    score += 150.0
            elif cid in (SALVATORE, MEGA_SIGNAL, HILDA):
                score += 90.0 if not _have_mega_to_play(state, me_i) else 30.0
            elif cid == BOSS_ORDERS:
                score += 80.0 if _opp_bench(state, me_i) else 10.0
        return score

    return score

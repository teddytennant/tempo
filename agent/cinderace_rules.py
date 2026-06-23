"""Cinderace + Mega Starmie ex specialist scoring (id-gated), consulted by agent/scorer.best_options.

The deck (data/decks/cinderace_starmie.csv) is keidroid's #1-leaderboard "Mega Starmie ex /
Cinderace / Crushing Hammer" list (~1373 LB). It is the high-ceiling answer to the two structural
problems of the pure-Mega Starmie/Froslass list:

  • Cinderace (666, NON-ex, 160HP, Fire) — the engine + wall-breaker.
      - Ability "Explosiveness": at setup it may be placed face-down directly into the Active Spot
        (no Scorbunny/Raboot line needed — the deck runs none). So game 1 it fronts the board.
      - Turbo Flare (965): {C} -> 50 damage AND search the deck for up to 3 Basic Energy and attach
        them to the BENCH. This is the energy engine: it ramps a benched Staryu/Mega Starmie while
        chipping. Being NON-ex (1 prize), its 50 damage is NOT negated by Crustle's ex-damage-
        prevention wall — Cinderace is the card that actually breaks Crustle.
  • Mega Starmie ex (1031, 330HP, Water) — the primary attacker / KO engine.
      - Jetting Blow  (1487): {W}        -> 120 + 50 to a benched mon. Online turn 1-2.
      - Nebula Beam   (1488): {C}{C}{C}  -> 210, IGNORES weakness/resistance AND all effects on the
                                            opponent's Active (pierces damage-prevention walls).
      - Ignition Energy (17) provides {C}{C}{C} on an Evolution, so one attach arms Nebula Beam.
  • 4x Crushing Hammer (1120) — energy denial: flip a coin, heads = discard an opposing Energy. Knocks
    the opponent's attacker off attack-range (decisive in the mirror / vs every energy-hungry deck).
  • 4x Wally's Compassion (1229) — fully heal a Mega ex but return its Energy to hand: the heal-loop
    that protects our 3-prize Mega Starmie from ever being banked.

Like the other specialists this is a pure-fresh-scan id gate: `is_cinderace_deck(state, me_i)` fires
only when a card UNIQUE to this list (Cinderace / Crushing Hammer / Harlequin / Ultra Ball / Hero's
Cape) is visible on OUR side, so it never routes the sibling Starmie/Froslass deck (which shares the
Starmie line) or any other deck through here — the generic path is untouched.
"""
from __future__ import annotations

from collections import Counter

from cg.api import (
    AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext, all_attack, all_card_data,
)

# ── deck card IDs (verified via all_card_data against data/decks/cinderace_starmie.csv) ─────────
CINDERACE = 666          # Stage 2, NON-ex, 160HP Fire; setup-active ability + Turbo Flare ramp/break
STARYU = 1030            # basic, 70HP, evolves -> Mega Starmie ex
MEGA_STARMIE = 1031      # stage1 megaEx, 330HP, weak Lightning; primary attacker
SALVATORE = 1189         # supporter: search an Evolution (no Ability) and evolve a Pokémon in play
HILDA = 1225             # supporter: search an Evolution Pokémon + an Energy to hand
LILLIE_DET = 1227        # supporter: shuffle hand, draw 6 (8 if exactly 6 prizes)
HARLEQUIN = 1223         # supporter: both shuffle hand to deck, coin flip -> you draw 5/opp 3 or vice versa
WALLY_COMP = 1229        # supporter: heal a Mega ex fully BUT return all its energy to hand
BOSS_ORDERS = 1182       # supporter: gust a benched opponent Pokémon to Active
BUDDY_POFFIN = 1086      # item: put up to 2 Basic (<=70HP) Pokémon onto the bench (Staryu only here)
POKEGEAR = 1122          # item: look top 7, may take a Supporter
MEGA_SIGNAL = 1145       # item: search a Mega Evolution ex to hand
ULTRA_BALL = 1121        # item: discard 2 from hand, search ANY Pokémon to hand
NIGHT_STRETCHER = 1097   # item: recover a Pokémon or Basic Energy from discard
CRUSHING_HAMMER = 1120   # item: flip a coin, heads -> discard an Energy from an opponent's Pokémon
HERO_CAPE = 1159         # tool (ACE SPEC): +100 HP to the Pokémon it's attached to
BASIC_WATER = 3          # 9x — the deck's only basic energy (Cinderace ramps these)
IGNITION_ENERGY = 17     # special: provides {C}{C}{C} on an Evolution (one attach powers Nebula Beam)

# Attack IDs.
TURBO_FLARE = 965        # Cinderace: 50 + search 3 Basic Energy to bench (ramp), cost {C}
WATER_GUN = 1486         # Staryu 20
JETTING_BLOW = 1487      # Mega Starmie 120 + 50 bench snipe, cost {W}
NEBULA_BEAM = 1488       # Mega Starmie 210 fixed, ignores weakness/resistance/effects, cost {C}{C}{C}

MEGAS = {MEGA_STARMIE}
BASICS = {STARYU}                  # only basic that evolves into our Mega (Cinderace has no basic here)
EVOLVERS = {STARYU}                # what Salvatore/evolution targets sit on
# Cards UNIQUE to this list (absent from the sibling Starmie/Froslass deck and every other our-deck),
# so a single sighting on OUR side is a zero-false-positive tell that we are piloting THIS deck.
_SIGNATURE = {CINDERACE, CRUSHING_HAMMER, HARLEQUIN, ULTRA_BALL, HERO_CAPE}

try:
    _LIGHTNING = int(EnergyType.LIGHTNING)
except Exception:
    _LIGHTNING = 4

# Full 60-card decklist for the lethal verifier's determinization.
CINDERACE_DECK = (
    [BASIC_WATER] * 9 + [IGNITION_ENERGY] * 4 + [CINDERACE] * 4 + [STARYU] * 3 + [MEGA_STARMIE] * 3
    + [BUDDY_POFFIN] * 4 + [POKEGEAR] * 4 + [MEGA_SIGNAL] * 4 + [SALVATORE] * 4 + [HILDA] * 2
    + [LILLIE_DET] * 4 + [HARLEQUIN] * 2 + [ULTRA_BALL] * 1 + [NIGHT_STRETCHER] * 2
    + [CRUSHING_HAMMER] * 4 + [WALLY_COMP] * 4 + [BOSS_ORDERS] * 1 + [HERO_CAPE] * 1
)
assert len(CINDERACE_DECK) == 60, len(CINDERACE_DECK)
_DECK_COUNTS = Counter(CINDERACE_DECK)

KEY_PIECES = MEGAS | BASICS | {CINDERACE, SALVATORE, MEGA_SIGNAL, HILDA, BOSS_ORDERS, HERO_CAPE}
ATTACK_ENERGY = {BASIC_WATER, IGNITION_ENERGY}

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


def _energy_count(pk) -> int:
    try:
        return len(pk.energies or [])
    except Exception:
        try:
            return len(pk.energyCards or [])
        except Exception:
            return 0


def is_cinderace_deck(state, me_i: int) -> bool:
    """True iff our side is piloting the Cinderace/Mega Starmie list (a list-UNIQUE card is visible).

    Pure fresh scan (no latch) — exactly like is_starmie_deck — so the same scorer process can pilot a
    different deck on a later job without leaking a stale True. Gated on cards unique to this list
    (Cinderace / Crushing Hammer / Harlequin / Ultra Ball / Hero's Cape), so the sibling Starmie/
    Froslass deck (which shares the Staryu/Mega Starmie line) is never routed through here.
    """
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
    """A Mega is already in play, in hand, or on a Staryu ready to evolve next turn."""
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
            if _id(p) in EVOLVERS:
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


def _has_tool(pk) -> bool:
    try:
        return bool(getattr(pk, "tools", None))
    except Exception:
        return False


# ── opponent-archetype gating: Crustle damage-prevention wall ────────────────────────────────────
# Crustle (Dwebble 344 -> Crustle 345, 150HP) PREVENTS all damage from Pokémon-ex / Mega-ex attacks.
# Mega Starmie's ex attacks (Jetting Blow) are negated, but TWO of our cards still punch through:
# Cinderace's Turbo Flare (NON-ex 50 + ramp) and Mega Starmie's Nebula Beam (effect-ignoring 210).
# Every branch is a strict no-op while _VS_CRU is False, so the mirror/other matchups are byte-identical.
_CRUSTLE_LINE = {344, 345}
_VS_CRU = False

# Mega Lucario ex Fighting beatdown shell (baseline950). Aura Jab is only 130/turn and Mega Brave (270)
# self-locks, so a full-HP Mega Starmie (330) never dies in one turn -> the Wally heal-loop walls it.
_LUCARIO_LINE = {673, 674, 675, 676, 677, 678}
_VS_LUC = False
_LUC_WALLY_DMG = 130.0


def _vs_crustle(obs, me_i) -> bool:
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


def _vs_lucario(obs, me_i) -> bool:
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


def vs_crustle() -> bool:
    return _VS_CRU


# ── prize-tracker integration (refuse to play a search whose only target is prized) ─────────────
try:
    from prize_tracker import PrizeTracker
except Exception:
    try:
        from agent.prize_tracker import PrizeTracker
    except Exception:
        PrizeTracker = None

_TRACKER = None
_LAST_PRIZE = None
_GO_FIRST = True  # start ramping (Cinderace Turbo Flare) a turn earlier


def note_obs(obs, obs_dict, me_i) -> None:
    """Update the per-game prize tracker + the Crustle/Lucario opponent latches. Called every frame."""
    global _TRACKER, _LAST_PRIZE, _VS_CRU, _VS_LUC
    try:
        pc = len(obs.current.players[me_i].prize)
        if _TRACKER is None or (_LAST_PRIZE is not None and pc > _LAST_PRIZE):
            if PrizeTracker is not None:
                _TRACKER = PrizeTracker(CINDERACE_DECK)
            _VS_CRU = False      # fresh game -> re-detect the matchup from scratch
            _VS_LUC = False
        _LAST_PRIZE = pc
        if _TRACKER is not None:
            _TRACKER.update(obs, obs_dict)
        if not _VS_CRU and _vs_crustle(obs, me_i):
            _VS_CRU = True       # latch: stays set for the rest of this game
        if not _VS_LUC and _vs_lucario(obs, me_i):
            _VS_LUC = True
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
    """Conservative count of copies of `card_id` still in the draw pile (not visible, not known-prized).
    Unknown prizes count as available — a wrong inference is worse than none."""
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
    return _deck_available(state, me_i, MEGA_STARMIE) > 0


def _basic_available_in_deck(state, me_i) -> bool:
    return _deck_available(state, me_i, STARYU) > 0


# ── attack evaluation ───────────────────────────────────────────────────────────────────────────
def _eff_damage(active, attack_id, opp_active, opp) -> int:
    """Effective damage to the opponent's Active for one of our attacks (special-cases the fixed /
    effect-ignoring attacks; otherwise weakness-aware via the generic helper)."""
    if attack_id == NEBULA_BEAM:
        return 210  # fixed; ignores weakness/resistance/effects
    try:
        from scorer import _attack_damage
        d = _attack_damage(active, attack_id, opp_active)
        if d:
            return d
    except Exception:
        pass
    atk = _ATK.get(attack_id)
    return (atk.damage or 0) if atk is not None else 0


def _opp_active_has_energy(state, me_i) -> bool:
    oa = _opp_active(state, me_i)
    return oa is not None and _energy_count(oa) >= 1


# ── MAIN priority bands ──────────────────────────────────────────────────────────────────────────
# Proven ordering: DIG/DRAW before you commit, evolve, attach, attack LAST (an attack ends the turn).
# Boss / Crushing Hammer / Hero's Cape are free pre-attack setup. The id-gated overrides differ from
# the generic scorer exactly where it misplays this deck (Wally stripping its own attacker's energy,
# under-rating the Cinderace ramp / the Crushing Hammer denial / the Nebula-Beam wall-break).
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        bench_n = len(_my_bench(state, me_i))
        sup_done = bool(getattr(state, "supporterPlayed", False))
        need_fuel = active is not None and _id(active) in (MEGAS | BASICS) and _energy_count(active) < 3

        # ---- free pre-attack ITEMS that do real work (don't compete with the one supporter/turn) ---
        if cid == CRUSHING_HAMMER:        # energy denial: strip the opponent's attacker off attack-range
            return 1500.0 if _opp_active_has_energy(state, me_i) else -1.0
        if cid == HERO_CAPE:              # +100 HP tool: bolt it onto a Mega so it tanks an extra hit
            try:
                megas_no_tool = [p for p in ([active] + _my_bench(state, me_i))
                                 if _id(p) in MEGAS and not _has_tool(p)]
            except Exception:
                megas_no_tool = []
            return 1400.0 if megas_no_tool else -1.0

        # ---- pre-attack supporters that do real work outrank the draw engine (one supporter/turn) ---
        if cid == BOSS_ORDERS:            # gust + KO a benched target for the prize race
            if sup_done:
                return -1.0
            return 1950.0 if _good_gust_target(obs, state, me_i) is not None else -1.0

        # ---- draw / search engine (dig before committing) -----------------------------------------
        if cid == SALVATORE:              # search-evolve a Staryu in play straight to Mega Starmie
            if sup_done:
                return -1.0
            if _basic_in_play_evolvable(state, me_i) and _mega_available_in_deck(state, me_i):
                return 1850.0
            return -1.0
        if cid == HILDA:                  # tutor an Evolution + an Energy to hand
            if sup_done:
                return -1.0
            return 1820.0 if _mega_available_in_deck(state, me_i) else 60.0
        if cid == LILLIE_DET:             # shuffle hand, draw 6/8: refuel a thin hand
            if sup_done:
                return -1.0
            hand_n = len(state.players[me_i].hand or [])
            if hand_n <= 4:
                return 1800.0
            if hand_n <= 6:
                return 1500.0
            return -1.0                   # loaded hand -> shuffling it away is a loss
        if cid == HARLEQUIN:              # risky draw (opp also draws): emergency refuel only
            if sup_done:
                return -1.0
            hand_n = len(state.players[me_i].hand or [])
            return 1480.0 if hand_n <= 2 else -1.0
        if cid == MEGA_SIGNAL:            # item: tutor Mega Starmie to hand
            if not _mega_available_in_deck(state, me_i):
                return -1.0
            return 1750.0 if not _have_mega_to_play(state, me_i) else 350.0
        if cid == BUDDY_POFFIN:           # item: fetch Staryu (the only <=70HP basic) onto the bench
            if not _basic_available_in_deck(state, me_i):
                return -1.0
            if bench_n <= 1:
                return 1780.0
            if bench_n <= 3:
                return 1650.0
            return 250.0
        if cid == ULTRA_BALL:             # item: discard 2, search ANY Pokémon — grab a missing piece
            hand_n = len(state.players[me_i].hand or [])
            want = (not _have_mega_to_play(state, me_i)) or (active is None) or bench_n == 0
            if want and hand_n >= 4:
                return 1620.0
            return 150.0                  # don't bleed 2 cards when the board is already set
        if cid == POKEGEAR:               # item: dig for a Supporter
            return 1600.0 if not sup_done else 300.0
        if cid == NIGHT_STRETCHER:        # item: recover a key piece from discard
            try:
                if any(_id(c) in (MEGAS | BASICS | {CINDERACE}) for c in (state.players[me_i].discard or [])):
                    return 1550.0
            except Exception:
                pass
            return 250.0

        # ---- the generic-scorer misplay we override: Wally strips its own attacker's energy ---------
        if cid == WALLY_COMP:             # heal a Mega BUT return its Energy -> usually a tempo trap
            if sup_done:
                return -1.0
            # vs Lucario: the heal-loop wall. Aura Jab does only 130/turn and Mega Brave (270) self-
            # locks, so a full-HP Mega Starmie (330) never dies in one turn. Wally fully heals our
            # damaged active and one re-attached {W} re-arms Jetting Blow (120 + 50 snipe): the 330
            # Starmie loops while still racing, so the bot banks no prizes off our 3-prize Mega.
            if _VS_LUC and _wally_reset(state, me_i, _LUC_WALLY_DMG):
                return 1830.0
            if not _wally_worth_it(state, me_i):
                return -1.0
            return 1100.0

        # Bare Pokémon from hand (Staryu): board presence.
        cd = _meta(cid)
        if cd is not None and cd.cardType == CardType.POKEMON and getattr(cd, "basic", False):
            return 1700.0 if bench_n == 0 else 1300.0
        return 600.0

    if t == OptionType.EVOLVE:
        # every evolution here is Staryu -> Mega Starmie ex; evolve after digging, before attaching.
        return 1300.0

    if t == OptionType.ATTACH:
        active = _my_active(state, me_i)
        if o.inPlayArea == AreaType.ACTIVE:
            if _id(active) in MEGAS:
                # vs Crustle: rush Mega Starmie to {C}{C}{C} so Nebula Beam (the only ex attack that
                # pierces the ex-damage-prevention wall) comes online a turn earlier.
                if _VS_CRU and _energy_count(active) < 3:
                    return 1320.0
                return 1250.0 if _energy_count(active) < 3 else 1000.0
            if _id(active) in BASICS:
                if _VS_CRU and _energy_count(active) < 3:
                    return 1230.0
                return 1200.0  # fuel the soon-to-be Mega (energy carries through evolution)
            return 1050.0      # Cinderace etc. — keep its single energy for Turbo Flare
        if o.inPlayArea == AreaType.BENCH:
            tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            if _id(tgt) in MEGAS:
                if _VS_CRU and _energy_count(tgt) < 3:
                    return 1180.0
                return 1100.0 if _energy_count(tgt) < 3 else 1000.0
            if _id(tgt) in BASICS:
                if _VS_CRU and _energy_count(tgt) < 3:
                    return 1080.0
                return 1050.0
            return 1000.0
        return 1000.0

    if t == OptionType.ABILITY:
        return 400.0

    if t == OptionType.ATTACK:
        # Attacking ENDS the turn -> develop first, attack LAST. EXCEPT a game-winning swing (KOs their
        # last prize), which is taken immediately. Turbo Flare doubles as our energy engine, so it
        # carries a ramp bonus when a benched attacker still needs fuel.
        active = _my_active(state, me_i)
        oa = _opp_active(state, me_i)
        score = 100.0
        dmg = _eff_damage(active, o.attackId, oa, state.players[1 - me_i])
        score += min(max(dmg, 0), 300) * 0.2
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 160.0  # KO
            try:
                opp = state.players[1 - me_i]
                if len(opp.prize or []) <= _prize_count_for(oa):
                    return 50000.0  # game-winning: take their last prize(s) now
            except Exception:
                pass
        if o.attackId == JETTING_BLOW:
            score += 12.0  # the 50 bench snipe is real extra value (tiebreak)
        if o.attackId == TURBO_FLARE:
            # the energy engine: +ramp value when a benched Mega/Staryu still needs fuel for Nebula/
            # Jetting. Non-ex damage, so it also chips through the Crustle wall (extra vs _VS_CRU).
            ramp_targets = [b for b in _my_bench(state, me_i)
                            if _id(b) in (MEGAS | BASICS) and _energy_count(b) < 3]
            if ramp_targets:
                score += 40.0
            if _VS_CRU:
                score += 80.0  # one of only two attacks that isn't negated by the wall
        if o.attackId == NEBULA_BEAM and oa is not None:
            cd = _meta(_id(oa))
            if cd is not None and (getattr(cd, "ex", False) or getattr(cd, "megaEx", False)):
                score += 20.0  # effect-ignoring: robust vs damage-prevention walls / big ex
        if _VS_CRU:
            # Crustle negates all ex/Mega-ex damage; only Nebula Beam (effect-ignoring) and Cinderace's
            # Turbo Flare (non-ex) actually land. Rank Nebula well above the negated Jetting Blow.
            if o.attackId == NEBULA_BEAM:
                score += 300.0
            elif o.attackId == JETTING_BLOW:
                score -= 60.0  # negated vs the wall (kept >= END so the bench snipe still fires)
        return score

    if t == OptionType.RETREAT:
        # Promote a benched Mega when stuck with a bare Staryu / a tapped-out Cinderace active.
        active = _my_active(state, me_i)
        if _id(active) in (BASICS | {CINDERACE}) and any(_id(b) in MEGAS for b in _my_bench(state, me_i)):
            return 120.0
        return -1.0

    if t == OptionType.END:
        return 0.0
    if t == OptionType.YES:
        return 5.0
    if t == OptionType.NO:
        return 3.0
    return 1.0


def _best_attack_damage(state, me_i):
    """Max effective damage our Active can deal to the opponent's Active this turn (rough; gates only
    Boss decisions)."""
    active = _my_active(state, me_i)
    oa = _opp_active(state, me_i)
    if active is None:
        return 0, None
    cd = _meta(_id(active))
    best = 0
    if cd is not None:
        for aid in (getattr(cd, "attacks", None) or []):
            best = max(best, _eff_damage(active, aid, oa, state.players[1 - me_i]))
    return best, oa


def _good_gust_target(obs, state, me_i):
    """A benched opponent Pokémon worth gusting (one we can KO this turn for a prize, or the only KO
    available when their Active is out of reach), else None."""
    best_dmg, oa = _best_attack_damage(state, me_i)
    if best_dmg <= 0:
        return None
    active_koable = oa is not None and best_dmg >= (oa.hp or 0)
    target = None
    target_val = 0.0
    for b in _opp_bench(state, me_i):
        if best_dmg >= (b.hp or 0):
            val = _opponent_value(b) + _prize_count_for(b) * 100.0
            if (not active_koable) or val > _opponent_value(oa) + _prize_count_for(oa) * 100.0 + 60.0:
                if val > target_val:
                    target, target_val = b, val
    return target


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
    if hp > maxhp * 0.4:
        return False
    try:
        hand = state.players[me_i].hand or []
        return any(_id(c) in ATTACK_ENERGY for c in hand)
    except Exception:
        return False


def _wally_reset(state, me_i, threshold) -> bool:
    """Our active is a Mega that has soaked >= `threshold` damage and we can re-power its 1-energy {W}
    attack from hand -> Wally fully heals it and re-attached {W} re-arms Jetting Blow. Used vs decks
    that can't OHKO a full-HP Mega (Lucario), so the healed Mega never dies in the gap."""
    if threshold <= 0:
        return False
    active = _my_active(state, me_i)
    if _id(active) not in MEGAS:
        return False
    hp = active.hp or 0
    maxhp = getattr(active, "maxHp", 0) or 0
    if maxhp <= 0 or (maxhp - hp) < threshold:
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

        # Damage / Crushing-Hammer / boss / gust targeting: opponent's most valuable, prefer active.
        # For Crushing Hammer's energy-discard target we want the opponent's ACTIVE attacker (knock it
        # off attack-range), which this same "prefer opponent active" rule selects.
        if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
                       SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET):
            if isinstance(card, Pokemon) and pidx != me_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 250.0
            elif isinstance(card, Pokemon):
                score -= _opponent_value(card)
            elif pidx != me_i:
                # Energy-card target on the opponent (Crushing Hammer): any opposing energy is good;
                # a Special Energy (e.g. their Ignition) is the juiciest strip.
                cd = _meta(cid)
                score += 60.0
                if cd is not None and cd.cardType == CardType.SPECIAL_ENERGY:
                    score += 40.0
            return score

        # Discarding / pitching (incl. Ultra Ball's 2-card cost): dump spare Water energy first;
        # protect the Mega/Cinderace line + the tutors.
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

        # Search/tutor + placement targets.
        if isinstance(card, Pokemon):
            if pidx != me_i:
                score += _opponent_value(card)
                if o.area == AreaType.ACTIVE:
                    score += 200.0
                return score
            # Our own mon (setup, evolve, fetch, switch-in).
            if cid == CINDERACE:
                # the setup engine + wall-breaker: best fronting the board (its ability puts it active),
                # so it shields our 3-prize Mega from being the early KO target while it ramps.
                score += 300.0
                if o.area == AreaType.ACTIVE or context in (
                        SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.TO_ACTIVE):
                    score += 120.0
            elif cid in MEGAS:
                score += 320.0     # the Mega attacker is the best fetch/placement
            elif cid in BASICS:
                score += 180.0
                if len(_my_bench(state, me_i)) == 0:
                    score += 220.0  # empty bench -> a body is urgent
            # vs Crustle: only Mega Starmie's Nebula Beam pierces the ex-damage wall, so make sure the
            # Starmie line is fetched/placed/evolved (Cinderace already chips it with Turbo Flare).
            if _VS_CRU and cid in (MEGAS | BASICS):
                score += 120.0
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
                # Ignition Energy provides {C}{C}{C} on an Evolution in one attach -> it brings Mega
                # Starmie's Nebula Beam online a full turn early (decisive vs the Crustle wall).
                if cid == IGNITION_ENERGY:
                    score += 80.0 + (150.0 if _VS_CRU else 0.0)
            elif cid in (SALVATORE, MEGA_SIGNAL, HILDA):
                score += 90.0 if not _have_mega_to_play(state, me_i) else 30.0
            elif cid == BOSS_ORDERS:
                score += 80.0 if _opp_bench(state, me_i) else 10.0
        return score

    return score

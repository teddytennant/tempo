"""Great Tusk fighting-box MILL specialist scoring (id-gated), consulted by agent/scorer.best_options.

The deck (data/decks/mined/alancai_tusk.csv) is teammate alancai27's stable-894 list (submission
54290398, 54% over 495 ladder episodes), mined card-for-card from his replays. Every rule below is
calibrated on ~205 of his real ladder games (~7,000 MAIN decisions, wins AND losses). Despite the
"fighting box" look, the deck is a DECK-OUT MILL engine:

  • WIN CONDITION (measured): 99/105 of his wins end with the opponent's deck at <=2 cards — and in
    76 of them he was BEHIND on prizes (median prizes taken in wins: HIM 0, opponent 2). He gives
    prizes away freely and wins when the opponent starts a turn with an empty deck.
  • Great Tusk (58, basic F, 140HP, non-ex). Land Collapse {C}{C}: 0 damage, discard the top card
    of the opponent's deck — and 3 MORE if an ANCIENT Supporter was played this turn. Explorer's
    Guidance (1185) and Colress's Tenacity (1194) are the deck's Ancient supporters (engine-
    verified from replays: opp deck drop mode is 2/turn plain, 5/turn with the combo). Land
    Collapse is 92% of all his attacks; Giant Tusk (160, {F}{F}{C}{C}) was used 10 times in 205
    games (finishing big megas / free KOs).
  • Crustle (345, stage-1, 150HP, non-ex). Mysterious Rock Inn: prevents ALL damage from opponent
    Pokémon-ex attacks. Fronted 57% of turns when the opponent's active is an ex, 29% when not.
    It cannot attack in this list (Superb Scissors needs {G}; the deck runs only Rock/Mist), so
    Crustle turns are wall+pass turns — the opponent burns their deck into it.
  • Neutralization Zone (1247, ACE stadium): prevents all damage to non-Rule-Box Pokémon (the
    whole board — every mon in the list is single-prize) from opponent ex/V attacks. Ex-attacker
    decks literally cannot take a prize while it is up (until they overwrite the stadium).
  • Disruption: 4x Xerosic's Machinations (opp discards to 3 — removes their resources AND caps
    Alakazam's Powerful Hand at 60), 4x Boss's Orders + 2x Lisia's Appeal used to STRAND an
    energyless support mon in the opponent's active (median gust target: 80HP, 0 energy) while
    the mill clock runs, 4x Switch for own repositioning (he retreated twice in 205 games).

Teacher weaknesses IMPROVED here (his losses: opponent keeps a prize lead and never decks out):
  1. He paired an Ancient supporter with Land Collapse in only 22% of mills. We sequence
     Colress/Explorer's ahead of other supporters on every Tusk mill turn -> 4-card mills.
  2. vs Alakazam "Powerful Hand" (his 62%, but his #1 loss source in volume) we fire Xerosic on
     a lower threshold: their HAND SIZE is their damage output.
  3. Mirror/wall deck-out races (3 of his 5 mirror losses were self-deck-outs): a stall-conserve
     governor stops optional self-draws when walling with a thin deck margin.
  4. Bench discipline vs counter-placers (Dragapult 27%, Munkidori): damage counters ignore both
     walls, so spare 70HP Dwebbles are free prizes — bench cap 2 in those matchups.

`is_tusk_deck(state, me_i)` fires on list-unique cards (Great Tusk 58 / Terrakion 607 / Lisia 1204
are globally unique; Dwebble/Crustle 344/345 PLUS any tusk-only trainer is unique vs the crustle
wall list) and LATCHES per seat. It must be consulted BEFORE crustle_rules (this list contains
344/345 = the crustle signature) and before cinderace_rules (this list plays Ultra Ball 1121 =
part of the cinderace signature).
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_attack, all_card_data

# ── deck card IDs (verified against the mined list + engine card data) ─────────────────────────
GREAT_TUSK = 58       # basic F, 140HP, non-ex; Land Collapse (mill) / Giant Tusk 160
DWEBBLE = 344         # basic G, 70HP; Ascension (evolve from deck)
CRUSTLE = 345         # stage1 G, 150HP; Mysterious Rock Inn (ex-attack-proof wall)
TERRAKION = 607       # basic F, 140HP; Retaliate 50(+80) / Land Crush 100 — the 1-of spare body

MIST_ENERGY = 11      # {C}; prevents attack EFFECTS on its holder
ROCK_ENERGY = 20      # {F}; prevents attack EFFECTS on its {F} holder (Tusk/Terrakion only)

BUDDY_POFFIN = 1086   # item: up to 2 Basic <=70HP to bench (Dwebble is the only legal target)
ULTRA_BALL = 1121     # item: discard 2, search any Pokémon
POKEGEAR = 1122       # item: look at top 7, reveal a Supporter to hand
SWITCH = 1123         # item: swap active with a benched mon (the deck's ONLY mobility)
FIGHTING_GONG = 1142  # item: search a Basic {F} Energy or Basic {F} Pokémon to hand
JUMBO_ICE_CREAM = 1147  # item: heal 80 from the active if it has 3+ energy
POKE_PAD = 1152       # item: search a non-Rule-Box Pokémon to hand
BOSS_ORDERS = 1182    # supporter: gust a benched opponent mon active (STRAND tool here)
EXPLORERS = 1185      # supporter (ANCIENT): look 6, take 2, discard 4 — the mill trigger
COLRESS = 1194        # supporter (ANCIENT): search Stadium + Energy to hand — the FREE mill trigger
XEROSIC = 1197        # supporter: opponent discards down to 3
LISIA = 1204          # supporter: gust a benched opponent BASIC active + confuse it
NEUTRAL_ZONE = 1247   # ACE stadium: non-Rule-Box mons take 0 from opponent ex/V attacks

ANCIENTS = {EXPLORERS, COLRESS}   # played same-turn => Land Collapse mills 4 instead of 1

# Attack IDs (verified via all_attack).
LAND_COLLAPSE = 62    # Tusk {C}{C}: mill 1 (+3 with an Ancient supporter this turn). 92% of attacks.
GIANT_TUSK = 63       # Tusk {F}{F}{C}{C}: 160
ASCENSION = 478       # Dwebble {C}: evolve into Crustle from the DECK
RETALIATE = 873       # Terrakion {F}{C}: 50 (+80 if our mon was KO'd last turn)
LAND_CRUSH_T = 874    # Terrakion {F}{F}{C}: 100

# Gate: 58/607/1204 are globally unique across every specialist/candidate deck; the combo arm
# (crustle-line 344/345 on OUR side + any tusk-only trainer) separates us from the crustle wall.
_SIGNATURE = {GREAT_TUSK, TERRAKION, LISIA}
_CRUSTLE_LINE = {DWEBBLE, CRUSTLE}
_TUSK_ONLY_TRAINERS = {ROCK_ENERGY, ULTRA_BALL, POKEGEAR, SWITCH, FIGHTING_GONG, POKE_PAD,
                       BOSS_ORDERS, EXPLORERS, COLRESS, XEROSIC, NEUTRAL_ZONE}

# Full 60-card decklist (the mined modal list, byte-identical across all 205 seat-games).
TUSK_DECK = (
    [GREAT_TUSK] * 4 + [DWEBBLE] * 4 + [CRUSTLE] * 4 + [TERRAKION]
    + [MIST_ENERGY] * 4 + [ROCK_ENERGY] * 4
    + [BUDDY_POFFIN] * 4 + [ULTRA_BALL] + [POKEGEAR] * 4 + [SWITCH] * 4 + [FIGHTING_GONG] * 4
    + [JUMBO_ICE_CREAM] + [POKE_PAD] * 4 + [BOSS_ORDERS] * 4 + [EXPLORERS] * 4 + [COLRESS] * 2
    + [XEROSIC] * 4 + [LISIA] * 2 + [NEUTRAL_ZONE]
)
assert len(TUSK_DECK) == 60, len(TUSK_DECK)

KEY_PIECES = {GREAT_TUSK, CRUSTLE, DWEBBLE, NEUTRAL_ZONE, MIST_ENERGY, ROCK_ENERGY,
              COLRESS, BOSS_ORDERS}

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

# Deck-out governors: the mirror is decided by draw parity, and 3 of his 5 mirror losses were
# self-deck-outs. He digs to deckCount 1; we keep a small floor plus a stall-conserve mode.
_SEARCH_FLOOR = 3      # no optional searches below this deckCount
_EXPLORERS_FLOOR = 10  # Explorer's costs SIX deck cards — needs real margin

# ── engine tables (loaded once) ────────────────────────────────────────────────────────────────
try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}
try:
    _ATK = {a.attackId: a for a in all_attack()}
except Exception:
    _ATK = {}

# Attacks carrying this phrase pierce Mysterious Rock Inn / Neutralization Zone.
_PIERCE = "any effects on your opponent"
POWERFUL_HAND = 1072   # Alakazam: 20 x their hand size, counter placement — ignores both walls


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


def _damage_on(p) -> int:
    try:
        return max(0, (getattr(p, "maxHp", 0) or 0) - (getattr(p, "hp", 0) or 0))
    except Exception:
        return 0


# ── deck detection (latched per seat, grimmsnarl pattern) ──────────────────────────────────────
_LATCH = {}        # me_i -> True once the signature has been seen on our side this game
_LATCH_PRIZE = {}  # me_i -> last seen own prize count (increase => new game => re-detect)


def _our_visible_ids(me):
    ids = []
    try:
        for c in (list(me.hand or []) + list(me.discard or [])):
            ids.append(_id(c))
        for p in (list(me.active or []) + list(me.bench or [])):
            if p is None:
                continue
            ids.append(_id(p))
            for c in (getattr(p, "preEvolution", None) or []):
                ids.append(_id(c))
            for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
                ids.append(_id(c))
    except Exception:
        pass
    return ids


def is_tusk_deck(state, me_i: int) -> bool:
    """True iff our side pilots the Great Tusk mill list. Latches for the rest of the game so a
    frame where the hand hides the unique cards cannot fall through to the crustle/cinderace
    specialists (this list contains their signature cards 344/345 and Ultra Ball 1121).

    TUSK_DISABLE=1 (eval-only) turns the gate off to reproduce the pre-specialist routing
    (the crustle specialist picks the deck up via 344/345) for baseline comparisons."""
    import os
    if os.environ.get("TUSK_DISABLE"):
        return False
    try:
        me = state.players[me_i]
        pc = len(me.prize or [])
        if _LATCH.get(me_i) and _LATCH_PRIZE.get(me_i) is not None and pc > _LATCH_PRIZE[me_i]:
            _LATCH[me_i] = False   # prizes grew back: a new game started
        _LATCH_PRIZE[me_i] = pc
        if _LATCH.get(me_i):
            return True
        ids = set(_our_visible_ids(me))
        try:
            for c in (state.stadium or []):
                if c is not None and getattr(c, "playerIndex", None) == me_i:
                    ids.add(_id(c))
        except Exception:
            pass
        hit = bool(ids & _SIGNATURE) or (
            bool(ids & _CRUSTLE_LINE) and bool(ids & _TUSK_ONLY_TRAINERS))
        if hit:
            _LATCH[me_i] = True
            return True
    except Exception:
        return False
    return False


# ── safe state getters ─────────────────────────────────────────────────────────────────────────
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


def _opp_deck_count(state, me_i) -> int:
    return _deck_count(state, 1 - me_i)


def _opp_hand_count(state, me_i) -> int:
    try:
        return int(state.players[1 - me_i].handCount or 0)
    except Exception:
        return 0


def _turn(state) -> int:
    try:
        return int(getattr(state, "turn", 0) or 0)
    except Exception:
        return 99


def _count_in_play(state, me_i, cid) -> int:
    return sum(1 for p in _my_mons(state, me_i) if _id(p) == cid)


def _is_ex(cid) -> bool:
    cd = _meta(cid)
    return cd is not None and bool(getattr(cd, "ex", False) or getattr(cd, "megaEx", False))


def _zone_up(state) -> bool:
    try:
        return any(c is not None and _id(c) == NEUTRAL_ZONE for c in (state.stadium or []))
    except Exception:
        return False


def _opp_stadium_up(state, me_i) -> bool:
    try:
        return any(c is not None and getattr(c, "playerIndex", None) == 1 - me_i
                   for c in (state.stadium or []))
    except Exception:
        return False


def _our_stadium_up(state, me_i) -> bool:
    try:
        return any(c is not None and getattr(c, "playerIndex", None) == me_i
                   for c in (state.stadium or []))
    except Exception:
        return False


# ── matchup latches (per-frame bookkeeping via note_obs) ───────────────────────────────────────
_VS_ALAKAZAM = {}   # me_i -> opponent runs the Powerful Hand engine (hand size = damage)
_VS_COUNTER = {}    # me_i -> opponent places damage counters that ignore both walls
_VS_WALL = {}       # me_i -> opponent is the Grass Crustle wall (deck-parity mill race)
_NOTE_PRIZE = {}
_ALAKAZAM_LINE = {741, 742, 743}          # Abra / Kadabra / Alakazam
_COUNTER_PLACERS = {741, 742, 743, 119, 120, 121, 112}  # + Dreepy/Drakloak/Dragapult, Munkidori
_WALL_LINE = {344, 345}


def note_obs(obs, obs_dict, me_i) -> None:
    """Per-frame bookkeeping: matchup latches (new game resets on prize growth). Never raises."""
    try:
        state = obs.current
        pc = len(state.players[me_i].prize or [])
        if _NOTE_PRIZE.get(me_i) is not None and pc > _NOTE_PRIZE[me_i]:
            _VS_ALAKAZAM[me_i] = False
            _VS_COUNTER[me_i] = False
            _VS_WALL[me_i] = False
        _NOTE_PRIZE[me_i] = pc
        if _VS_ALAKAZAM.get(me_i) and _VS_COUNTER.get(me_i) and _VS_WALL.get(me_i):
            return
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
        s = set(seen)
        if s & _ALAKAZAM_LINE:
            _VS_ALAKAZAM[me_i] = True
        if s & _COUNTER_PLACERS:
            _VS_COUNTER[me_i] = True
        if s & _WALL_LINE:
            _VS_WALL[me_i] = True
    except Exception:
        pass


def _opp_f_weak(state, me_i) -> bool:
    """The opponent's ACTIVE is Fighting-weak (Lightning archetypes etc.): our box stops stalling
    and RACES — Terrakion's Retaliate hits 100-260 and Giant Tusk 320 with the doubling, one-
    shotting their whole board. The mill plan alone loses to fast non-ex aggro (walls blank
    nothing), so weakness beatdown is the deck's real answer."""
    try:
        oa = _opp_active(state, me_i)
        cd = _meta(_id(oa)) if oa is not None else None
        return cd is not None and getattr(cd, "weakness", None) == 6
    except Exception:
        return False


# ── threat model (wall-aware) ──────────────────────────────────────────────────────────────────
def _threat_to(state, me_i, target) -> int:
    """Best payable damage the opponent's active can put on `target` next turn (their energy +1),
    weakness-aware, zeroed by Mysterious Rock Inn (target Crustle vs non-piercing ex) and by
    Neutralization Zone while it is up. Powerful Hand's hand-size damage is modeled explicitly."""
    oa = _opp_active(state, me_i)
    if oa is None or target is None:
        return 0
    ocd = _meta(_id(oa))
    tcd = _meta(_id(target))
    if ocd is None:
        return 0
    is_ex = bool(getattr(ocd, "ex", False) or getattr(ocd, "megaEx", False))
    have = _energy_count(oa) + 1
    zone = _zone_up(state)
    best = 0
    for aid in (getattr(ocd, "attacks", None) or []):
        atk = _ATK.get(aid)
        if atk is None or len(getattr(atk, "energies", None) or []) > have:
            continue
        text = atk.text or ""
        if aid == POWERFUL_HAND:
            best = max(best, 20 * _opp_hand_count(state, me_i))   # ignores both walls
            continue
        d = atk.damage or 0
        if d <= 0:
            continue
        pierce = _PIERCE in text
        if is_ex and not pierce and (_id(target) == CRUSTLE or zone):
            continue   # blanked by Rock Inn / Neutralization Zone
        if tcd is not None and not pierce:
            try:
                if tcd.weakness is not None and tcd.weakness == ocd.energyType:
                    d *= 2
                elif tcd.resistance is not None and tcd.resistance == ocd.energyType:
                    d = max(0, d - 30)
            except Exception:
                pass
        best = max(best, d)
    return best


def _wall_immune(state, me_i) -> bool:
    """Their active attacker cannot damage our active at all (the true stall state)."""
    a = _my_active(state, me_i)
    return a is not None and _opp_active(state, me_i) is not None and _threat_to(state, me_i, a) == 0


def _stall_conserve(state, me_i) -> bool:
    """Deck-parity governor: while walling, whoever burns their deck first loses. When we cannot
    out-deck the opponent by a safe margin, every optional draw/search is a step toward our own
    deck-out (3 of his 5 mirror losses were exactly this)."""
    try:
        if not _wall_immune(state, me_i):
            return False
        return _deck_count(state, me_i) <= _opp_deck_count(state, me_i) + 4
    except Exception:
        return False


def _lc_ready(state, me_i) -> bool:
    """Our active is a Great Tusk that can pay Land Collapse ({C}{C}) — a mill turn."""
    a = _my_active(state, me_i)
    return a is not None and _id(a) == GREAT_TUSK and _energy_count(a) >= 2


def _tusk_damage(state, me_i, attack_id, target) -> int:
    """Weakness-aware damage of our active's attack vs `target`."""
    a = _my_active(state, me_i)
    atk = _ATK.get(attack_id)
    if a is None or atk is None or target is None:
        return 0
    d = atk.damage or 0
    if d <= 0:
        return 0
    acd, tcd = _meta(_id(a)), _meta(_id(target))
    if acd is not None and tcd is not None:
        try:
            if tcd.weakness is not None and tcd.weakness == acd.energyType:
                d *= 2
            elif tcd.resistance is not None and tcd.resistance == acd.energyType:
                d = max(0, d - 30)
        except Exception:
            pass
    return d


def _can_attack_at_all(p) -> bool:
    """Whether `p` has any attack payable with its current energy (colorless-cost counting)."""
    cd = _meta(_id(p))
    if cd is None:
        return False
    have = _energy_count(p)
    for aid in (getattr(cd, "attacks", None) or []):
        atk = _ATK.get(aid)
        if atk is not None and len(getattr(atk, "energies", None) or []) <= have:
            return True
    return False


def _strand_value(state, me_i, p) -> float:
    """How good `p` (an opponent BENCHED mon) is to gust into their active and STRAND: energyless,
    attack-incapable, expensive to retreat — every stranded turn is a free mill/wall turn. His
    measured targets: median 80HP, 71% zero energy."""
    v = 0.0
    en = _energy_count(p)
    if en == 0:
        v += 400.0
    elif en == 1:
        v += 120.0
    else:
        v -= 150.0 * (en - 1)
    if not _can_attack_at_all(p):
        v += 250.0
    cd = _meta(_id(p))
    if cd is not None:
        v += 40.0 * (getattr(cd, "retreatCost", 0) or 0)
        if getattr(cd, "basic", False) and (getattr(cd, "hp", 0) or 0) <= 80:
            v += 80.0   # fresh support basic — his favourite pull
    return v


def _best_strand_target(state, me_i, basic_only=False):
    best, bv = None, 120.0   # require a genuinely good strand, not any body
    for b in _opp_bench(state, me_i):
        if basic_only:
            cd = _meta(_id(b))
            if cd is None or not getattr(cd, "basic", False):
                continue
        v = _strand_value(state, me_i, b)
        if v > bv:
            best, bv = b, v
    return best


def _bench_cap(state, me_i) -> int:
    """Counter-placer matchups (Dragapult/Alakazam/Munkidori): spare 70HP bodies are free prizes
    for damage counters that ignore both walls — keep the bench lean. Otherwise bench freely
    (every extra single-prize body is another KO they must pay for)."""
    return 2 if _VS_COUNTER.get(me_i) else 4


def _energy_in_deck_possible(state, me_i) -> bool:
    """Conservative: could an energy still be in our deck? (8 total in list)."""
    seen = 0
    try:
        me = state.players[me_i]
        for c in (list(me.hand or []) + list(me.discard or [])):
            if _id(c) in (MIST_ENERGY, ROCK_ENERGY):
                seen += 1
        for p in _my_mons(state, me_i):
            for c in (getattr(p, "energyCards", None) or getattr(p, "energies", None) or []):
                if _id(c) in (MIST_ENERGY, ROCK_ENERGY):
                    seen += 1
    except Exception:
        pass
    return seen < 8


def _zone_in_deck_possible(state, me_i) -> bool:
    try:
        me = state.players[me_i]
        for c in (list(me.hand or []) + list(me.discard or [])):
            if _id(c) == NEUTRAL_ZONE:
                return False
        for c in (state.stadium or []):
            if c is not None and _id(c) == NEUTRAL_ZONE:
                return False
    except Exception:
        pass
    return True


# ── MAIN-turn scoring ──────────────────────────────────────────────────────────────────────────
# Measured ordering: Zone/stadium down early -> evolve Crustle ASAP -> Ancient supporter on mill
# turns (the 1->4 mill combo, HIS big miss) -> Boss/Lisia strand or Xerosic -> board items ->
# energy on Tusk -> Switch repositioning -> ATTACK (never skipped: 835:0) -> END.
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type

    if t == OptionType.EVOLVE:
        return 2600.0   # Dwebble -> Crustle the turn it is live (his ot2 mode); the wall is tempo

    if t == OptionType.ABILITY:
        # The deck has no activatable abilities (Rock Inn is passive). Anything surfacing here is
        # an opponent-stadium ability (his bot idly clicked Spikemuth 80 times — pure waste).
        return -1.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        bench_n = len(_my_bench(state, me_i))
        deck_n = _deck_count(state, me_i)
        sup_done = bool(getattr(state, "supporterPlayed", False))
        stad_done = bool(getattr(state, "stadiumPlayed", False))
        conserve = _stall_conserve(state, me_i)
        lc = _lc_ready(state, me_i)

        # ---- stadium ----------------------------------------------------------------------------
        if cid == NEUTRAL_ZONE:
            if stad_done or _our_stadium_up(state, me_i):
                return -1.0
            # He plays it on sight; overwriting their stadium is strictly better than a bare board.
            return 2500.0 if _opp_stadium_up(state, me_i) else 2400.0

        # ---- supporters (one per turn) ----------------------------------------------------------
        if cid == COLRESS:
            if sup_done:
                return -1.0
            fetch = (_zone_in_deck_possible(state, me_i) and not stad_done) or \
                _energy_in_deck_possible(state, me_i)
            if lc:
                # THE improvement: a free Ancient trigger (searches, discards nothing) turns this
                # turn's Land Collapse into a 4-mill. Outranks every other supporter.
                return 2470.0 if deck_n > _SEARCH_FLOOR else 2340.0
            if _VS_WALL.get(me_i):
                # The wall race is decided by mill rate: hold every Ancient for a mill turn
                # unless it must fetch the FIRST miller's energy right now.
                own_energy = (sum(_energy_count(p) for p in _my_mons(state, me_i))
                              + sum(1 for c in _hand(state, me_i)
                                    if _id(c) in (ROCK_ENERGY, MIST_ENERGY)))
                return 2200.0 if (own_energy < 2 and fetch and deck_n > _SEARCH_FLOOR) else -1.0
            return 2200.0 if (fetch and deck_n > _SEARCH_FLOOR and not conserve) else -1.0
        if cid == EXPLORERS:
            if sup_done or conserve or deck_n < _EXPLORERS_FLOOR:
                return -1.0   # it burns SIX deck cards — never in a deck-parity race
            if _VS_WALL.get(me_i) and not lc and deck_n < 35:
                return -1.0   # hold the Ancient for a mill turn (and spare the 6-card burn)
            if _VS_WALL.get(me_i) and deck_n < 20 and deck_n < _opp_deck_count(state, me_i) - 2:
                return -1.0   # clearly behind on raw deck parity late: stop the 6-card burns
            if lc:
                return 2460.0  # Ancient trigger + draw 2 on a mill turn
            return 2150.0
        if cid == XEROSIC:
            if sup_done:
                return -1.0
            oh = _opp_hand_count(state, me_i)
            if _VS_ALAKAZAM.get(me_i):
                # Powerful Hand does 20 x their hand size: Xerosic IS the damage cap. Highest
                # supporter priority in this matchup (his #1 loss volume) from hand >= 4.
                return 2480.0 if oh >= 4 else -1.0
            if oh >= 5:
                return 2320.0 if not lc else 2260.0   # on mill turns Ancients come first
            return -1.0
        if cid == BOSS_ORDERS:
            if sup_done:
                return -1.0
            tgt = _best_strand_target(state, me_i)
            if tgt is None:
                return -1.0
            return 2310.0 if not lc else 2250.0   # strand, but never over the Ancient mill combo
        if cid == LISIA:
            if sup_done:
                return -1.0
            tgt = _best_strand_target(state, me_i, basic_only=True)
            if tgt is None:
                return -1.0
            return 2280.0 if not lc else 2230.0   # + Confused: even harder to escape

        # ---- items ------------------------------------------------------------------------------
        if cid == BUDDY_POFFIN:
            if deck_n <= _SEARCH_FLOOR or conserve:
                return -1.0
            if bench_n == 0:
                return 2490.0   # never risk the no-Active loss
            if bench_n < _bench_cap(state, me_i):
                return 2060.0
            return -1.0
        if cid == FIGHTING_GONG:
            if deck_n <= _SEARCH_FLOOR or conserve:
                return -1.0
            tusks = _count_in_play(state, me_i, GREAT_TUSK) + \
                sum(1 for c in _hand(state, me_i) if _id(c) == GREAT_TUSK)
            if tusks < 2 or _energy_in_deck_possible(state, me_i):
                return 2040.0
            return -1.0
        if cid == POKE_PAD:
            if deck_n <= _SEARCH_FLOOR or conserve:
                return -1.0
            unevolved = any(_id(p) == DWEBBLE for p in _my_mons(state, me_i))
            crustle_in_hand = any(_id(c) == CRUSTLE for c in _hand(state, me_i))
            walls = _count_in_play(state, me_i, CRUSTLE) + _count_in_play(state, me_i, DWEBBLE)
            tusks = _count_in_play(state, me_i, GREAT_TUSK)
            if (unevolved and not crustle_in_hand) or walls == 0 or tusks < 2:
                return 2030.0
            return 1500.0 if deck_n >= 20 else -1.0
        if cid == POKEGEAR:
            if deck_n <= _SEARCH_FLOOR or conserve:
                return -1.0
            return 1900.0   # dig for the next supporter (Boss/Colress/Xerosic — mill triggers)
        if cid == SWITCH:
            # The deck's only mobility (he retreated TWICE in 205 games — Switch does the moving).
            active = _my_active(state, me_i)
            aid_ = _id(active)
            oa = _opp_active(state, me_i)
            oa_ex = oa is not None and _is_ex(_id(oa))
            threat = _threat_to(state, me_i, active) if active is not None else 0
            hp = (getattr(active, "hp", 0) or 0) if active is not None else 0
            # (a) wall-in: their active is an ex and a benched Crustle blanks it.
            if (oa_ex and aid_ != CRUSTLE
                    and any(_id(b) == CRUSTLE for b in _my_bench(state, me_i))
                    and threat >= hp > 0):
                return 2290.0
            # (b) mill-in / race-in: a fueled attacker sits benched while the active cannot
            #     attack (Crustle/empty Dwebble): front the miller (or the Terrakion sweeper
            #     when their board is Fighting-weak).
            if (active is not None and aid_ in (CRUSTLE, DWEBBLE, TERRAKION, GREAT_TUSK)
                    and not _can_attack_at_all(active)):
                f_weak = _opp_f_weak(state, me_i)
                for b in _my_bench(state, me_i):
                    fueled = (_id(b) == GREAT_TUSK and _energy_count(b) >= 2) or \
                        (f_weak and _id(b) == TERRAKION and _energy_count(b) >= 2)
                    if fueled:
                        if f_weak or _threat_to(state, me_i, b) < (getattr(b, "hp", 0) or 0):
                            return 2270.0
            # (c) rescue: the active dies next turn and a safer body waits (never bleed 1-prize
            #     bodies for free when a wall stands).
            if threat >= hp > 0 and any(
                    _threat_to(state, me_i, b) < (getattr(b, "hp", 0) or 0)
                    for b in _my_bench(state, me_i)):
                return 1950.0
            return -1.0
        if cid == ULTRA_BALL:
            if deck_n <= _SEARCH_FLOOR or conserve or len(_hand(state, me_i)) < 3:
                return -1.0
            tusks = _count_in_play(state, me_i, GREAT_TUSK)
            walls = _count_in_play(state, me_i, CRUSTLE) + _count_in_play(state, me_i, DWEBBLE)
            if tusks == 0 or walls == 0:
                return 1800.0   # emergency body search only — it pitches 2 cards
            return -1.0
        if cid == JUMBO_ICE_CREAM:
            active = _my_active(state, me_i)
            if active is None or _energy_count(active) < 3:
                return -1.0
            dmg = _damage_on(active)
            emergency = (getattr(active, "hp", 0) or 0) <= _threat_to(state, me_i, active)
            return 1850.0 if (dmg >= 80 or (dmg > 0 and emergency)) else -1.0

        # ---- Pokémon from hand ------------------------------------------------------------------
        cd = _meta(cid)
        if cd is not None and cd.cardType == CardType.POKEMON and getattr(cd, "basic", False):
            if bench_n == 0:
                return 2490.0
            if bench_n >= _bench_cap(state, me_i):
                return -1.0
            if cid == GREAT_TUSK:
                return 2020.0 if _count_in_play(state, me_i, GREAT_TUSK) < 2 else 1400.0
            if cid == DWEBBLE:
                walls = _count_in_play(state, me_i, CRUSTLE) + _count_in_play(state, me_i, DWEBBLE)
                return 2010.0 if walls < 2 else 1300.0
            if cid == TERRAKION:
                return 1200.0   # spare 140HP body; he benches it as late padding
            return 900.0
        if cid == CRUSTLE:
            return 500.0        # stage 1 surfacing under PLAY (engine quirk) — evolve path scores it
        return 500.0

    if t == OptionType.ATTACH:
        card = _get(obs, getattr(o, "area", None), getattr(o, "index", None), me_i)
        cid = _id(card)
        tgt = _get(obs, getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), me_i)
        tid = _id(tgt)
        ten = _energy_count(tgt)
        in_active = getattr(o, "inPlayArea", None) == AreaType.ACTIVE
        oa = _opp_active(state, me_i)
        f_weak = _opp_f_weak(state, me_i)
        # 8 energies total; every one is a future mill turn. Measured routing: Great Tusk 86%.
        if tid == GREAT_TUSK:
            if ten < 2:
                # Rock on the F-body first (its effect-prevention only works on {F} mons); keep
                # Mist flexible. Active Tusk (this turn's miller) over a benched one — but NEVER
                # fuel a body that dies to the next hit while a safer twin waits (8 energies are
                # the whole game; every one buried with a KO'd mon is a lost mill turn).
                bias = 20.0 if cid == ROCK_ENERGY else 0.0
                threat = _threat_to(state, me_i, tgt)
                hp = getattr(tgt, "hp", 0) or 0
                if (threat >= hp > 0 and ten == 0
                        and any(_id(m) == GREAT_TUSK and m is not tgt
                                for m in _my_mons(state, me_i))):
                    return 1710.0 + bias
                return 2210.0 + bias + (40.0 if in_active else 0.0)
            # Pump past 2 toward Giant Tusk: vs a big ex tank (his 3x Mega Starmie chip line),
            # for a weakness KO, or in full race mode vs a Fighting-weak board.
            if ten < 4:
                if oa is not None and _tusk_damage(state, me_i, GIANT_TUSK, oa) >= (getattr(oa, "hp", 0) or 0) > 0:
                    return 1750.0
                if f_weak:
                    return 1720.0
                if oa is not None and (_is_ex(_id(oa)) and (getattr(oa, "maxHp", 0) or 0) >= 250):
                    return 1700.0
            return 100.0
        if tid == TERRAKION and f_weak and ten < 3:
            # The anti-Lightning tech: Retaliate {F}{C} hits 100-260 with the doubling and the
            # +80 revenge rider — it one-shots every non-ex body in the Iono-style decks.
            return 2160.0 if ten < 2 else 1650.0
        if tid == DWEBBLE and ten < 1:
            # One energy = Ascension (evolve into Crustle from the DECK). His ot1 line.
            crustle_live = any(_id(c) == CRUSTLE for c in _hand(state, me_i))
            return 2150.0 if (not crustle_live and cid == MIST_ENERGY) else 1600.0
        if tid == CRUSTLE and in_active and ten < 3:
            return 450.0    # slow-park spares on the wall: enables the 80-heal, dodges opp Xerosic
        if tid == TERRAKION:
            return 30.0     # he attached to Terrakion ZERO times in 205 games (mill games)
        return 50.0

    if t == OptionType.ATTACK:
        aid = getattr(o, "attackId", None)
        oa = _opp_active(state, me_i)
        # He NEVER ends the turn with an attack available (835:0) — base clears END easily.
        if aid == LAND_COLLAPSE:
            return 900.0    # the win condition: 1-4 cards off their deck every single turn
        if aid == ASCENSION:
            # Dwebble active: free evolve from the deck. Skip only when no Crustle can be there.
            crustles_left = 4 - _count_in_play(state, me_i, CRUSTLE) \
                - sum(1 for c in _hand(state, me_i) if _id(c) == CRUSTLE)
            return 870.0 if crustles_left > 0 and _deck_count(state, me_i) > 0 else 200.0
        if aid == GIANT_TUSK:
            dmg = _tusk_damage(state, me_i, GIANT_TUSK, oa)
            if oa is not None and dmg >= (getattr(oa, "hp", 0) or 0) > 0:
                score = 1000.0   # a free KO is a free KO (weakness doubles vs F-weak actives)
                try:
                    opp = state.players[1 - me_i]
                    cd = _meta(_id(oa))
                    prizes = 3 if getattr(cd, "megaEx", False) else 2 if getattr(cd, "ex", False) else 1
                    if len(opp.prize or []) <= prizes:
                        return 50000.0
                except Exception:
                    pass
                return score
            if oa is not None and _is_ex(_id(oa)) and (getattr(oa, "maxHp", 0) or 0) >= 250:
                return 920.0    # chip the mega tank down (his measured anti-Mega line)
            return 300.0
        if aid in (RETALIATE, LAND_CRUSH_T):
            dmg = _tusk_damage(state, me_i, aid, oa)
            if oa is not None and dmg >= (getattr(oa, "hp", 0) or 0) > 0:
                return 950.0
            return 400.0
        return 350.0

    if t == OptionType.RETREAT:
        return -1.0   # he retreated twice in 205 games; Switch does the moving (energy is mill fuel)

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

    if t == OptionType.NUMBER:
        return score + (getattr(o, "number", 0) or 0)

    if t == OptionType.YES:
        if context == SelectContext.IS_FIRST:
            return score   # go SECOND: in a deck-out race the player who draws first loses parity
        return score + 100.0
    if t == OptionType.NO:
        if context == SelectContext.IS_FIRST:
            return score + 100.0
        return score
    if t == OptionType.SPECIAL_CONDITION:
        return 2000.0

    if t in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD, OptionType.ENERGY):
        pidx = getattr(o, "playerIndex", me_i)
        card = _get(obs, o.area, o.index, pidx)
        cid = _id(card)

        if context in HEAL_CTX:
            if isinstance(card, Pokemon):
                score += _damage_on(card)
                if o.area == AreaType.ACTIVE and pidx == me_i:
                    score += 100.0
            return score

        if context in DMG_CTX:
            if isinstance(card, Pokemon) and pidx == opp_i:
                hp = getattr(card, "hp", 0) or 0
                score += 100.0
                if 0 < hp <= 30:
                    score += 300.0
                if o.area == AreaType.ACTIVE:
                    score += 150.0
            elif isinstance(card, Pokemon):
                score -= 500.0   # never damage our own
            return score

        # Discards (Ultra Ball cost / opponent Xerosic). Measured pitch order: spare Switch >
        # Jumbo > Pokégear > Lisia > Terrakion(!) > dup supporters. Protect the 8 energies, the
        # mill/wall bodies, Zone and the Ancient triggers.
        if context in GIVE_UP_CTX:
            pitch = {SWITCH: 90.0, JUMBO_ICE_CREAM: 80.0, POKEGEAR: 60.0, LISIA: 55.0,
                     TERRAKION: 50.0, XEROSIC: 40.0, EXPLORERS: 30.0, ULTRA_BALL: 25.0}
            if cid in pitch:
                return score + pitch[cid]
            protect = {MIST_ENERGY: -300.0, ROCK_ENERGY: -300.0, NEUTRAL_ZONE: -400.0,
                       GREAT_TUSK: -280.0, CRUSTLE: -220.0, DWEBBLE: -160.0, COLRESS: -140.0,
                       BOSS_ORDERS: -100.0, BUDDY_POFFIN: -60.0, FIGHTING_GONG: -60.0,
                       POKE_PAD: -40.0}
            return score + protect.get(cid, 0.0)

        # Gust target (Boss's Orders / Lisia's Appeal -> their bench to active): STRAND the mon
        # that gives them the fewest options (energyless, attack-less, heavy retreat).
        if context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH) and pidx == opp_i:
            if isinstance(card, Pokemon):
                score += _strand_value(state, me_i, card)
            return score

        # Our own promotion / switch-in (after a KO, or our own Switch): wall vs miller by
        # matchup, survival-aware; feed Dwebble chaff when everything dies anyway.
        if (context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH) and pidx == me_i
                and isinstance(card, Pokemon)):
            oa = _opp_active(state, me_i)
            oa_ex = oa is not None and _is_ex(_id(oa))
            f_weak = _opp_f_weak(state, me_i)
            threat = _threat_to(state, me_i, card)
            hp = getattr(card, "hp", 0) or 0
            survives = hp > threat
            if cid == CRUSTLE:
                score += 520.0 if oa_ex else 210.0
                if survives:
                    score += 120.0
            elif cid == GREAT_TUSK:
                score += 300.0 + (150.0 if _energy_count(card) >= 2 else 0.0)
                if f_weak and _energy_count(card) >= 2:
                    score += 200.0   # race mode: the fighting attacker one-shots their board
                if not survives:
                    score -= 260.0   # don't feed the fueled miller
                if oa_ex and _energy_count(card) < 2:
                    score -= 100.0
            elif cid == DWEBBLE:
                score += 200.0       # the cheapest feed; Ascension makes it a wall next turn
                if survives:
                    score += 60.0
            elif cid == TERRAKION:
                score += 140.0 + (60.0 if survives else 0.0)
                if f_weak:
                    score += 300.0 + (150.0 if _energy_count(card) >= 2 else 0.0)
            return score

        # Setup seats (measured: active Dwebble 57% > Great Tusk 35% > Terrakion 8%; bench
        # Great Tusk > Terrakion ~ Dwebble).
        if context == SelectContext.SETUP_ACTIVE_POKEMON:
            score += {DWEBBLE: 260.0, GREAT_TUSK: 190.0, TERRAKION: 120.0}.get(cid, 0.0)
            return score
        if context == SelectContext.SETUP_BENCH_POKEMON:
            score += {GREAT_TUSK: 240.0, TERRAKION: 170.0, DWEBBLE: 150.0}.get(cid, 20.0)
            return score

        # Deck / looking picks (Poffin, Gong, Poké Pad, Colress, Pokégear, Explorer's, Ultra
        # Ball). Need-aware values calibrated on his picks: Great Tusk 402 > Rock 196 ~ Mist 192 >
        # Crustle 157 > Boss 126 > Zone 116 > Colress 111 > Dwebble 108.
        if o.area in (AreaType.DECK, AreaType.LOOKING) or context in (
                SelectContext.TO_HAND, SelectContext.TO_BENCH, SelectContext.LOOK):
            need = 0.0
            tusks = _count_in_play(state, me_i, GREAT_TUSK) + \
                sum(1 for c in _hand(state, me_i) if _id(c) == GREAT_TUSK)
            walls = _count_in_play(state, me_i, CRUSTLE) + _count_in_play(state, me_i, DWEBBLE)
            unevolved = any(_id(p) == DWEBBLE for p in _my_mons(state, me_i))
            if cid == GREAT_TUSK:
                need = 320.0 if tusks < 2 else 180.0
            elif cid == CRUSTLE:
                need = 300.0 if unevolved else 150.0
            elif cid == DWEBBLE:
                need = 260.0 if walls < 2 else 120.0
            elif cid in (ROCK_ENERGY, MIST_ENERGY):
                attached = sum(_energy_count(p) for p in _my_mons(state, me_i))
                in_hand = sum(1 for c in _hand(state, me_i)
                              if _id(c) in (ROCK_ENERGY, MIST_ENERGY))
                need = 290.0 if (attached + in_hand) < 4 else 170.0
                if cid == ROCK_ENERGY:
                    need += 10.0
            elif cid == NEUTRAL_ZONE:
                need = 280.0
            elif cid == BOSS_ORDERS:
                need = 230.0
            elif cid == COLRESS:
                need = 240.0   # the free Ancient trigger — he under-fetched it
            elif cid == XEROSIC:
                need = 260.0 if _VS_ALAKAZAM.get(me_i) else 150.0
            elif cid == EXPLORERS:
                need = 140.0
            elif cid == BUDDY_POFFIN:
                need = 130.0
            elif cid == POKE_PAD:
                need = 110.0
            elif cid == LISIA:
                need = 100.0
            elif cid == SWITCH:
                need = 90.0
            elif cid == FIGHTING_GONG:
                need = 85.0
            elif cid == POKEGEAR:
                need = 80.0
            elif cid == TERRAKION:
                need = 60.0
            else:
                need = 40.0
            if context in PLACEMENT_CTX:
                need += 400.0
            return score + need

        # Generic our-side placement / evolution targets.
        if isinstance(card, Pokemon) or (
                _meta(cid) is not None and _meta(cid).cardType == CardType.POKEMON):
            if pidx == opp_i:
                score += 100.0 + (getattr(card, "hp", 0) or 0) / 10.0
                if o.area == AreaType.ACTIVE:
                    score += 100.0
                return score
            if context in PLACEMENT_CTX:
                score += 400.0
            score += {CRUSTLE: 120.0, GREAT_TUSK: 100.0, DWEBBLE: 80.0}.get(cid, 20.0)
            return score
        return score

    if t == OptionType.ATTACH:
        # Energy-target sub-selection (engine paths that surface ATTACH outside MAIN).
        tgt = _get(obs, getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), me_i)
        tid = _id(tgt)
        ten = _energy_count(tgt)
        if tid == GREAT_TUSK and ten < 2:
            return 600.0
        if tid == DWEBBLE and ten < 1:
            return 500.0
        if tid == CRUSTLE and ten < 3:
            return 200.0
        return 50.0

    return score

"""Hop's Snorlax specialist scoring (id-gated), consulted by agent/scorer.best_options.

This is the #2 frontier team's deck — "The Debauchery Tea Party" (~1358 Elo), extracted card-for-card
from their deck-selection action in data/top2/episode-81091518-replay.json. It is a single-prize
"Hop's" toolbox aggro/control deck (Snorlax / Cramorant / Phantump→Trevenant) whose win condition is
chipping the opponent's Active down with CHEAP single-prize attackers stacked by three additive +30
buffs (Snorlax "Extra Helpings" while in play, the Postwick stadium, and the Hop's Choice Band tool).

Design note (important): the GENERIC deck-agnostic scorer (agent/scorer._score_main / _score_sub)
already pilots this toolbox WELL — empirically far better than a hand-rolled rule table. So unlike the
other specialists this one is THIN: it delegates board-building / energy-attachment / draw / search /
sub-selection to the proven generic scorer and overrides ONLY the two things the generic table gets
wrong for this archetype, both on the ATTACK option:

  1. Hop's Cramorant's "Fickle Spitting" does literally nothing unless the opponent has exactly 3 or 4
     prizes remaining. The generic scorer reads its printed 120 damage and happily whiffs the turn;
     this specialist hard-gates that attack to opp-prize ∈ {3, 4}.
  2. The generic scorer estimates attack damage from the raw printed number; this specialist folds in
     the Hop's +30 buff stack (Extra Helpings / Postwick / Choice Band) and weakness so it (a) picks
     the best Hop's attack and (b) recognises buffed KOs / game-winning swings.

Being an active specialist ALSO enables the multi-step lethal verifier (agent/lethal.py) for this deck
in scorer.best_options, which the bare generic path does not get.

`is_hops_snorlax_deck(state, me_i)` detects we pilot the Hop's line (a 304/311/878/879 is always
visible on our side — these ids are disjoint from every other specialist's signatures). For any other
deck none of this fires and the generic scorer path stays byte-identical.
"""
from __future__ import annotations

from cg.api import AreaType, OptionType, all_card_data

# ── deck card IDs (verified present in data/decks/hops_snorlax.csv + engine card data) ─────────────
SNORLAX = 304        # x2  Basic   (Extra Helpings: +30 to all Hop's attacks while in play; Dynamic Press)
CRAMORANT = 311      # x3  Basic   (Fickle Spitting 120 — ONLY if opp has exactly 3 or 4 prizes)
PHANTUMP = 878       # x4  Basic   (evolves into Trevenant)
TREVENANT = 879      # x4  Stage 1 (Corner 90 + retreat-lock; Horrifying Revenge 30)
HOPS_BAG = 1115      # x4  Item
POKEGEAR = 1122      # x4  Item
TRANSCEIVER = 1134   # x4  Item
CHOICE_BAND = 1171   # x4  Tool     Hop's only: −1 {C} cost, +30 to opp Active
PETREL = 1219        # x4  Supporter
LILLIE = 1227        # x4  Supporter
POSTWICK = 1255      # x4  Stadium  +30 to Hop's attacks vs opp Active
HILDA = 1225         # x3  Supporter
POKE_PAD = 1152      # x2  Item
BOSS = 1182          # x2  Supporter
XEROSIC = 1197       # x2  Supporter
SECRET_BOX = 1092    # x1  Item
NIGHT_STRETCHER = 1097  # x1 Item
MIST_ENERGY = 11     # x4  Special {C}
TELEPATH_ENERGY = 19 # x4  Special {P}

# Full 60-card decklist (used by the lethal verifier's determinization when piloting this deck).
HOPS_SNORLAX_DECK = (
    [SNORLAX] * 2 + [CRAMORANT] * 3 + [PHANTUMP] * 4 + [TREVENANT] * 4
    + [HOPS_BAG] * 4 + [POKEGEAR] * 4 + [TRANSCEIVER] * 4 + [CHOICE_BAND] * 4
    + [PETREL] * 4 + [LILLIE] * 4 + [POSTWICK] * 4 + [HILDA] * 3 + [POKE_PAD] * 2
    + [BOSS] * 2 + [XEROSIC] * 2 + [SECRET_BOX] + [NIGHT_STRETCHER]
    + [MIST_ENERGY] * 4 + [TELEPATH_ENERGY] * 4
)
assert len(HOPS_SNORLAX_DECK) == 60

# The four Hop's Pokémon uniquely identify the deck (its only Pokémon, disjoint from Crustle/Lucario/
# Starmie/Dunsparce/Iono/Fezandipiti signatures), so at least one is always in our active/bench/hand/
# discard whenever we pilot it.
_SIGNATURE = {SNORLAX, CRAMORANT, PHANTUMP, TREVENANT}

# Hop's attack ids and printed base damage.
ATK_DYNAMIC_PRESS = 422       # Snorlax   140 (CCC, 80 recoil)
ATK_FICKLE_SPITTING = 433     # Cramorant 120 (C)  — does NOTHING unless opp prizes ∈ {3,4}
ATK_HORRIFYING_REVENGE = 1267  # Trevenant 30 (C)
ATK_CORNER = 1268             # Trevenant 90 (P+CC, retreat-lock)
ATK_SPLASHING_DODGE = 1266    # Phantump  10 (C)  — flip-to-prevent, ~no offence
_BASE_DMG = {
    ATK_DYNAMIC_PRESS: 140, ATK_FICKLE_SPITTING: 120, ATK_CORNER: 90,
    ATK_HORRIFYING_REVENGE: 30, ATK_SPLASHING_DODGE: 10,
}

# ── card metadata (loaded once) ───────────────────────────────────────────────────────────────────
try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}

# Lazily-bound generic scorer (the deck-agnostic table this specialist delegates to). Imported on
# first use to avoid a circular import at module load (scorer imports this module).
_scorer = None


def _generic():
    global _scorer
    if _scorer is None:
        try:
            import scorer as s
        except Exception:
            from agent import scorer as s
        _scorer = s
    return _scorer


def _id(card):
    return getattr(card, "id", None) if card is not None else None


def _energies(p) -> int:
    try:
        return len(p.energies or [])
    except Exception:
        return 0


def _has_tool(p) -> bool:
    try:
        return bool(getattr(p, "tools", None))
    except Exception:
        return False


def is_hops_snorlax_deck(state, me_i: int) -> bool:
    """True if our side is piloting the Hop's line (a signature Pokémon is visible on our side)."""
    try:
        me = state.players[me_i]
        for zone in (me.active or [], me.bench or [], me.hand or [], me.discard or []):
            for c in zone:
                if _id(c) in _SIGNATURE:
                    return True
    except Exception:
        return False
    return False


def _snorlax_in_play(me) -> bool:
    try:
        for zone in (me.active or [], me.bench or []):
            for p in zone:
                if _id(p) == SNORLAX:
                    return True
    except Exception:
        return False
    return False


def _our_postwick(state) -> bool:
    try:
        for s in (state.stadium or []):
            if getattr(s, "id", None) == POSTWICK:
                return True
    except Exception:
        return False
    return False


def _buffed_damage(attack_id, attacker, me, state, opp_active) -> int:
    """Printed base + the Hop's +30 buff stack (Extra Helpings / Postwick / Choice Band), then ×2 on
    weakness. Best-effort estimate; agent/lethal.py is the exact arbiter for actual KOs."""
    base = _BASE_DMG.get(attack_id, 0)
    if base <= 0:
        return 0
    buff = 0
    if _snorlax_in_play(me):
        buff += 30
    if _our_postwick(state):
        buff += 30
    if attacker is not None and _has_tool(attacker):
        buff += 30
    dmg = base + buff
    try:
        adata = _CARD.get(_id(attacker))
        ddata = _CARD.get(_id(opp_active))
        if adata is not None and ddata is not None and ddata.weakness is not None \
                and ddata.weakness == adata.energyType:
            dmg *= 2
    except Exception:
        pass
    return dmg


# ── ATTACK override (the only thing the generic table gets wrong for this archetype) ──────────────
def _score_attack(obs, o, me_i) -> float:
    state = obs.current
    me = state.players[me_i]
    opp = state.players[1 - me_i]
    op_prizes = len(opp.prize)
    aid = o.attackId

    # Cramorant's Fickle Spitting whiffs entirely off 3/4 prizes — score below END so we don't waste
    # the turn (any productive setup option already outranks an attack on the generic scale).
    if aid == ATK_FICKLE_SPITTING and op_prizes not in (3, 4):
        return -1.0
    # Phantump's 10-damage coin-flip attack: only an absolute last resort.
    if aid == ATK_SPLASHING_DODGE:
        return 0.5

    attacker = me.active[0] if (me.active and me.active[0] is not None) else None
    opp_active = opp.active[0] if (opp.active and opp.active[0] is not None) else None
    dmg = _buffed_damage(aid, attacker, me, state, opp_active)
    is_ko = opp_active is not None and dmg > 0 and dmg >= (opp_active.hp or 0)

    # Dynamic Press hits Snorlax for 80 recoil. If it would NOT KO and the recoil would faint our
    # Snorlax (its HP <= 80) we'd throw away the +30 Extra Helpings engine for nothing — avoid it and
    # let a cheaper, recoil-free attacker (Corner / Cramorant) or more setup take priority.
    if aid == ATK_DYNAMIC_PRESS and not is_ko and attacker is not None:
        if (getattr(attacker, "hp", 0) or 0) <= 80:
            return 1.0

    # Same scale as the generic scorer's ATTACK branch so it composes with the (generic) scores of
    # every other option on the MAIN menu.
    score = 100.0 + min(dmg, 250) * 0.2
    if aid == ATK_CORNER:
        score += 10.0  # prefer the recoil-free retreat-lock control attack on ties
    if aid == ATK_DYNAMIC_PRESS and not is_ko:
        score -= 12.0  # mild recoil tax when it doesn't secure a KO
    if is_ko:
        score += 150.0  # a KO
        prize = _generic().prize_count(opp_active)
        if op_prizes <= prize:
            return 50000.0  # this KO takes their last prize(s): game-winning
    return score


# ── entry points: delegate everything except ATTACK to the proven generic scorer ──────────────────
def score_main(obs, o, me_i) -> float:
    if o.type == OptionType.ATTACK:
        try:
            return _score_attack(obs, o, me_i)
        except Exception:
            pass
    g = _generic()
    state = obs.current
    me = state.players[me_i]
    opp = state.players[1 - me_i]
    return g._score_main(obs, o, me, opp, me_i)


def score_sub(obs, o, me_i, context) -> float:
    g = _generic()
    state = obs.current
    me = state.players[me_i]
    opp = state.players[1 - me_i]
    return g._score_sub(obs, o, context, me, opp, me_i, 1 - me_i)

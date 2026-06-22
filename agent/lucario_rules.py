"""Mega Lucario ex aggro-deck specialist scoring (id-gated), consulted by agent/scorer.best_options.

The generic scorer plays a balanced, setup-heavy game and pilots the MEGA LUCARIO ex deck poorly
(~33% in our round-robin) because Lucario is the *opposite* of a setup deck: it is a fast Mega-ex
beatdown that wants to evolve Riolu -> Mega Lucario ex (678, a 340HP Stage-1 Mega) as fast as
possible, dump energy onto the one main attacker, and start swinging for KOs to win the prize race.

`is_lucario_deck(state, me_i)` detects we are piloting the Lucario line (a 673-678 Pokemon is on our
side). `score_main` / `score_sub` then produce a *self-consistent* score for every option (same scale
family as the Crustle specialist) so best_options can rank a whole turn with this aggressive table
instead of the generic one. For any other deck none of this fires (no 673-678 on our side), so the
generic + Crustle paths are completely untouched.

Rule set distilled from the 4 reference Mega-Lucario notebooks (kiyotah / harukiharada / nursrijan /
pilkwang), all descended from the official kiyotah sample agent:
  - Evolve Riolu -> Mega Lucario ex ASAP (highest tempo gain).
  - Concentrate energy on the *active* main attacker first; Lucario line wants 2 energy
    (Aura Jab = 1, Mega Brave = 2), Hariyama 3, Solrock exactly 1, Lunatone never.
  - Aura Jab (982: 1E, 130 dmg, re-attaches up to 3 F energy from discard to the bench) is the
    default repeatable attack; Mega Brave (983: 2E, 270 dmg, locked out next turn) only when the
    extra damage is needed for a KO. Weakness doubles damage.
  - Premium Power Pro (+30 to F attacks) only on a turn we actually attack and when the +30 changes
    a KO outcome.
  - Boss's Orders gusts up a benched opponent only when that benched mon is the best KO/target.
  - Prize guard: when we are at our last 2-3 prizes, do not over-expose the 3-prize Mega-ex.
  - Crustle (345) is immune to ex/Mega-ex damage -> never throw the ex into the wall.
"""
from __future__ import annotations

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext, all_attack, all_card_data

# ── Lucario deck card IDs (verified present in data/decks/lucario_praxel.csv + engine card data) ──
MAKUHITA = 673      # Basic F, 80HP  -> Hariyama
HARIYAMA = 674      # Stage1 F, 150HP, Heave-Ho Catcher (evolve helper); Wild Press 210 (70 recoil)
LUNATONE = 675      # Basic F, 110HP, Lunar Cycle ability (energy accel w/ Solrock); Power Gem 50
SOLROCK = 676       # Basic F, 110HP, Cosmic Beam 70 (needs Lunatone on bench)
RIOLU = 677         # Basic F, 80HP  -> Mega Lucario ex
MEGA_LUCARIO = 678  # Stage1 Mega-ex F, 340HP. Aura Jab (982) / Mega Brave (983). THE attacker.

DUSK_BALL = 1102
SWITCH = 1123
PREMIUM_POWER_PRO = 1141   # item: F attacks +30 dmg to opp Active this turn
FIGHTING_GONG = 1142       # item: search deck for Basic F energy or Basic F Pokemon
POKE_PAD = 1152            # item: search deck for a non-Rule-Box Pokemon
HEROS_CAPE = 1159          # tool: +100 HP
BOSS_ORDERS = 1182         # supporter: gust a benched opponent to active
CARMINE = 1192             # supporter: draw
LILLIE = 1227             # supporter: shuffle hand, draw 6 (if 6 prizes)
GRAVITY_MOUNTAIN = 1252    # stadium: Stage-2 -30HP both sides
BASIC_F = 6                # Basic Fighting Energy

# Attack IDs / costs (verified via all_attack):
AURA_JAB = 982            # 1 F, 130 dmg, +re-attach up to 3 F energy from discard to bench
MEGA_BRAVE = 983          # 2 F, 270 dmg, this Pokemon can't use Mega Brave next turn
WILD_PRESS = 978          # Hariyama, 3 F, 210 dmg (70 recoil)

# The opponent's Crustle wall (Stage-1, 345) negates damage from ex/Mega-ex attacks.
CRUSTLE = 345

# Full 60-card decklist (used by the lethal verifier's determinization while piloting Lucario).
LUCARIO_DECK = (
    [MAKUHITA] * 2 + [HARIYAMA] * 2 + [LUNATONE] * 2 + [SOLROCK] * 3 + [RIOLU] * 3 + [MEGA_LUCARIO] * 4
    + [DUSK_BALL] * 4 + [SWITCH] * 2 + [PREMIUM_POWER_PRO] * 4 + [FIGHTING_GONG] * 4 + [POKE_PAD] * 4
    + [HEROS_CAPE] + [BOSS_ORDERS] * 2 + [CARMINE] * 4 + [LILLIE] * 4 + [GRAVITY_MOUNTAIN] * 2
    + [BASIC_F] * 13
)
assert len(LUCARIO_DECK) == 60

# At least one of these is always on our side (we must have an Active Pokemon) and none of them
# appear in any other deck (verified) -> detection is reliable and false-positive-free.
_SIGNATURE = {MAKUHITA, HARIYAMA, LUNATONE, SOLROCK, RIOLU, MEGA_LUCARIO}

# The two Lucario-line attackers: where energy and evolution effort concentrate.
_LUCARIO_LINE = {RIOLU, MEGA_LUCARIO}
LUCARIO_ENERGY_GOAL = 2   # Aura Jab needs 1, Mega Brave needs 2 -> "ready" at 2
HARIYAMA_ENERGY_GOAL = 3
SOLROCK_ENERGY_GOAL = 1

KEY_PIECES = {MEGA_LUCARIO, RIOLU, HEROS_CAPE}        # never discard if avoidable
USEFUL_PIECES = {HARIYAMA, MAKUHITA, LUNATONE, SOLROCK, BOSS_ORDERS,
                 PREMIUM_POWER_PRO, FIGHTING_GONG, DUSK_BALL, POKE_PAD, SWITCH}

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

# ── card / attack metadata (loaded once) ────────────────────────────────────────────────────────
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
    return card_id in (MAKUHITA, LUNATONE, SOLROCK, RIOLU)


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


def is_lucario_deck(state, me_i: int) -> bool:
    """True if our side is piloting the Mega Lucario line (a 673-678 Pokemon is visible on our side)."""
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


def _my_prize_count(state, me_i) -> int:
    try:
        return len(state.players[me_i].prize)
    except Exception:
        return 6


def _f_energy_in_discard(state, me_i) -> int:
    try:
        return sum(1 for c in (state.players[me_i].discard or []) if _id(c) == BASIC_F)
    except Exception:
        return 0


def _attack_damage(attacker, attack_id, defender) -> int:
    """Weakness/resistance-aware base damage of an attack (mirrors the generic scorer)."""
    atk = _ATK.get(attack_id)
    if atk is None:
        return 0
    dmg = getattr(atk, "damage", 0) or 0
    if dmg <= 0:
        return 0
    adata = _meta(_id(attacker))
    ddata = _meta(_id(defender))
    if adata is not None and ddata is not None:
        atype = getattr(adata, "energyType", None)
        wk = getattr(ddata, "weakness", None)
        rs = getattr(ddata, "resistance", None)
        if wk is not None and wk == atype:
            dmg *= 2
        elif rs is not None and rs == atype:
            dmg = max(0, dmg - 30)
    return dmg


def _opponent_value(p) -> float:
    """How tempting an opponent Pokemon is as a KO / gust target (prize value + investment)."""
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
    v += _energy_count(p) * 40
    try:
        v += len(p.tools or []) * 30
    except Exception:
        pass
    v += (getattr(p, "hp", 0) or 0) // 10
    return v


# ── MAIN-turn scoring ─────────────────────────────────────────────────────────────────────────
# Priority (high score = do first within a turn, all setup BEFORE the turn-ending attack):
#   EVOLVE-to-Mega/Hariyama > play Pokemon to a thin bench > ABILITY > Hero's Cape > ATTACH-energy
#   > Boss's-Orders(gust to a real target) > draw/search > Premium-Power-Pro(only if it makes a KO)
#   > ATTACK (Aura-Jab default / Mega-Brave for the KO) > END > RETREAT(only to promote an attacker)
def score_main(obs, o, me_i) -> float:
    state = obs.current
    t = o.type

    if t == OptionType.EVOLVE:
        # Evolving Riolu -> Mega Lucario ex is the single biggest tempo gain; do it before attaching
        # energy so the energy lands on (and stays on) the 340HP Mega. Hariyama next.
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        if cid == MEGA_LUCARIO:
            return 2600.0
        if cid == HARIYAMA:
            return 2400.0
        return 2300.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        active = _my_active(state, me_i)
        bench_n = _my_bench_count(state, me_i)

        # Develop the board: get bodies down (Riolu first — it becomes the attacker).
        if _is_basic_pokemon(cid) or cid in (MAKUHITA, RIOLU, LUNATONE, SOLROCK):
            base = 2200.0 if cid == RIOLU else 2000.0
            if bench_n <= 0:
                return base + 200.0   # empty bench: a body is survival-critical
            if bench_n < 3:
                return base
            return 700.0              # deep bench: no rush

        # Hero's Cape: armour the main attacker (active Mega Lucario / Riolu).
        if cid == HEROS_CAPE:
            if _id(active) in _LUCARIO_LINE:
                return 1750.0
            return 900.0

        # Search items: dig for the Lucario line / energy. Cheap, do them to develop.
        if cid == FIGHTING_GONG:
            return 1500.0   # fetches F energy or a Basic F Pokemon -> fuels the attacker
        if cid in (DUSK_BALL, POKE_PAD):
            return 1450.0

        # Draw supporters: keep the hand flowing (only one supporter per turn; engine gates it).
        if cid in (LILLIE, CARMINE):
            return -1.0 if getattr(state, "supporterPlayed", False) else 1400.0

        # Boss's Orders: gust only when a benched opponent is the best target (else save it).
        if cid == BOSS_ORDERS:
            if getattr(state, "supporterPlayed", False):
                return -1.0
            opp = state.players[1 - me_i]
            bench = [b for b in (opp.bench or []) if b is not None]
            oa = _opp_active(state, me_i)
            if bench:
                best_bench = max(_opponent_value(b) for b in bench)
                active_val = _opponent_value(oa) if oa is not None else 0.0
                if best_bench > active_val + 40:
                    return 1700.0   # a juicier KO sits on their bench -> drag it up
            return -1.0

        # Premium Power Pro: +30 to F attacks this turn. Worth it ONLY on a turn we attack and
        # only when the +30 converts a non-KO swing into a KO (mirrors the notebooks).
        if cid == PREMIUM_POWER_PRO:
            oa = _opp_active(state, me_i)
            if oa is None or _id(active) not in _LUCARIO_LINE:
                return -1.0
            hp = oa.hp or 0
            best_dmg = 0
            for aid in (AURA_JAB, MEGA_BRAVE):
                best_dmg = max(best_dmg, _attack_damage(active, aid, oa))
            if best_dmg < hp <= best_dmg + 30:   # the +30 is exactly what turns it into a KO
                return 1600.0
            return -1.0

        # Gravity Mountain: situational (Stage-2 -30HP). Low unless a stadium war matters.
        if cid == GRAVITY_MOUNTAIN:
            return -1.0 if getattr(state, "stadiumPlayed", False) else 400.0

        if cid == SWITCH:
            return 300.0   # only meaningfully ranked when a benched attacker is better (rare)
        return 600.0

    if t == OptionType.ABILITY:
        # Lunatone's Lunar Cycle (energy accel), Hariyama's evolve helper, etc. Fire them early.
        return 2100.0

    if t == OptionType.ATTACH:
        card = _get(obs, o.area, o.index, me_i)
        active = _my_active(state, me_i)
        active_id = _id(active)
        # Concentrate energy on the ACTIVE main attacker until it can swing, then pre-fuel a bench
        # Lucario, then top-ups / support. The whole plan is to power ONE attacker fast.
        if o.inPlayArea == AreaType.ACTIVE:
            if active_id in _LUCARIO_LINE:
                return 1600.0 if _energy_count(active) < LUCARIO_ENERGY_GOAL else 1080.0
            if active_id == HARIYAMA:
                return 1500.0 if _energy_count(active) < HARIYAMA_ENERGY_GOAL else 1050.0
            if active_id == SOLROCK:
                return 1400.0 if _energy_count(active) < SOLROCK_ENERGY_GOAL else 1000.0
            if active_id == LUNATONE:
                return 1000.0   # Lunatone never wants its own energy
            return 1100.0
        if o.inPlayArea == AreaType.BENCH:
            tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
            tid = _id(tgt)
            if tid in _LUCARIO_LINE:
                return 1300.0 if _energy_count(tgt) < LUCARIO_ENERGY_GOAL else 1020.0
            if tid == HARIYAMA:
                return 1250.0 if _energy_count(tgt) < HARIYAMA_ENERGY_GOAL else 1010.0
            if tid == SOLROCK:
                return 1200.0 if _energy_count(tgt) < SOLROCK_ENERGY_GOAL else 1000.0
            return 1005.0
        return 1000.0

    if t == OptionType.ATTACK:
        # Attack last (it ends the turn) but pick the best one. Stays below all setup actions but
        # well above END so we always swing once the board is built.
        oa = _opp_active(state, me_i)
        active = _my_active(state, me_i)
        dmg = _attack_damage(active, o.attackId, oa)

        # Crustle (345) negates damage from our Mega-ex -> never waste the ex on the wall.
        if _id(oa) == CRUSTLE:
            ad = _meta(_id(active))
            if ad is not None and getattr(ad, "megaEx", False):
                return -50.0

        score = 100.0 + min(max(dmg, 0), 300) * 0.3
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 200.0  # KO
            # Prefer the repeatable Aura Jab when it already KOs (Mega Brave locks us out next turn).
            if o.attackId == AURA_JAB:
                score += 60.0
            # Game-winning swing: this KO takes their last prize(s).
            try:
                opp = state.players[1 - me_i]
                from scorer import prize_count as _pc
                if len(opp.prize) <= _pc(oa):
                    return 50000.0
            except Exception:
                pass
        return score

    if t == OptionType.RETREAT:
        # Aggro stays put — unless we're stuck with a non-attacker active while a Lucario/Hariyama
        # that can swing sits benched.
        active = _my_active(state, me_i)
        if _id(active) not in _LUCARIO_LINE and _id(active) != HARIYAMA:
            if _bench_has_id(state, me_i, MEGA_LUCARIO) or _bench_has_id(state, me_i, HARIYAMA):
                return 250.0
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

    # Turn order: an aggressive deck wants to go FIRST to start the Riolu->Mega clock a turn sooner.
    if t == OptionType.YES:
        return score + (150.0 if context == SelectContext.IS_FIRST else 100.0)
    if t == OptionType.NO:
        return score + (0.0 if context == SelectContext.IS_FIRST else 0.0)
    if t == OptionType.SPECIAL_CONDITION:
        return 2000.0
    if t == OptionType.NUMBER:
        return score + (getattr(o, "number", 0) or 0)

    if t in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD, OptionType.ENERGY):
        card = _get(obs, o.area, o.index, getattr(o, "playerIndex", me_i))
        cid = _id(card)

        # Energy-card sub-selections (discard / move): pitch nothing valuable; F energy is the deck's
        # lifeblood, but when forced to discard energy a basic F is the only choice we have anyway.
        if t in (OptionType.ENERGY_CARD, OptionType.ENERGY) and not isinstance(card, Pokemon):
            return score

        if card is not None:
            if context in PLACEMENT_CTX:
                score += 500.0
                # Place / fetch / promote the attacker line preferentially.
                if cid == MEGA_LUCARIO:
                    score += 160.0
                elif cid == RIOLU:
                    score += 120.0
                elif cid == HARIYAMA:
                    score += 90.0
                elif cid in (MAKUHITA, SOLROCK, LUNATONE):
                    score += 40.0
                if _is_basic_pokemon(cid) and _my_bench_count(state, me_i) <= 0:
                    score += 400.0   # empty bench -> a benchable Basic is the priority fetch
            elif context == SelectContext.TO_HAND and cid in (RIOLU, MEGA_LUCARIO):
                score += 150.0   # search effects: grab the attacker line

            if isinstance(card, Pokemon):
                if getattr(o, "playerIndex", me_i) == opp_i:
                    # Targeting the opponent (gust / damage / boss): hit their most valuable mon.
                    score += 500.0 if o.area == AreaType.ACTIVE else 100.0
                    score += _opponent_value(card)
                else:
                    if context in HEAL_CTX:
                        score += max(0, (getattr(card, "maxHp", 0) or 0) - (getattr(card, "hp", 0) or 0))
                    else:
                        score += getattr(card, "hp", 0) or 0
                        if cid == MEGA_LUCARIO:
                            score += 80.0   # promote/keep the attacker
                        elif cid == RIOLU:
                            score += 40.0
            else:
                if context in GIVE_UP_CTX:
                    if cid in KEY_PIECES:
                        score -= 300.0      # protect the attacker line + Hero's Cape
                    elif cid in USEFUL_PIECES:
                        score -= 80.0
                    elif cid == BASIC_F:
                        score += 60.0       # spare basic energy is the cheapest pitch

    return score

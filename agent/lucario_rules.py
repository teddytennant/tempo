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

WALL MODE (the Crustle matchup, agent/bots/bot_crustle*). Crustle (345) has an ability that negates
ALL damage from ex/Mega-ex attacks AND swings back for 120 (Superb Scissors) while its deck heals and
tries to deck us out. Throwing the Mega Lucario ex into it whiffs for 0 every turn (the old 0/60 bug).
When `_opp_active_ex_immune` sees the wall on the opponent's Active we switch plans (and ONLY then):
  - Route through the NON-ex Hariyama (Wild Press 210 one-shots Crustle 150 / Dwebble 70, ignoring the
    ex-immunity): search for + evolve the Makuhita->Hariyama line, pour energy into it, promote it
    active, and Wild Press the wall every turn. Hero's Cape goes on Hariyama (250HP survives 120+recoil).
  - Never attack the wall with the ex (scored below END); use Boss's Orders / Hariyama's Heave-Ho to
    gust a NON-immune benched target (a Dwebble) up so the cheap ex Aura Jab (1E) can KO it.
  - Anti-deck-out: suppress our own draw engine (Lillie / Carmine / Lunatone's Lunar Cycle) once the
    deck is thin so the staller can't outlast us — we were milling ourselves out.
This is fully gated on the wall being Active, so aggressive play vs every normal opponent is unchanged.
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
# Where Premium Power Pro sits in the ranking. The buff lasts the whole turn, so WHEN we play it
# inside the turn is free -- but the scorer is greedy per decision, so the score decides which other
# development it displaces. Both values sit above every non-game-winning ATTACK score (max ~450:
# 100 + 300*0.3 + 60 Aura-Jab bias + 200 KO) and below every setup/search card, making the buff the
# last thing we do before swinging rather than something that pushes Dusk Ball / Poke Pad down the
# menu. See the guard in score_main for the frontier measurement these replaced.
PPP_SCORE = 500.0
PPP_SCORE_KO = 700.0
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

# Full 60-card decklist, used by the lethal verifier (scorer.py) to determinize the unseen part
# of our deck while it searches for a game-winning line this turn.
#
# It MUST be the list we are actually piloting. The reference list below is the one this module
# was written against; when we swap to another team's Lucario build (currently Majkel1337's exact
# August list) the two diverge — that build differs from the reference on 16 of 60 cards (Ultra
# Ball / Judge / Wally's Compassion in, Dusk Ball / Carmine / Gravity Mountain out). A verifier
# determinizing from the wrong list can "prove" a lethal that draws a card we do not own, which is
# precisely the impossible-line failure the belief correction in lethal.py exists to prevent — and
# that path decides whether we actually close out won games. So read the bundled deck.csv (the
# single source of truth the build script writes) and fall back to the reference list only if it
# cannot be read.
_REFERENCE_DECK = (
    [MAKUHITA] * 2 + [HARIYAMA] * 2 + [LUNATONE] * 2 + [SOLROCK] * 3 + [RIOLU] * 3 + [MEGA_LUCARIO] * 4
    + [DUSK_BALL] * 4 + [SWITCH] * 2 + [PREMIUM_POWER_PRO] * 4 + [FIGHTING_GONG] * 4 + [POKE_PAD] * 4
    + [HEROS_CAPE] + [BOSS_ORDERS] * 2 + [CARMINE] * 4 + [LILLIE] * 4 + [GRAVITY_MOUNTAIN] * 2
    + [BASIC_F] * 13
)
assert len(_REFERENCE_DECK) == 60


def _load_piloted_deck():
    """The 60 ids in the bundled deck.csv, or None if it is missing/unreadable/not 60 cards."""
    import os as _os
    cands = []
    try:
        cands.append(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "deck.csv"))
    except Exception:
        pass
    cands += ["deck.csv", "/kaggle_simulations/agent/deck.csv"]
    for p in cands:
        try:
            if not _os.path.exists(p):
                continue
            with open(p) as f:
                ids = [int(x) for x in f.read().splitlines() if x.strip()]
            if len(ids) == 60:
                return ids
        except Exception:
            continue
    return None


LUCARIO_DECK = _load_piloted_deck() or list(_REFERENCE_DECK)
assert len(LUCARIO_DECK) == 60

# At least one of these is always on our side (we must have an Active Pokemon) and none of them
# appear in any other deck (verified) -> detection is reliable and false-positive-free.
_SIGNATURE = {MAKUHITA, HARIYAMA, LUNATONE, SOLROCK, RIOLU, MEGA_LUCARIO}

# The two Lucario-line attackers: where energy and evolution effort concentrate.
_LUCARIO_LINE = {RIOLU, MEGA_LUCARIO}
LUCARIO_ENERGY_GOAL = 2   # Aura Jab needs 1, Mega Brave needs 2 -> "ready" at 2
HARIYAMA_ENERGY_GOAL = 3
SOLROCK_ENERGY_GOAL = 1

# Anti-deck-out: stall/wall decks (Crustle) win by outlasting us, so once our deck is this thin we
# stop firing the draw engine (Lillie / Carmine / Lunatone's Lunar Cycle) that would mill us out.
LOW_DECK_COUNT = 8
# Vs the ex-wall the game is a long grind we can lose by decking out, and our draw engine burns
# ~9 cards/turn (Lillie 6 + Lunatone 3). Against the wall we keep a MUCH larger deck buffer (and
# lean on the non-milling search cards to find Hariyama instead of raw draw).
WALL_DECK_GUARD = 12

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


def _compute_ex_immune_ids():
    """Card IDs whose ability prevents ALL damage from our ex/Mega-ex attacks (the wall).

    Crustle (345) is the known case; we also scan the card DB so any future printing with the
    same "Prevent all damage ... {ex}" ability is recognised without a code change."""
    ids = {CRUSTLE}
    for cid, c in _CARD.items():
        try:
            for s in (getattr(c, "skills", None) or []):
                txt = (getattr(s, "text", "") or "").lower()
                if "prevent all damage" in txt and "ex" in txt:
                    ids.add(cid)
        except Exception:
            pass
    return ids


# Opponent actives that are immune to our ex/Mega-ex attacks (Mega Lucario whiffs into these).
_EX_IMMUNE_IDS = _compute_ex_immune_ids()


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
    """True if our side is piloting the Mega Lucario line (a 673-678 Pokemon is visible on our side).

    Detection is by *visible* cards, which is right once the game is under way but leaves a hole at
    the very first decision of the game: "would you like to go first?" (SelectContext.IS_FIRST) is
    asked before the opening hand is dealt, so our side is completely empty and every archetype
    specialist gets bypassed for the one decision that sets the tempo of the whole game. Measured on
    the 2026-08-08 ladder dump, that hole fired on 93 of 93 real IS_FIRST positions.

    We do not have to infer our archetype from the board there — we ship the decklist. So when
    nothing at all is visible on our side, fall back to the bundled deck.csv (LUCARIO_DECK). This
    can only fire on an empty board, i.e. before the opening hand exists; in every other position
    the visible-card test below is unchanged.
    """
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
        if not (me.active or me.bench or me.hand or me.discard):
            return any(cid in _SIGNATURE for cid in LUCARIO_DECK)
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


def _is_ex(card_id) -> bool:
    """True if this Pokemon is an ex / Mega-ex (its attack damage is negated by the ex-wall)."""
    cd = _meta(card_id)
    if cd is None:
        return card_id == MEGA_LUCARIO
    return bool(getattr(cd, "ex", False) or getattr(cd, "megaEx", False))


def _opp_active_ex_immune(state, me_i) -> bool:
    """True when the opponent's ACTIVE negates damage from our ex attacks (Crustle wall).

    This is the trigger for "wall mode": our Mega Lucario ex does 0 effective damage to it, so we
    must route the turn through the NON-ex Hariyama line (Wild Press 210) instead of throwing the
    ex into the wall every turn. False for every normal opponent -> aggressive play is unchanged."""
    oa = _opp_active(state, me_i)
    return oa is not None and _id(oa) in _EX_IMMUNE_IDS


def _my_prize_count(state, me_i) -> int:
    try:
        return len(state.players[me_i].prize)
    except Exception:
        return 6


def _my_deck_count(state, me_i) -> int:
    try:
        return int(getattr(state.players[me_i], "deckCount", 999))
    except Exception:
        return 999


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


def _best_attack_on_menu(obs, state, me_i):
    """(is an ATTACK offered right now, best damage among the attacks offered).

    A turn-scoped damage buff is only ever worth a card on a turn we actually swing, and "an ATTACK
    is on this menu" is the engine's own statement that we can swing right now. Measured on the
    frontier's 2,552 real Premium Power Pro offers (tools/ppp_probe.py), this single feature
    separates a 3.3% play rate from a 23.7-41.9% one -- it is the rule, and the damage arithmetic
    below it is only a tie-break."""
    best, found = 0, False
    try:
        active = _my_active(state, me_i)
        defender = _opp_active(state, me_i)
        for opt in (obs.select.option or []):
            if opt.type != OptionType.ATTACK:
                continue
            found = True
            best = max(best, _attack_damage(active, opt.attackId, defender))
    except Exception:
        return found, best
    return found, best


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

    # Wall mode: the opponent's active is immune to our ex attacks (Crustle). When set, we route the
    # whole turn through the non-ex Hariyama line instead of whiffing the Mega Lucario ex into it.
    wall = _opp_active_ex_immune(state, me_i)

    if t == OptionType.EVOLVE:
        # Evolving Riolu -> Mega Lucario ex is the single biggest tempo gain; do it before attaching
        # energy so the energy lands on (and stays on) the 340HP Mega. Hariyama next.
        card = _get(obs, AreaType.HAND, o.index, me_i)
        cid = _id(card)
        if wall:
            # Against the ex-wall the Hariyama line is our ONLY damage source -> evolve it first.
            # (Makuhita -> Hariyama also fires Heave-Ho Catcher, gusting the wall off the active.)
            if cid == HARIYAMA:
                return 2800.0
            if cid == MEGA_LUCARIO:
                return 2500.0
            return 2300.0
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

        # Hero's Cape: armour the main attacker. Vs the wall, a +100HP Hariyama (250HP) survives a
        # Superb Scissors (120) AND its own Wild Press recoil (70), so it gets multiple KOs -> cape
        # the Hariyama line, not the ex (which can't break the wall anyway).
        if cid == HEROS_CAPE:
            if wall:
                if _bench_has_id(state, me_i, HARIYAMA) or _id(active) == HARIYAMA:
                    return 1750.0
                return 700.0
            if _id(active) in _LUCARIO_LINE:
                return 1750.0
            return 900.0

        # Search items: dig for the Lucario line / energy. Cheap, do them to develop.
        if cid == FIGHTING_GONG:
            return 1500.0   # fetches F energy or a Basic F Pokemon -> fuels the attacker
        if cid in (DUSK_BALL, POKE_PAD):
            return 1450.0

        # Draw supporters: keep the hand flowing (only one supporter per turn; engine gates it).
        # But against a deck-out staller, drawing into a thin deck loses us the game -> stop drawing.
        if cid in (LILLIE, CARMINE):
            if getattr(state, "supporterPlayed", False):
                return -1.0
            guard = WALL_DECK_GUARD if wall else LOW_DECK_COUNT
            if _my_deck_count(state, me_i) <= guard:
                return -1.0
            return 1400.0

        # Boss's Orders: gust only when a benched opponent is the best target (else save it).
        if cid == BOSS_ORDERS:
            if getattr(state, "supporterPlayed", False):
                return -1.0
            opp = state.players[1 - me_i]
            bench = [b for b in (opp.bench or []) if b is not None]
            oa = _opp_active(state, me_i)
            # Against the ex-wall, gust a benched (non-immune) target up so our Mega Lucario ex can
            # KO it -> the ex stays relevant by routing AROUND the wall, not just through Hariyama.
            if wall and bench and _id(active) in _LUCARIO_LINE:
                non_immune = [b for b in bench if _id(b) not in _EX_IMMUNE_IDS]
                if non_immune:
                    return 1800.0
            if bench:
                best_bench = max(_opponent_value(b) for b in bench)
                active_val = _opponent_value(oa) if oa is not None else 0.0
                if best_bench > active_val + 40:
                    return 1700.0   # a juicier KO sits on their bench -> drag it up
            return -1.0

        # Premium Power Pro: +30 to EVERY {F} attack this turn.
        #
        # This used to fire only when the +30 turned a specific swing into a knockout AND the Active
        # was in the Lucario line; everything else returned -1.0, i.e. below END, i.e. never. On the
        # frontier's own menus that guard is satisfied 83 times out of 2,552 offers, and the net
        # effect was that we played this card on 4 of 1,618 offers (0.2%) where the #1 player
        # (LB 1203.5) played it on 256 (15.8%) -- the largest single behavioural gap in the deck,
        # and the only one in tools/card_use.py that turn ORDERING cannot explain (re-ordering a
        # turn moves *when* you play a card, not whether you ever do).
        #
        # tools/ppp_probe.py buckets those 2,552 real offers by what a rule could key on:
        #   attack on the menu, +30 converts a KO    136 offers   41.9% played
        #   attack on the menu, does not convert     386          29.0%
        #   attack on the menu, already lethal       963          23.7%
        #   NO attack on the menu                   1067           3.3%
        #   active = Lucario line 19.8% | Solrock 18.2% | Hariyama 17.8%
        # So the rule is "are we swinging this turn", the KO-conversion case is a tie-break worth
        # ~1.4x, and the Lucario-line restriction is unjustified -- Solrock, Hariyama and Makuhita
        # are {F} too and the card boosts them identically. Card economy is not the constraint in a
        # deck running 4 copies behind Lunar Cycle (draw 3) and Lillie's Determination (draw 6):
        # a turn-scoped buff held in hand is worth nothing at end of turn.
        if cid == PREMIUM_POWER_PRO:
            has_attack, best_dmg = _best_attack_on_menu(obs, state, me_i)
            if not has_attack:
                return -1.0          # the buff expires unused -> keep the card
            oa = _opp_active(state, me_i)
            hp = (oa.hp or 0) if oa is not None else 0
            if oa is not None and best_dmg < hp <= best_dmg + 30:
                return PPP_SCORE_KO  # the +30 is exactly what turns this swing into a KO
            return PPP_SCORE         # otherwise still buff the swing

        # Gravity Mountain: situational (Stage-2 -30HP). Low unless a stadium war matters.
        if cid == GRAVITY_MOUNTAIN:
            return -1.0 if getattr(state, "stadiumPlayed", False) else 400.0

        if cid == SWITCH:
            # In wall mode, free-switch a benched Hariyama into the active spot so it sits there
            # accumulating energy and Wild Presses the wall the moment it reaches 3E (the active ex
            # is dead weight vs the wall). Otherwise Switch is rarely worth it.
            if wall and _id(active) in _LUCARIO_LINE and _bench_has_id(state, me_i, HARIYAMA):
                return 1800.0
            return 300.0   # only meaningfully ranked when a benched attacker is better (rare)
        return 600.0

    if t == OptionType.ABILITY:
        # Lunatone's Lunar Cycle draws 3 by pitching a Basic F energy — great early, but vs the wall
        # it both mills us toward deck-out AND discards the F energy Hariyama needs, so don't fire it
        # in wall mode (rely on search). Otherwise suppress only once our deck is thin.
        card = _get(obs, o.area, o.index, me_i)
        if _id(card) == LUNATONE:
            if wall:
                return -1.0
            if _my_deck_count(state, me_i) <= LOW_DECK_COUNT:
                return -1.0
        return 2100.0

    if t == OptionType.ATTACH:
        card = _get(obs, o.area, o.index, me_i)
        active = _my_active(state, me_i)
        active_id = _id(active)

        # Wall mode: the ex can't damage the wall, so pour energy into the non-ex Hariyama, whose Wild
        # Press (3E/210) is the only repeatable answer (one-shots both Crustle 150 and Dwebble 70 on
        # the active spot every turn). Solrock (Cosmic Beam, 1E/70) is a cheap backup vs Dwebbles.
        if wall:
            if o.inPlayArea == AreaType.ACTIVE:
                if active_id == HARIYAMA:
                    return 1700.0 if _energy_count(active) < HARIYAMA_ENERGY_GOAL else 1050.0
                if active_id in _LUCARIO_LINE:
                    return 900.0   # ex active can't damage the wall -> don't sink energy here
                if active_id == SOLROCK:
                    return 1400.0 if _energy_count(active) < SOLROCK_ENERGY_GOAL else 1000.0
                return 1000.0
            if o.inPlayArea == AreaType.BENCH:
                tgt = _get(obs, o.inPlayArea, o.inPlayIndex, me_i)
                tid = _id(tgt)
                if tid == HARIYAMA:
                    return 1700.0 if _energy_count(tgt) < HARIYAMA_ENERGY_GOAL else 1010.0
                if tid in _LUCARIO_LINE:
                    return 900.0
                if tid == SOLROCK:
                    return 1200.0 if _energy_count(tgt) < SOLROCK_ENERGY_GOAL else 1000.0
                return 1005.0
            return 1000.0

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

        # The wall (Crustle) negates damage from our ex/Mega-ex attacks -> never waste the ex on it
        # (this whiff was the 0/60 bug). Scored below END so we'd rather set up than swing for 0.
        if wall and _is_ex(_id(active)):
            return -50.0

        score = 100.0 + min(max(dmg, 0), 300) * 0.3
        # Aura Jab (982) is the DEFAULT repeatable attack: 130 dmg, re-attaches up to 3 F energy from
        # discard, and (unlike Mega Brave 983, which locks this Pokémon out next turn) keeps swinging.
        # Bias toward it on EVERY swing; the +200 KO term below still lets Mega Brave win the turns
        # where only its 270 dmg secures a KO. (Previously this +60 was trapped inside the KO branch,
        # so non-lethal turns defaulted to the lockout attack and skipped the energy re-attach.)
        if o.attackId == AURA_JAB:
            score += 60.0
        if oa is not None and dmg > 0 and dmg >= (oa.hp or 0):
            score += 200.0  # KO
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
        aid = _id(active)
        # Wall mode: our ex active is dead weight vs the wall -> retreat to promote a benched
        # Hariyama so it can Wild Press through (Switch is preferred when in hand, see PLAY).
        if wall and aid in _LUCARIO_LINE and _bench_has_id(state, me_i, HARIYAMA):
            return 260.0
        if aid not in _LUCARIO_LINE and aid != HARIYAMA:
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

    # Wall mode (opponent active is ex-immune): we win only through the non-ex Hariyama line, so our
    # searches/placements must dig for Hariyama + Makuhita + energy, not the dead ex line.
    wall = _opp_active_ex_immune(state, me_i)

    # Turn order: an aggressive deck wants to go FIRST to start the Riolu->Mega clock a turn sooner.
    # Corroborated two ways on 2026-08-09: real ladder Lucario players answered YES in 91 of 93
    # IS_FIRST positions in the 2026-08-08 dump, and a forced mirror A/B (tools/first_turn_ab.py)
    # put the player who went first at ~52% over 1000 games. scorer._score_sub says the opposite
    # ("going second is often better for a setup deck") and used to win by default, because
    # is_lucario_deck could not see an empty board — see the note there.
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
                # Place / fetch / promote the attacker line preferentially. Vs the wall the Hariyama
                # line (Makuhita -> Hariyama) is the attacker, so it leapfrogs the dead ex line.
                if wall:
                    if cid == HARIYAMA:
                        score += 180.0
                    elif cid == MAKUHITA:
                        score += 150.0
                    elif cid in (SOLROCK, LUNATONE):
                        score += 60.0
                    elif cid == MEGA_LUCARIO:
                        score += 40.0
                    elif cid == RIOLU:
                        score += 30.0
                elif cid == MEGA_LUCARIO:
                    score += 160.0
                elif cid == RIOLU:
                    score += 120.0
                elif cid == HARIYAMA:
                    score += 90.0
                elif cid in (MAKUHITA, SOLROCK, LUNATONE):
                    score += 40.0
                if _is_basic_pokemon(cid) and _my_bench_count(state, me_i) <= 0:
                    score += 400.0   # empty bench -> a benchable Basic is the priority fetch
            elif context == SelectContext.TO_HAND:
                # Search effects (Poké Pad / Dusk Ball / Fighting Gong): grab what wins the game.
                if wall:
                    # vs the wall, assemble the Hariyama line (Wild Press is the only answer) + energy.
                    if cid == HARIYAMA:
                        score += 320.0
                    elif cid == MAKUHITA:
                        score += 260.0
                    elif cid == BASIC_F:
                        score += 200.0
                    elif cid in (RIOLU, MEGA_LUCARIO):
                        score += 20.0   # the ex line can't break the wall -> low priority
                elif cid in (RIOLU, MEGA_LUCARIO):
                    score += 150.0   # normal: grab the ex attacker line

            if isinstance(card, Pokemon):
                if getattr(o, "playerIndex", me_i) == opp_i:
                    # Targeting the opponent (gust / damage / boss): hit their most valuable mon.
                    score += 500.0 if o.area == AreaType.ACTIVE else 100.0
                    score += _opponent_value(card)
                    # Gusting a benched opponent up (Boss's Orders / Hariyama's Heave-Ho) vs the
                    # wall: pull a NON-immune target our ex can actually KO (a Dwebble), never
                    # another ex-immune wall (which the ex still can't touch).
                    if (context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE)
                            and cid in _EX_IMMUNE_IDS and _opp_active_ex_immune(state, me_i)):
                        score -= 1000.0
                else:
                    if context in HEAL_CTX:
                        score += max(0, (getattr(card, "maxHp", 0) or 0) - (getattr(card, "hp", 0) or 0))
                    elif (context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE)
                          and _opp_active_ex_immune(state, me_i)):
                        # Choosing our new active against the ex-wall: send up the non-ex Hariyama
                        # (it can Wild Press through), never the ex (which whiffs for 0). Prefer a
                        # Hariyama that already has enough energy to swing this turn.
                        score += getattr(card, "hp", 0) or 0
                        if cid == HARIYAMA:
                            score += 200.0 + (300.0 if _energy_count(card) >= HARIYAMA_ENERGY_GOAL else 0.0)
                        elif cid in _LUCARIO_LINE:
                            score -= 300.0
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

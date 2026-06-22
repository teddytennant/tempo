"""Independent opponent: the Day-2 hardened Crustle wall bot (biohack44).

Faithful port of the published notebook
  biohack44__beating-the-day-2-new
to tempo's `cg.api`. Same proven "score every option, attack last" Crustle brain
as the day-1 #1 bot, with defensive upgrades that the notebook adds on top:
best-attack selection (prefer a KO), energy concentrated onto the wall, KO/prize-
aware targeting, heal the most-damaged mon, junk-aware discard, bench insurance
(avoid the "no Active Pokemon" loss), targeted Dwebble->Crustle retreat, and a
crash-proof guard. Runs the same 60-card Crustle list as bot_crustle (shared
deck_crustle.csv).

This is an independent policy — it does NOT call tempo's scorer. The logic below
is a verbatim reproduction of the notebook's `agent()`; only deck loading was
rewired to this bot's own decklist.
"""
from __future__ import annotations

import os

from cg.api import (
    AreaType, CardType, SelectType, SelectContext,
    OptionType, Pokemon, all_card_data, all_attack, to_observation_class,
)

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

KEY_PIECES = {CRUSTLE, DWEBBLE, HEROS_CAPE}
USEFUL_PIECES = {JUMBO_ICE_CREAM, COOK, CHEREN, BUDDY_POFFIN, BATTLE_CAGE}

PREFER_GO_FIRST = False

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

try:
    _CARD = {c.cardId: c for c in all_card_data()}
except Exception:
    _CARD = {}
try:
    _ATK = {a.attackId: a for a in all_attack()}
except Exception:
    _ATK = {}

_DECK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_crustle.csv")
with open(_DECK_PATH) as _f:
    _lines = [ln for ln in _f.read().splitlines() if ln.strip()]
DECK = [int(_lines[i]) for i in range(60)]


def card_meta(card_id):
    try:
        return _CARD.get(card_id)
    except Exception:
        return None


def attack_meta(attack_id):
    try:
        return _ATK.get(attack_id)
    except Exception:
        return None


def read_deck_csv():
    return DECK


def get_card(obs, area, index, player_index):
    try:
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
        if area == AreaType.LOOKING:
            return obs.current.looking[index]
    except Exception:
        return None
    return None


def _opp_active(obs, me):
    try:
        op = obs.current.players[1 - me]
        if op.active and op.active[0] is not None:
            return op.active[0]
    except Exception:
        pass
    return None


def opponent_value(p):
    v = 0
    cd = card_meta(getattr(p, "id", None))
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
        v += len(p.energies) * 40
    except Exception:
        pass
    try:
        v += len(p.tools) * 30
    except Exception:
        pass
    v += getattr(p, "hp", 0) // 10
    return v


def _my_active(obs, me):
    try:
        a = obs.current.players[me].active
        if a and a[0] is not None:
            return a[0]
    except Exception:
        pass
    return None


def _my_bench_count(obs, me):
    try:
        return len(obs.current.players[me].bench)
    except Exception:
        return 99


def _bench_has_id(obs, me, card_id):
    try:
        for b in obs.current.players[me].bench:
            if b is not None and getattr(b, "id", None) == card_id:
                return True
    except Exception:
        pass
    return False


def _is_basic_pokemon(card_id):
    cd = card_meta(card_id)
    if cd is not None:
        try:
            return bool(getattr(cd, "basic", False)) and getattr(cd, "cardType", None) == CardType.POKEMON
        except Exception:
            pass
    return card_id == DWEBBLE


def _score_main(obs, o, me):
    t = o.type

    if t == OptionType.ATTACH:
        card = get_card(obs, o.area, o.index, me)
        if card is not None and getattr(card, "id", None) == HEROS_CAPE:
            return 2100 if o.inPlayArea == AreaType.ACTIVE else 0
        if o.inPlayArea == AreaType.ACTIVE:
            return 1060
        if o.inPlayArea == AreaType.BENCH:
            tgt = get_card(obs, o.inPlayArea, o.inPlayIndex, me)
            if tgt is not None and getattr(tgt, "id", None) == CRUSTLE:
                return 1030
            return 1010
        return 1000

    if t == OptionType.EVOLVE:
        return 800

    if t == OptionType.PLAY:
        card = get_card(obs, AreaType.HAND, o.index, me)
        cid = getattr(card, "id", None) if card is not None else None
        active = None
        try:
            a = obs.current.players[me].active
            if a and a[0] is not None:
                active = a[0]
        except Exception:
            active = None
        if cid == JUMBO_ICE_CREAM:
            if active is not None and active.hp < active.maxHp and len(active.energies) >= 3:
                return 2000
            return -2
        if cid == COOK:
            if active is not None and active.hp < active.maxHp:
                return 1500
            return -2
        if cid == CHEREN:
            return 1400
        if cid == BATTLE_CAGE:
            return 1300
        if _is_basic_pokemon(cid):
            bench_n = _my_bench_count(obs, me)
            if bench_n <= 0:
                return 1700
            if bench_n == 1:
                return 700
            return 600
        return 600

    if t == OptionType.ABILITY:
        return 400

    if t == OptionType.ATTACK:
        score = 100.0
        a = attack_meta(o.attackId)
        dmg = getattr(a, "damage", 0) if a is not None else 0
        try:
            dmg = int(dmg)
        except Exception:
            dmg = 0
        score += min(max(dmg, 0), 250) * 0.2
        opp = _opp_active(obs, me)
        if opp is not None and dmg > 0 and dmg >= getattr(opp, "hp", 10 ** 9):
            score += 150
        return score

    if t == OptionType.RETREAT:
        active = _my_active(obs, me)
        if (active is not None and getattr(active, "id", None) == DWEBBLE
                and _bench_has_id(obs, me, CRUSTLE)):
            return 120
        return -1

    if t == OptionType.END:
        return 0

    return 0


def _score_sub(obs, o, me, context):
    t = o.type
    score = 2000.0

    if t == OptionType.CARD:
        card = get_card(obs, o.area, o.index, o.playerIndex)
        if card is not None:
            cid = getattr(card, "id", None)

            if context in PLACEMENT_CTX:
                score += 500
                if cid == CRUSTLE:
                    score += 120
                elif cid == DWEBBLE:
                    score += 80
                if _is_basic_pokemon(cid) and _my_bench_count(obs, me) <= 0:
                    score += 400
            elif context == SelectContext.TO_HAND and cid in (CRUSTLE, DWEBBLE):
                score += 100
                if cid == DWEBBLE and _my_bench_count(obs, me) <= 0:
                    score += 200

            if isinstance(card, Pokemon):
                if o.playerIndex != me:
                    score += 500 if o.area == AreaType.ACTIVE else 100
                    score += opponent_value(card)
                else:
                    if context in HEAL_CTX:
                        score += max(0, getattr(card, "maxHp", 0) - getattr(card, "hp", 0))
                    else:
                        score += getattr(card, "hp", 0)
                        if cid == CRUSTLE:
                            score += 60
            else:
                if context in GIVE_UP_CTX:
                    if cid in KEY_PIECES:
                        score -= 300
                    elif cid in USEFUL_PIECES:
                        score -= 80
                    elif cid == BASIC_GRASS:
                        score += 60

    elif t in (OptionType.ENERGY_CARD, OptionType.ENERGY):
        cid = getattr(o, "cardId", None)
        if context in (SelectContext.DISCARD_ENERGY_CARD, SelectContext.DISCARD_ENERGY,
                       SelectContext.TO_HAND_ENERGY, SelectContext.TO_DECK_ENERGY,
                       SelectContext.DETACH_FROM):
            if cid == BASIC_GRASS:
                score += 40
            elif cid in (GROW_GRASS, MIST, SPIKY):
                score -= 40

    elif t == OptionType.YES:
        if context == SelectContext.IS_FIRST and not PREFER_GO_FIRST:
            score += 0
        else:
            score += 100

    elif t == OptionType.NO:
        if context == SelectContext.IS_FIRST and not PREFER_GO_FIRST:
            score += 150
        else:
            score += 0

    elif t == OptionType.NUMBER:
        score += getattr(o, "number", 0) or 0

    elif t == OptionType.SPECIAL_CONDITION:
        score = 2000

    return score


def _legal_fallback(select):
    try:
        n = len(select.option)
        lo = select.minCount if select.minCount is not None else 1
        hi = select.maxCount if select.maxCount is not None else 1
        k = max(0, min(lo, hi, n))
        return list(range(n))[:k]
    except Exception:
        return [0]


def best_options(obs_dict: dict) -> list[int]:
    """Entry point (biohack44 hardened Crustle bot). Never raises."""
    try:
        obs = to_observation_class(obs_dict)
    except Exception:
        try:
            return read_deck_csv()
        except Exception:
            return []

    if obs.select is None:
        try:
            return read_deck_csv()
        except Exception:
            return []

    select = obs.select
    try:
        me = obs.current.yourIndex
    except Exception:
        me = 0
    context = getattr(select, "context", None)
    options = select.option

    try:
        is_main = (context == SelectContext.MAIN) or (
            getattr(select, "type", None) == SelectType.MAIN
        )
        scores = []
        for o in options:
            try:
                s = _score_main(obs, o, me) if is_main else _score_sub(obs, o, me, context)
            except Exception:
                s = 0
            scores.append(s)

        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        out = []
        limit = min(len(order), select.maxCount)
        for i in range(limit):
            idx = order[i]
            if scores[idx] >= 0 or len(out) < select.minCount:
                out.append(idx)

        if len(out) < select.minCount:
            for idx in order:
                if idx not in out:
                    out.append(idx)
                    if len(out) >= select.minCount:
                        break
        return out[: select.maxCount]
    except Exception:
        return _legal_fallback(select)


agent = best_options

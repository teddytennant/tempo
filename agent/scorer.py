"""tempo greedy heuristic scorer — frontier rule-based option ranker.

`best_options(obs_dict) -> list[int]` scores every option in `obs.select` and returns
a legal index list (length in [minCount, maxCount]). This is the no-search scorer that the
950-1140 Elo frontier notebooks win with: rich card valuation + a strict priority ordering on
the MAIN turn so that board-building / energy-attachment / evolution all happen BEFORE the
attack (an attack ends your turn).

It is deck-agnostic: every rule reads the engine card database (`all_card_data` / `all_attack`)
rather than hard-coding card IDs, with a few generic name-keyword detectors (draw supporters,
heal cards) so it transfers across decks. Adapted from:
  - romanrozen strong-start v10 (≈950): prize_count / pokemon_score primitives, priority order.
  - dashimaki360 / biohack44 crustle-bot: ATTACH>EVOLVE>PLAY>ABILITY>ATTACK>RETREAT ordering.
  - map1e114514 iwapalace (≈1000): resource-balance energy concentration.

Robustness contract: EVERYTHING is wrapped; on any error or empty result we return a
guaranteed-legal fallback. The scorer never forfeits with an empty/illegal selection.
"""
from __future__ import annotations

from cg.api import (
    AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext,
    all_attack, all_card_data, to_observation_class,
)

# Deck specialists (optional — generic path stands alone if these fail to import).
try:
    import grimmsnarl_rules as _grimmsnarl    # Marnie's Grimmsnarl ex (Tea Party #1 list) specialist
except Exception:
    try:
        from agent import grimmsnarl_rules as _grimmsnarl
    except Exception:
        _grimmsnarl = None
try:
    import tusk_rules as _tusk                # Great Tusk mill box (alancai27 stable-894 replica)
except Exception:
    try:
        from agent import tusk_rules as _tusk
    except Exception:
        _tusk = None
try:
    import crustle_rules as _crustle          # when agent/ is on sys.path (submission runtime)
except Exception:
    try:
        from agent import crustle_rules as _crustle
    except Exception:
        _crustle = None
try:
    import lucario_rules as _lucario          # Mega Lucario ex aggro specialist
except Exception:
    try:
        from agent import lucario_rules as _lucario
    except Exception:
        _lucario = None
try:
    import starmie_rules as _starmie          # Mega Starmie / Mega Froslass ex prize-race specialist
except Exception:
    try:
        from agent import starmie_rules as _starmie
    except Exception:
        _starmie = None
try:
    import cinderace_rules as _cinderace      # keidroid #1 Cinderace + Mega Starmie ex / Crushing Hammer
except Exception:
    try:
        from agent import cinderace_rules as _cinderace
    except Exception:
        _cinderace = None
try:
    import dunsparce_rules as _dunsparce       # Alakazam Powerful Hand / Dudunsparce draw-combo specialist
except Exception:
    try:
        from agent import dunsparce_rules as _dunsparce
    except Exception:
        _dunsparce = None
try:
    import iono_rules as _iono                  # Iono's Bellibolt ex Lightning energy-stacking specialist
except Exception:
    try:
        from agent import iono_rules as _iono
    except Exception:
        _iono = None
try:
    import fezandipiti_rules as _fezandipiti     # Fezandipiti ex / Alakazam "Powerful Hand" combo specialist
except Exception:
    try:
        from agent import fezandipiti_rules as _fezandipiti
    except Exception:
        _fezandipiti = None
try:
    import hops_snorlax_rules as _hops_snorlax   # Hop's Snorlax single-prize toolbox aggro/control specialist
except Exception:
    try:
        from agent import hops_snorlax_rules as _hops_snorlax
    except Exception:
        _hops_snorlax = None
try:
    from lethal import lethal_move as _lethal_move
except Exception:
    try:
        from agent.lethal import lethal_move as _lethal_move
    except Exception:
        _lethal_move = None

# ── static engine tables (loaded once) ───────────────────────────────────────
_CARD = {c.cardId: c for c in all_card_data()}
_ATK = {a.attackId: a for a in all_attack()}

# Draw / dig supporters: firing them develops the hand and is high priority. Detected by name
# keyword so this generalises beyond one decklist (Lillie/Hilda/Carmine/Iono/Professor… style).
_DRAW_WORDS = ("draw", "shuffle your hand", "search your deck", "look at the top")
# Heal cards: only worth playing when something is actually damaged.
_HEAL_WORDS = ("heal",)


def _card_data(card):
    return _CARD.get(getattr(card, "id", None))


def _is_draw_supporter(data) -> bool:
    if data is None or data.cardType != CardType.SUPPORTER:
        return False
    txt = " ".join((s.text or "").lower() for s in (data.skills or []))
    return any(w in txt for w in _DRAW_WORDS)


def _is_heal_card(data) -> bool:
    if data is None:
        return False
    txt = (data.name or "").lower() + " " + " ".join((s.text or "").lower() for s in (data.skills or []))
    return any(w in txt for w in _HEAL_WORDS)


# ── card valuation primitives (from the ≈950 scorer) ──────────────────────────
def prize_count(pokemon) -> int:
    """Prizes the opponent takes for KOing this Pokémon."""
    data = _card_data(pokemon)
    if data is None:
        return 1
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in getattr(pokemon, "energyCards", None) or []:
        if card.id == 12:  # Legacy Energy: -1 prize when KO'd
            count -= 1
    return max(0, count)


def pokemon_score(pokemon) -> float:
    """Standalone value of a Pokémon in play (higher = more valuable target / keep)."""
    data = _card_data(pokemon)
    score = prize_count(pokemon) * 1000.0
    score += len(getattr(pokemon, "energyCards", None) or []) * 150.0
    score += len(getattr(pokemon, "tools", None) or []) * 100.0
    if data is not None:
        if data.stage2:
            score += 250.0
        elif data.stage1:
            score += 130.0
    score += getattr(pokemon, "hp", 0) or 0
    return score


# ── zone resolution ───────────────────────────────────────────────────────────
def _get(obs, area, index, player_index):
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


def _attack_damage(attacker, attack_id, defender) -> int:
    atk = _ATK.get(attack_id)
    if atk is None:
        return 0
    dmg = atk.damage or 0
    if dmg <= 0:
        return 0
    adata = _card_data(attacker)
    ddata = _card_data(defender)
    if adata is not None and ddata is not None:
        atype = adata.energyType
        if ddata.weakness is not None and ddata.weakness == atype:
            dmg *= 2
        elif ddata.resistance is not None and ddata.resistance == atype:
            dmg = max(0, dmg - 30)
    return dmg


# ── fallback ─────────────────────────────────────────────────────────────────
def _fallback(select) -> list[int]:
    try:
        n = len(select.option)
        if n == 0 or select.maxCount <= 0:
            return []
        lo = max(select.minCount, 1)
        return list(range(min(lo, select.maxCount, n)))
    except Exception:
        return [0]


def _fallback_from_dict(obs_dict) -> list[int]:
    try:
        sel = (obs_dict or {}).get("select") or {}
        n = len(sel.get("option") or [])
        if n == 0:
            return []
        maxc = sel.get("maxCount", 1) or 1
        if maxc <= 0:
            return []
        lo = max(sel.get("minCount", 0) or 0, 1)
        return list(range(min(lo, maxc, n)))
    except Exception:
        return [0]


# ── MAIN-turn scoring (priority ordering: setup before attack) ────────────────
def _score_main(obs, o, me, opp, me_i):
    t = o.type

    if t == OptionType.ATTACH:
        score = 1000.0
        pk = _get(obs, getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), me_i)
        if isinstance(pk, Pokemon):
            data = _card_data(pk)
            if getattr(o, "inPlayArea", None) == AreaType.ACTIVE:
                score += 60.0  # concentrate energy on the active (intended attacker)
            elif data is not None and (data.stage1 or data.stage2):
                score += 30.0  # else fuel an evolved bench threat
        return score

    if t == OptionType.EVOLVE:
        return 800.0

    if t == OptionType.PLAY:
        card = _get(obs, AreaType.HAND, o.index, me_i)
        data = _card_data(card)
        if data is None:
            return 600.0
        if data.cardType == CardType.POKEMON:
            if data.basic:
                bench_used = len([p for p in me.bench if p is not None])
                if bench_used == 0:
                    return 1700.0  # bench a basic onto an EMPTY bench: board survival, critical
            return 600.0
        if _is_heal_card(data):
            damaged = any(
                p is not None and (p.maxHp or 0) > (p.hp or 0)
                for p in ([me.active[0] if me.active else None] + list(me.bench))
            )
            return 900.0 if damaged else -2.0  # heal only with a damaged mon, else below END
        if _is_draw_supporter(data):
            return -1.0 if obs.current.supporterPlayed else 1400.0
        if data.cardType == CardType.SUPPORTER:
            return -1.0 if obs.current.supporterPlayed else 700.0
        if data.cardType == CardType.STADIUM:
            return -1.0 if obs.current.stadiumPlayed else 500.0
        return 600.0  # items / tools — develop

    if t == OptionType.ABILITY:
        return 400.0

    if t == OptionType.ATTACK:
        oa = opp.active[0] if opp.active else None
        if oa is None:
            return 100.0
        dmg = _attack_damage(me.active[0] if me.active else None, o.attackId, oa)
        score = 100.0 + min(dmg, 250) * 0.2
        if dmg >= (oa.hp or 0) and dmg > 0:
            score += 150.0  # lethal KO
            if len(opp.prize) <= prize_count(oa):
                return 50000.0  # this KO takes their last prize(s): game-winning
        return score

    if t == OptionType.RETREAT:
        return -1.0
    if t == OptionType.END:
        return 0.0
    if t == OptionType.YES:
        return 5.0
    if t == OptionType.NO:
        return 3.0
    return 1.0


# ── sub-selection scoring (context != MAIN) ───────────────────────────────────
def _score_sub(obs, o, ctx, me, opp, me_i, opp_i):
    score = 2000.0  # base: always make a legal move
    t = o.type

    if t == OptionType.NUMBER:
        return score + (o.number or 0)  # take the bigger number
    if t == OptionType.YES:
        if ctx == SelectContext.IS_FIRST:
            return score + 150.0  # TAKE the first turn — see the NO branch for the evidence
        return score + 100.0
    if t == OptionType.NO:
        if ctx == SelectContext.IS_FIRST:
            # This branch used to add +100 ("for a setup/reactive deck, going second is often
            # better"). That rule was never measured and it is wrong for the entire field, not
            # just for one archetype:
            #   * 2026-08-08 ladder dump, 1,400 episodes, 305 IS_FIRST answers across 25
            #     archetypes: YES 99.0% overall and 100% in every one of the 9 archetypes with
            #     >=8 samples (tools/first_turn_field.py).
            #   * Of those same 305 asked seats, the seat that ended up going first won 54.4%.
            #   * Causal, in-engine: tools/first_turn_ab.py, 2,200 mirror games with identical
            #     decks and identical policy on both seats and ONLY the turn-order answer forced,
            #     arm- and seat-swapped — the player who went first won 54.0% +/- 2.1 (p~0.0002).
            # It mattered because specialist dispatch is keyed on cards VISIBLE on our side, and
            # IS_FIRST is asked before the opening hand exists, so this generic default decided
            # the opening tempo of every game we ever played. The archetype specialists now carry
            # a deck.csv fallback for that frame; fixing the default too means a specialist that
            # fails to load, or a list we have not written one for, no longer concedes the turn.
            return score
        return score
    if t == OptionType.SPECIAL_CONDITION:
        return score

    # Card-target selections.
    card = None
    if t in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD, OptionType.ENERGY):
        card = _get(obs, o.area, o.index, getattr(o, "playerIndex", me_i))
    data = _card_data(card)

    # Heal / damage-removal: prefer the most-damaged friendly mon.
    if ctx in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        if isinstance(card, Pokemon):
            score += (card.maxHp or 0) - (card.hp or 0)
        return score

    # Placing damage / dealing damage: hit the opponent's most valuable mon, prefer active.
    if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
               SelectContext.DAMAGE_COUNTER_ANY, SelectContext.EFFECT_TARGET):
        if isinstance(card, Pokemon) and getattr(o, "playerIndex", me_i) == opp_i:
            score += pokemon_score(card)
            if o.area == AreaType.ACTIVE:
                score += 300.0
        elif isinstance(card, Pokemon):
            score -= pokemon_score(card)  # don't damage our own
        return score

    # Discard: dump spare basic energy first; protect our evolution line & tools.
    if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
               SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM):
        if data is not None:
            if data.cardType == CardType.BASIC_ENERGY:
                return score + 60.0  # spare basic energy is the cheapest pitch
            if data.cardType in (CardType.POKEMON, CardType.SPECIAL_ENERGY, CardType.TOOL):
                return score - 200.0  # protect key pieces
        return score

    # Generic target selection: opponent's Pokémon (boss/gust/switch targets).
    if isinstance(card, Pokemon):
        if getattr(o, "playerIndex", me_i) == opp_i:
            score += pokemon_score(card)
            if o.area == AreaType.ACTIVE:
                score += 200.0
        else:
            # Selecting our own mon (setup active, switch-in, evolve placement): value it.
            score += pokemon_score(card) * 0.25
            if ctx in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH,
                       SelectContext.EVOLVES_FROM, SelectContext.EVOLVES_TO):
                score += 500.0
        return score

    return score


# ── entry point ───────────────────────────────────────────────────────────────
def best_options(obs_dict) -> list[int]:
    """Score every option in obs.select and return a legal selection (min..maxCount)."""
    try:
        obs = to_observation_class(obs_dict)
        select = obs.select
        if select is None:
            return _fallback_from_dict(obs_dict)
        n = len(select.option)
        if n == 0 or select.maxCount <= 0:
            return []

        state = obs.current
        me_i = state.yourIndex
        opp_i = 1 - me_i
        me = state.players[me_i]
        opp = state.players[opp_i]
        ctx = select.context

        # Marnie's Grimmsnarl ex specialist: checked FIRST because its list plays cards that other
        # gates key on (Hero's Cape 1159 -> cinderace; Fezandipiti 140 / Lillie 1227 / Xerosic 1197
        # -> fezandipiti; Dunsparce 305/66 -> dunsparce). Its own signature (Marnie's line 646/647/
        # 648, Spikemuth 1259, Risky Ruins 1260) is unique to this list and LATCHES per game, so
        # when we pilot any other deck this never fires and every other path is untouched.
        grimmsnarl = False
        if _grimmsnarl is not None:
            try:
                grimmsnarl = _grimmsnarl.is_grimmsnarl_deck(state, me_i)
                if grimmsnarl:
                    _grimmsnarl.note_obs(obs, obs_dict, me_i)
            except Exception:
                grimmsnarl = False

        # Great Tusk mill-box specialist (alancai27's stable-894 list): checked BEFORE the crustle
        # specialist because this list CONTAINS Dwebble 344 / Crustle 345 (the crustle signature)
        # and before cinderace (it plays Ultra Ball 1121, part of that gate). Its own gate keys on
        # list-unique cards (Great Tusk 58 / Terrakion 607 / Lisia 1204, or the 344/345 line PLUS
        # a tusk-only trainer) and LATCHES per seat, so no other deck routes through it.
        tusk = False
        if not grimmsnarl and _tusk is not None:
            try:
                tusk = _tusk.is_tusk_deck(state, me_i)
                if tusk:
                    _tusk.note_obs(obs, obs_dict, me_i)
            except Exception:
                tusk = False

        # Crustle wall specialist: when we're piloting the wall, use its card-id-gated scoring
        # (and a verified multi-step lethal check) instead of the generic table. For every other
        # deck this never triggers (no Dwebble/Crustle on our side), so the generic path is intact.
        crustle = False
        if not grimmsnarl and not tusk and _crustle is not None:
            try:
                crustle = _crustle.is_crustle_deck(state, me_i)
            except Exception:
                crustle = False

        # Mega Lucario ex aggro specialist: only consulted when we pilot the Lucario line (and the
        # Crustle wall is NOT on our side, so the two id-gated paths never overlap). Generic +
        # Crustle paths are untouched for every other deck.
        lucario = False
        if not grimmsnarl and not tusk and not crustle and _lucario is not None:
            try:
                lucario = _lucario.is_lucario_deck(state, me_i)
            except Exception:
                lucario = False

        # keidroid #1 Cinderace + Mega Starmie ex / Crushing Hammer specialist: checked BEFORE the
        # Starmie/Froslass specialist because this list SHARES the Staryu/Mega Starmie line, so its
        # gate is the disjoint subset (Cinderace/Crushing Hammer/Harlequin/Ultra Ball/Hero's Cape) and
        # the starmie gate below is suppressed when it fires — the two never both pilot the same deck.
        cinderace = False
        if not grimmsnarl and not tusk and not crustle and not lucario and _cinderace is not None:
            try:
                cinderace = _cinderace.is_cinderace_deck(state, me_i)
                if cinderace:
                    _cinderace.note_obs(obs, obs_dict, me_i)
            except Exception:
                cinderace = False

        # Mega Starmie / Mega Froslass ex prize-race specialist: only when we pilot the Starmie line
        # (signatures disjoint from Crustle/Lucario, so the id-gated paths never overlap). It keeps a
        # per-game prize tracker so its deck-search decisions never whiff on a prized card.
        starmie = False
        if not grimmsnarl and not tusk and not crustle and not lucario and not cinderace and _starmie is not None:
            try:
                starmie = _starmie.is_starmie_deck(state, me_i)
                if starmie:
                    _starmie.note_obs(obs, obs_dict, me_i)
            except Exception:
                starmie = False

        # Fezandipiti ex / Alakazam "Powerful Hand" combo specialist: the THIRD-place PTCG-Club list,
        # the same Powerful Hand engine as the dunsparce list but with a Fezandipiti ex / Lillie's
        # Determination / Wondrous Patch / Xerosic tech package. It SHARES the Alakazam core with the
        # dunsparce list, so it is checked FIRST (its gate also requires a list-unique card) and the
        # dunsparce gate below is suppressed when it fires — the two never both pilot the same deck.
        fezandipiti = False
        if (not grimmsnarl and not tusk and not crustle and not lucario and not cinderace and not starmie
                and _fezandipiti is not None):
            try:
                fezandipiti = _fezandipiti.is_fezandipiti_deck(state, me_i)
            except Exception:
                fezandipiti = False

        # Alakazam "Powerful Hand" / Dudunsparce draw-combo specialist: only when we pilot that line
        # (signature disjoint from Crustle/Lucario/Starmie, so the id-gated paths never overlap). It
        # is the one deck that breaks the Crustle wall (Powerful Hand is non-ex damage counters).
        dunsparce = False
        if (not grimmsnarl and not tusk and not crustle and not lucario and not cinderace and not starmie
                and not fezandipiti and _dunsparce is not None):
            try:
                dunsparce = _dunsparce.is_dunsparce_deck(state, me_i)
            except Exception:
                dunsparce = False

        # Iono's Bellibolt ex Lightning energy-stacking specialist: only when we pilot the Iono line
        # (signature disjoint from Crustle/Lucario/Starmie/Dunsparce, so the id-gated paths never
        # overlap). This is the empirically strongest archetype on the board (it beats all four of our
        # other decks as an opponent), piloted here on our own side.
        iono = False
        if (not grimmsnarl and not tusk and not crustle and not lucario and not cinderace and not starmie
                and not dunsparce and not fezandipiti and _iono is not None):
            try:
                iono = _iono.is_iono_deck(state, me_i)
            except Exception:
                iono = False

        # Hop's Snorlax single-prize toolbox aggro/control specialist: only when we pilot the Hop's
        # line (signature 304/311/878/879 disjoint from every other specialist, so the id-gated paths
        # never overlap). This is the #2 frontier team's deck ("The Debauchery Tea Party", ~1358 Elo).
        hops_snorlax = False
        if (not grimmsnarl and not tusk and not crustle and not lucario and not cinderace and not starmie
                and not dunsparce and not fezandipiti and not iono and _hops_snorlax is not None):
            try:
                hops_snorlax = _hops_snorlax.is_hops_snorlax_deck(state, me_i)
            except Exception:
                hops_snorlax = False

        # Specialist guard FIRST so it short-circuits before touching SelectContext.MAIN (which the
        # mock test engine does not define): when no specialist is active this whole gate is skipped.
        if (grimmsnarl or tusk or crustle or lucario or cinderace or starmie or dunsparce or iono or fezandipiti or hops_snorlax) and _lethal_move is not None and ctx == SelectContext.MAIN:
            try:
                if grimmsnarl:
                    deck = _grimmsnarl.GRIMMSNARL_DECK
                elif tusk:
                    deck = _tusk.TUSK_DECK
                elif crustle:
                    deck = _crustle.CRUSTLE_DECK
                elif lucario:
                    deck = _lucario.LUCARIO_DECK
                elif cinderace:
                    deck = _cinderace.CINDERACE_DECK
                elif starmie:
                    deck = _starmie.STARMIE_DECK
                elif dunsparce:
                    deck = _dunsparce.DUNSPARCE_DECK
                elif fezandipiti:
                    deck = _fezandipiti.FEZANDIPITI_DECK
                elif iono:
                    deck = _iono.IONO_DECK
                else:
                    deck = _hops_snorlax.HOPS_SNORLAX_DECK
                # Feed the verifier our known-prized cards so it never plans a lethal that relies
                # on a card sitting in the prize zone (the top-3 team's stated core technique).
                prized_counter = None
                if starmie:
                    try:
                        prized_counter = _starmie._prized()
                    except Exception:
                        prized_counter = None
                elif grimmsnarl:
                    try:
                        prized_counter = _grimmsnarl._prized(me_i)
                    except Exception:
                        prized_counter = None
                lm = _lethal_move(obs_dict, deck, prized_counter)
                if isinstance(lm, list) and lm:
                    return lm
            except Exception:
                pass

        scores = []
        for o in select.option:
            try:
                if grimmsnarl:
                    if ctx == SelectContext.MAIN:
                        scores.append(_grimmsnarl.score_main(obs, o, me_i))
                    else:
                        scores.append(_grimmsnarl.score_sub(obs, o, me_i, ctx))
                elif tusk:
                    if ctx == SelectContext.MAIN:
                        scores.append(_tusk.score_main(obs, o, me_i))
                    else:
                        scores.append(_tusk.score_sub(obs, o, me_i, ctx))
                elif crustle:
                    if ctx == SelectContext.MAIN:
                        scores.append(_crustle.score_main(obs, o, me_i))
                    else:
                        scores.append(_crustle.score_sub(obs, o, me_i, ctx))
                elif lucario:
                    if ctx == SelectContext.MAIN:
                        scores.append(_lucario.score_main(obs, o, me_i))
                    else:
                        scores.append(_lucario.score_sub(obs, o, me_i, ctx))
                elif cinderace:
                    if ctx == SelectContext.MAIN:
                        scores.append(_cinderace.score_main(obs, o, me_i))
                    else:
                        scores.append(_cinderace.score_sub(obs, o, me_i, ctx))
                elif starmie:
                    if ctx == SelectContext.MAIN:
                        scores.append(_starmie.score_main(obs, o, me_i))
                    else:
                        scores.append(_starmie.score_sub(obs, o, me_i, ctx))
                elif dunsparce:
                    if ctx == SelectContext.MAIN:
                        scores.append(_dunsparce.score_main(obs, o, me_i))
                    else:
                        scores.append(_dunsparce.score_sub(obs, o, me_i, ctx))
                elif iono:
                    if ctx == SelectContext.MAIN:
                        scores.append(_iono.score_main(obs, o, me_i))
                    else:
                        scores.append(_iono.score_sub(obs, o, me_i, ctx))
                elif fezandipiti:
                    if ctx == SelectContext.MAIN:
                        scores.append(_fezandipiti.score_main(obs, o, me_i))
                    else:
                        scores.append(_fezandipiti.score_sub(obs, o, me_i, ctx))
                elif hops_snorlax:
                    if ctx == SelectContext.MAIN:
                        scores.append(_hops_snorlax.score_main(obs, o, me_i))
                    else:
                        scores.append(_hops_snorlax.score_sub(obs, o, me_i, ctx))
                elif ctx == SelectContext.MAIN:
                    scores.append(_score_main(obs, o, me, opp, me_i))
                else:
                    scores.append(_score_sub(obs, o, ctx, me, opp, me_i, opp_i))
            except Exception:
                scores.append(0.0)

        ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)

        # Honour min/maxCount: take positively-scored options in rank order, always fill minCount.
        minc = max(0, min(select.minCount, n))
        maxc = max(minc, min(select.maxCount, n))
        out = []
        for i in ranked:
            if scores[i] > 0 or len(out) < minc:
                out.append(i)
            if len(out) >= maxc:
                break
        for i in range(n):  # safety fill to minCount
            if len(out) >= minc:
                break
            if i not in out:
                out.append(i)
        if not out:
            return _fallback(select)
        return out[:maxc]
    except Exception:
        return _fallback_from_dict(obs_dict)

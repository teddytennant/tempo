"""Multi-step lethal verifier over the engine's native search tree.

`lethal_move(obs_dict, decklist) -> list[int] | None`

From the current MAIN decision, search whether THIS TURN there is a verified sequence of
actions (attach energy, evolve, use an ability, then attack — in any legal order) that takes
the opponent's last prize(s) / wins the game. If a winning first-action exists, return the
selection to play it (indices into the *current* obs.select.option); otherwise return None.

It uses the persistent search tree (`search_begin` / `search_step` / `search_release` /
`search_end`): each `search_step(parent_id, sel)` yields a fresh child state, so a node can be
re-expanded with different selections (verified by tools/search_probe.py). The whole thing is
hard-guarded: on ANY error, or if the native search API is unavailable (mock engine / Kaggle
sandbox without the symbols), it returns None so the caller falls back to its normal policy.

The search is strictly bounded (node budget + depth budget) so it can never blow the move clock.
It only runs when a win this turn is *plausible* (an attack is offered and the opponent is at
<= PRIZE_GATE prizes), which also keeps it cheap on the turns where it cannot matter.
"""
from __future__ import annotations

import time as _time

try:
    from cg.api import (
        AreaType, OptionType, SelectContext,
        search_begin, search_step, search_release, search_end, to_observation_class,
    )
    _HAVE_SEARCH = True
except Exception:  # mock engine / missing native symbols
    _HAVE_SEARCH = False

# Belief-corrected determinization: places known-prized cards in the prize slot (not the draw
# pile) and never lets the search "draw" a card that is really prized — the top-3 team's stated
# core technique ("a search that uses a prized card finds an impossible line = NOMATCH"). Optional;
# on any import/runtime failure we fall back to the old (overlapping) pool slice below.
try:
    from belief import corrected_deck as _corrected_deck
except Exception:
    try:
        from agent.belief import corrected_deck as _corrected_deck
    except Exception:
        _corrected_deck = None

# Plausibility gate: only bother verifying lethal when the opponent has at most this many prizes
# left. A single knockout yields at most THREE prizes (a Mega ex), so 3 — not 2 — is the largest
# prize count from which one KO can end the game. Measured on 2,500 real ladder MAIN decisions
# (tools/lethal_probe.py): raising 2 -> 3 finds 23 game-winning lines the gate used to hide, at
# no measurable latency cost (p99 140.6 -> 144.1 ms). The gate is a pure cost filter — it cannot
# create a false positive, because a positive is an engine-declared terminal win either way.
PRIZE_GATE = 3
# Require an ATTACK to already be on the root menu before searching? Shipped as False since
# 2026-08-10 — see the comment at the gate in lethal_move().
REQUIRE_ATTACK_OPTION = False
# Hard search caps — keep it well under the move clock even in pathological positions.
_MAX_DEPTH = 10       # selections deep into the turn (attach/evolve/ability/attack + sub-selects)
_NODE_BUDGET = 600    # total search_step calls per verification
# Wall-clock deadline: the node budget alone let branchy endgames spend >1s of engine search_step
# time (fuzz observed 1.26s). A hard time cap guarantees the verifier returns well under the
# per-move clock no matter how expensive each engine step is — it just bails and the caller uses
# its normal policy (which is already lethal-aware via scoring, so we lose nothing but the proof).
_MAX_TIME_S = 0.25


def _opp_prize_count(state, me_i: int) -> int:
    try:
        return len(state.players[1 - me_i].prize)
    except Exception:
        return 99


def _opp_bench_count(state, me_i: int) -> int:
    try:
        return len([b for b in state.players[1 - me_i].bench if b is not None])
    except Exception:
        return 99


def _win_plausible(state, me_i: int) -> bool:
    """A win THIS turn is conceivable when either the opponent is at their last prize(s), or they
    have no benched Pokémon (so a KO of their Active leaves them with "no Active Pokémon" = a loss
    for them, reason 3). Outside these cases an attack cannot end the game, so we skip the search."""
    return _opp_prize_count(state, me_i) <= PRIZE_GATE or _opp_bench_count(state, me_i) == 0


def _has_attack_option(select) -> bool:
    try:
        return any(o.type == OptionType.ATTACK for o in select.option)
    except Exception:
        return False


def _terminal_win(state, me_i: int):
    """Return True (we won), False (we lost/drew), or None (not terminal)."""
    try:
        r = getattr(state, "result", -1)
    except Exception:
        r = -1
    if r is None or r == -1:
        return None
    return r == me_i


def _order_options(select, me_i: int):
    """Try the most lethal-relevant options first: attacks, then ability/evolve/attach, then the
    rest; END last (ending the turn can only *fail* to be lethal)."""
    opts = select.option

    def key(i):
        t = opts[i].type
        if t == OptionType.ATTACK:
            return 0
        if t == OptionType.ABILITY:
            return 1
        if t == OptionType.EVOLVE:
            return 2
        if t == OptionType.ATTACH:
            return 3
        if t == OptionType.END:
            return 9
        return 5

    return sorted(range(len(opts)), key=key)


def _selection_for(select, idx: int):
    """A legal selection that includes option `idx`, honouring min/maxCount. For the common
    single-select case this is just [idx]; for multi-select we pad with other low indices."""
    n = len(select.option)
    minc = max(0, min(getattr(select, "minCount", 0) or 0, n))
    maxc = max(minc, min(getattr(select, "maxCount", 1) or 1, n))
    sel = [idx]
    if len(sel) < minc:
        for j in range(n):
            if j != idx:
                sel.append(j)
            if len(sel) >= minc:
                break
    return sel[:maxc]


class _Budget:
    __slots__ = ("steps", "deadline")

    def __init__(self):
        self.steps = 0
        self.deadline = _time.monotonic() + _MAX_TIME_S

    def exhausted(self) -> bool:
        return self.steps >= _NODE_BUDGET or _time.monotonic() >= self.deadline


def _dfs(search_id, obs, me_i: int, depth: int, budget: _Budget) -> bool:
    """Depth-first: from this search node, is there a line (still on our turn) that wins?"""
    state = obs.current
    if state is None:
        return False
    term = _terminal_win(state, me_i)
    if term is True:
        return True
    if term is False:
        return False
    # Control passed to the opponent without winning -> this line is not lethal this turn.
    if getattr(state, "yourIndex", me_i) != me_i:
        return False
    if depth >= _MAX_DEPTH:
        return False
    select = obs.select
    if select is None or not select.option:
        return False

    is_main = getattr(select, "context", None) == SelectContext.MAIN

    for idx in _order_options(select, me_i):
        if budget.exhausted():
            return False
        # On the MAIN menu, never explore END for lethal (it just ends the turn).
        if is_main and select.option[idx].type == OptionType.END:
            continue
        sel = _selection_for(select, idx)
        try:
            budget.steps += 1
            child = search_step(search_id, sel)
        except Exception:
            continue
        try:
            if _dfs(child.searchId, child.observation, me_i, depth + 1, budget):
                return True
        finally:
            try:
                search_release(child.searchId)
            except Exception:
                pass
    return False


def lethal_move(obs_dict, decklist, prized_counter=None) -> list[int] | None:
    """If a verified game-winning sequence exists from the current MAIN decision, return the
    selection that plays its first action; otherwise None. Never raises.

    `prized_counter` (a collections.Counter of card_id->count from PrizeTracker.prized_cards(), or
    None) lets the determinization seat our known-prized cards in the prize zone instead of the
    draw pile, so a verified lethal can never rely on a card that is actually prized."""
    if not _HAVE_SEARCH:
        return None
    try:
        obs = to_observation_class(obs_dict)
    except Exception:
        return None
    try:
        select = obs.select
        state = obs.current
        if select is None or state is None:
            return None
        if getattr(select, "context", None) != SelectContext.MAIN:
            return None
        if getattr(obs, "search_begin_input", None) is None:
            return None  # not a real-engine agent observation -> cannot search
        me_i = state.yourIndex

        # Cheap plausibility gate: only verify when a win this turn is conceivable.
        #
        # NOTE: this used to also require `_has_attack_option(select)` — an ATTACK already on the
        # root menu. That was the single largest hole in the verifier's coverage: the whole point of
        # searching is to find lines that *enable* an attack (attach the energy, evolve, use the
        # ability, then swing), and those start from a menu with no attack on it. Over 2,500 real
        # ladder MAIN decisions the requirement hid 28 game-winning lines, and in 6 of them the
        # heuristic went on to play a PLAY/ATTACH that made the win no longer provable
        # (tools/lethal_cost.py). Dropping it cost nothing measurable: p99 latency 140.6 -> 144.1 ms.
        # The flag is kept so tools/lethal_probe.py can still A/B the axis on any tree.
        if REQUIRE_ATTACK_OPTION and not _has_attack_option(select):
            return None
        if not _win_plausible(state, me_i):
            return None

        me = state.players[me_i]
        opp = state.players[1 - me_i]
        prize_n = max(len(me.prize), 1)
        deck_n = max(me.deckCount, 1)
        # Belief-corrected, NON-OVERLAPPING determinization: corrected_deck() returns the unseen
        # pool ordered [prized..., deck...]; we seat the front prize_n as prizes and the next
        # deck_n as the draw pile (matching engine_rs' non-overlapping slice contract). The old
        # path sliced your_deck and your_prize from the same front of pool (overlapping) AND could
        # place a prized card in the searchable deck — both fixed here.
        your_deck = None
        your_prize = None
        if _corrected_deck is not None:
            try:
                ordered = _corrected_deck(obs, list(decklist), prized_counter)
                if ordered and len(ordered) >= prize_n:
                    your_prize = ordered[:prize_n]
                    your_deck = ordered[prize_n: prize_n + deck_n]
            except Exception:
                your_deck = None
        if not your_deck:  # fallback: original behavior (never make it worse than before)
            pool = (list(decklist) * 2) if decklist else [1]
            your_deck = pool[:deck_n]
            your_prize = pool[:prize_n]
        if not your_prize:
            your_prize = (list(decklist) or [1])[:prize_n]
        opp_n = max(opp.deckCount, 1)
        opponent_deck = [1072] * opp_n          # placeholder basic (Snorlax) — hidden info
        opponent_prize = [1072] * max(len(opp.prize), 1)
        opponent_hand = [1072] * max(opp.handCount, 0) if opp.handCount else []
        opponent_active = []
        if opp.active and opp.active[0] is None:
            opponent_active = [1072]
    except Exception:
        return None

    root = None
    try:
        root = search_begin(obs, your_deck, your_prize,
                            opponent_deck, opponent_prize, opponent_hand, opponent_active)
        root_obs = root.observation
        root_select = root_obs.select
        if root_select is None or not root_select.option:
            return None
        budget = _Budget()
        for idx in _order_options(root_select, me_i):
            if root_select.option[idx].type == OptionType.END:
                continue
            if budget.exhausted():
                break
            sel = _selection_for(root_select, idx)
            try:
                budget.steps += 1
                child = search_step(root.searchId, sel)
            except Exception:
                continue
            try:
                if _dfs(child.searchId, child.observation, me_i, 1, budget):
                    # `idx` indexes root_select.option, which mirrors the live obs.select.option.
                    # Guard the assumption: only return it if it's a legal index for the LIVE select
                    # (else fall through to None so the caller's normal policy stays legal).
                    if 0 <= idx < len(select.option):
                        return _selection_for(select, idx)
                    return None
            finally:
                try:
                    search_release(child.searchId)
                except Exception:
                    pass
        return None
    except Exception:
        return None
    finally:
        try:
            if root is not None:
                search_release(root.searchId)
        except Exception:
            pass
        try:
            search_end()
        except Exception:
            pass

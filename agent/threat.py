"""Verified OPPONENT-lethal — does the move we are about to make hand them the game?

`threat_alternative(obs_dict, decklist, prized_counter, chosen) -> list[int] | None`

`agent/lethal.py` proves "I win THIS turn". This is the same machine with the polarity flipped:
from the MAIN decision where the scorer wants to end our turn (an ATTACK or an END), fork the game,
apply that move, and ask whether the OPPONENT can then provably win on their next turn. If they can,
try the other turn-ending options and return the first one that they provably cannot win against.

Why this is a legitimate search when four refutations of search are on file (RESEARCH.md): every one
of those refuted a *heuristic-eval* search replacing the scorer's ranking. Here, as in lethal.py, the
leaf value is `state.result` — an engine-declared terminal — so the "static board value is weaker
than the scorer's implicit tempo knowledge" mechanism cannot apply.

SOUNDNESS. The fork seats the opponent's hand and deck as placeholder basics (search_begin takes no
real opponent list — their hand is hidden). So inside the search they can attach energy, retreat, use
the abilities of Pokemon already in play and attack, but they cannot play a trainer, a supporter or
a gust. That is a strict SUBSET of what they can really do, which means:

  * a proven loss here is a real line they really have (up to the energy-zone caveat below), and
  * we will MISS threats that need a card from their hand.

The error is one-sided and in the safe direction: this fires rarely and never on a fantasy.
(Caveat: their energy zone is derived from the placeholder deck, so an attack whose cost is not
already paid by attached energy may be unpayable in the fork. That makes it miss more, not invent.)

AND/OR, so "they win" means they win against anything we do. Nodes where the OPPONENT selects are OR
nodes (any option that wins for them proves the loss); nodes where WE select — promoting a new Active
after a knockout, say — are AND nodes (every option of ours must still lose). Budget exhaustion at
either kind returns "not proven", so every form of doubt resolves to silence.

PRIOR PROTECTION, exactly as in lethal.py: this never speaks unless it can prove BOTH that the
scorer's move loses AND that a specific alternative does not. No score margin, no heuristic
comparison — two proofs or nothing.
"""
from __future__ import annotations

import time as _time

try:
    from cg.api import (
        OptionType, SelectContext,
        search_begin, search_step, search_release, search_end, to_observation_class,
    )
    _HAVE_SEARCH = True
except Exception:  # mock engine / missing native symbols
    _HAVE_SEARCH = False

try:
    from belief import corrected_deck as _corrected_deck
except Exception:
    try:
        from agent.belief import corrected_deck as _corrected_deck
    except Exception:
        _corrected_deck = None

# Only look when the opponent could actually close the game next turn: they are within one
# knockout's worth of prizes (a Mega ex is 3), or our Active is our last Pokemon so a knockout ends
# it outright. Outside that, losing the exchange is a tempo question, not a terminal one, and the
# whole prize-trade angle is on file as measured-settled at the tempo level.
OPP_PRIZE_GATE = 3
_MAX_DEPTH = 10
_NODE_BUDGET = 1600      # shared across the chosen move AND every alternative
_MAX_TIME_S = 0.35
_MAX_ALTERNATIVES = 4    # how many other turn-enders to try before giving up
# Falsification switch (tools/threat_probe.py --no-opp-attach). The opponent's deck and hand are
# placeholders in the fork, so their energy zone is derived from a list that is not theirs. Turning
# this off forbids the opponent to ATTACH inside the search, leaving them only the energy already on
# their board — any proof that survives cannot be an artifact of a mis-modelled energy zone.
OPP_MAY_ATTACH = True

_TURN_ENDERS = None       # filled lazily; OptionType is unavailable under the mock engine


def _turn_enders():
    global _TURN_ENDERS
    if _TURN_ENDERS is None:
        _TURN_ENDERS = (OptionType.ATTACK, OptionType.END)
    return _TURN_ENDERS


class _Budget:
    __slots__ = ("steps", "deadline")

    def __init__(self):
        self.steps = 0
        self.deadline = _time.monotonic() + _MAX_TIME_S

    def exhausted(self) -> bool:
        return self.steps >= _NODE_BUDGET or _time.monotonic() >= self.deadline


def _selection_for(select, idx: int):
    """A legal selection that includes option `idx`, honouring min/maxCount."""
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


def _order_opponent_options(select):
    """Their most game-ending options first: attack, then ability/attach/retreat, END last."""
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
        if t == OptionType.RETREAT:
            return 4
        if t == OptionType.END:
            return 9
        return 5

    return sorted(range(len(opts)), key=key)


def _they_win(search_id, obs, me_i: int, end_turn: int, depth: int, budget: _Budget) -> bool:
    """Can the opponent provably win at or below this node, before turn `end_turn` is over?

    OR over their selections, AND over ours. Anything unproven — depth, budget, an engine error,
    the turn rolling past theirs — is False.
    """
    state = obs.current
    if state is None:
        return False
    r = getattr(state, "result", -1)
    if r is not None and r != -1:
        return r == (1 - me_i)
    # Their turn is over and the game is still going: they did not win it.
    if (getattr(state, "turn", 0) or 0) > end_turn:
        return False
    if depth >= _MAX_DEPTH or budget.exhausted():
        return False
    select = obs.select
    if select is None or not select.option:
        return False

    ours = getattr(state, "yourIndex", me_i) == me_i
    # AND node (ours): a loss is only proven if EVERY reply of ours still loses, so a branch we
    # cannot expand — budget, depth, an engine error — collapses the whole node to "not proven".
    order = range(len(select.option)) if ours else _order_opponent_options(select)
    if not ours and not OPP_MAY_ATTACH:
        order = [i for i in order if select.option[i].type != OptionType.ATTACH]

    for idx in order:
        if budget.exhausted():
            return False
        sel = _selection_for(select, idx)
        try:
            budget.steps += 1
            child = search_step(search_id, sel)
        except Exception:
            if ours:
                return False
            continue
        try:
            won = _they_win(child.searchId, child.observation, me_i, end_turn, depth + 1, budget)
        except Exception:
            won = False
        finally:
            try:
                search_release(child.searchId)
            except Exception:
                pass
        if ours and not won:
            return False          # we have a survivor -> not proven
        if not ours and won:
            return True           # they have a winning line
    return bool(ours)             # AND: every branch lost. OR: nothing won.


def _loses_after(root_id, root_select, selection, me_i: int, end_turn: int, budget: _Budget):
    """Apply `selection` at the fork root and ask whether the opponent then provably wins.

    Returns True / False, or None when the move could not be evaluated at all."""
    n = len(root_select.option)
    sel = [i for i in selection if isinstance(i, int) and 0 <= i < n]
    if not sel or len(sel) != len(selection):
        return None
    child = None
    try:
        budget.steps += 1
        child = search_step(root_id, sel)
        return bool(_they_win(child.searchId, child.observation, me_i, end_turn, 1, budget))
    except Exception:
        return None
    finally:
        if child is not None:
            try:
                search_release(child.searchId)
            except Exception:
                pass


def _threat_plausible(state, me_i: int) -> bool:
    try:
        opp = state.players[1 - me_i]
        me = state.players[me_i]
    except Exception:
        return False
    if len(opp.prize) <= OPP_PRIZE_GATE:
        return True
    # No bench: a knockout of our Active leaves us with no Active Pokemon, which is a loss.
    try:
        return len([b for b in (me.bench or []) if b is not None]) == 0
    except Exception:
        return False


def _determinization(obs, decklist, prized_counter):
    """Identical seating to lethal.lethal_move, so both verifiers reason about the same fork."""
    state = obs.current
    me_i = state.yourIndex
    me = state.players[me_i]
    opp = state.players[1 - me_i]
    prize_n = max(len(me.prize), 1)
    deck_n = max(me.deckCount, 1)
    your_deck = your_prize = None
    if _corrected_deck is not None:
        try:
            ordered = _corrected_deck(obs, list(decklist), prized_counter)
            if ordered and len(ordered) >= prize_n:
                your_prize = ordered[:prize_n]
                your_deck = ordered[prize_n: prize_n + deck_n]
        except Exception:
            your_deck = None
    if not your_deck:
        pool = (list(decklist) * 2) if decklist else [1]
        your_deck = pool[:deck_n]
        your_prize = pool[:prize_n]
    if not your_prize:
        your_prize = (list(decklist) or [1])[:prize_n]
    opponent_active = [1072] if (opp.active and opp.active[0] is None) else []
    return (your_deck, your_prize,
            [1072] * max(opp.deckCount, 1),
            [1072] * max(len(opp.prize), 1),
            [1072] * max(opp.handCount, 0) if opp.handCount else [],
            opponent_active)


def threat_alternative(obs_dict, decklist, prized_counter=None, chosen=None,
                       _stats=None) -> list[int] | None:
    """Return a safer turn-ending selection, or None. Never raises.

    None means "say nothing", which covers every ambiguous case: no search available, not a MAIN
    decision, the opponent cannot close the game next turn, the scorer is not ending the turn, the
    scorer's move is not provably losing, or no alternative is provably safe.
    """
    if not _HAVE_SEARCH or not chosen:
        return None
    try:
        obs = to_observation_class(obs_dict)
        select = obs.select
        state = obs.current
        if select is None or state is None:
            return None
        if getattr(select, "context", None) != SelectContext.MAIN:
            return None
        if getattr(obs, "search_begin_input", None) is None:
            return None
        me_i = state.yourIndex
        if not _threat_plausible(state, me_i):
            return None

        enders = _turn_enders()
        opts = select.option
        chosen_idx = [i for i in chosen if isinstance(i, int) and 0 <= i < len(opts)]
        if len(chosen_idx) != len(chosen) or len(chosen_idx) != 1:
            return None
        if opts[chosen_idx[0]].type not in enders:
            return None       # not the last decision of the turn -> nothing has been committed yet
        alts = [i for i in range(len(opts))
                if i != chosen_idx[0] and opts[i].type in enders]
        if not alts:
            return None
        # Prefer another attack over simply passing: END concedes the whole turn.
        alts.sort(key=lambda i: 0 if opts[i].type == OptionType.ATTACK else 1)
        alts = alts[:_MAX_ALTERNATIVES]
        end_turn = getattr(state, "turn", 0) or 0
        seating = _determinization(obs, decklist, prized_counter)
    except Exception:
        return None

    root = None
    try:
        root = search_begin(obs, *seating)
        root_select = root.observation.select
        if root_select is None or len(root_select.option) != len(opts):
            return None
        budget = _Budget()
        # The opponent's turn is the one after ours; _they_win stops once state.turn passes it.
        end_turn = end_turn + 1
        bad = _loses_after(root.searchId, root_select, list(chosen), me_i, end_turn, budget)
        if _stats is not None:
            _stats["gated"] = _stats.get("gated", 0) + 1
            if bad:
                _stats["chosen_loses"] = _stats.get("chosen_loses", 0) + 1
        if not bad:
            return None
        for i in alts:
            if budget.exhausted():
                break
            sel = _selection_for(root_select, i)
            alt_bad = _loses_after(root.searchId, root_select, sel, me_i, end_turn, budget)
            if alt_bad is False:
                live = _selection_for(select, i)
                if _stats is not None:
                    _stats["saved"] = _stats.get("saved", 0) + 1
                    _stats.setdefault("saved_types", []).append(
                        (int(opts[chosen_idx[0]].type), int(opts[i].type)))
                return live
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

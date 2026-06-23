"""Scorer-guided lookahead search — strong prior + shallow determinized rollout.

`best_options(obs_dict, decklist) -> list[int]`. ONLY for MAIN-context single-select turns with
more than one legal first-action (else it defers to `scorer.best_options`):

  1. Rank the current options with the scorer's own MAIN heuristic.
  2. Take the top-K candidate first-actions.
  3. For each candidate, fork a determinized hypothetical game (engine `search_begin`), apply the
     candidate, then greedily finish OUR turn by repeatedly applying the scorer to the forked
     observation until control passes / the game ends / a step cap.
  4. Evaluate the resulting board with a prize-race-dominated value function, averaged over a few
     determinization samples (shared across candidates — common random numbers — to cut variance).
  5. Play the candidate whose rollout reaches the best board — but only if it beats the scorer's
     own pick by SWITCH_MARGIN, otherwise stay on the scorer (prior protection).

Everything is wrapped: on ANY error, or for non-qualifying decisions, we defer to
`scorer.best_options(obs_dict)`, so the lookahead never returns an illegal/empty selection and
never forfeits. Budget: K candidates x S samples x a short turn-completion rollout — measured ~4 ms,
well under the 1 s/move limit.

HONEST RESULT (reproduce with tools/validate_lookahead.py). On data/decks/crustle.csv, head-to-head
vs the pure scorer over 200 games, this lookahead does NOT beat it — it lands ~38-42% (the
scorer-vs-scorer mirror baseline is ~50%). It is a rigorously-supported NEGATIVE result, not the
>53% we sought. A full sweep was run — naive argmax over the static board (~48%/60g, noisy), a
deeper scorer-vs-scorer rollout to terminal scored by real win/loss (~37-45%), paired
robust-dominance over win/loss (~40%), scorer-near-tie tie-breaking (~32%/200g), and a lethal-rescue
gate (~36%) — and the trend is monotone: the MORE the policy deviates from the scorer, the worse it
does; it only approaches parity as deviations vanish (raising SWITCH_MARGIN toward infinity reduces
to the pure scorer, ~50%). So the agent in main.py should — and does — keep using the pure scorer.

WHY (mechanism): the scorer is an already-strong imperfect-information policy sitting at a sharp
local optimum, and a determinized rollout cannot out-evaluate it. Two failure modes compound:
(a) strategy fusion / phantom lethals — completing the turn with the scorer on a sampled deck order
frequently reaches a KO that exists only because of the fake determinized draws, so an alternative
first-action "wins" the rollout for hidden-information luck reality won't reproduce; and
(b) the static board value (energy/HP/hand) is a far weaker signal than the scorer's own implicit
tempo knowledge, so re-ranking the scorer's near-equal options by it moves *away* from good play
(measured: deviating toward EITHER the max- or the min-eval option loses). Net: on this deck a
shallow scorer-guided lookahead cannot reliably beat the greedy scorer.
"""
from __future__ import annotations

import random

from cg.api import (
    SelectContext, to_observation_class,
    search_begin, search_step, search_end, search_release,
)

import scorer as _scorer
from scorer import _score_main, _score_sub, _fallback  # reuse the strong heuristic

try:
    from belief import corrected_deck
except Exception:  # pragma: no cover - belief is optional
    corrected_deck = None

# ── tunables ──────────────────────────────────────────────────────────────────
K_CANDIDATES = 4      # scorer-top first-actions to look ahead on
N_SAMPLES = 3         # determinization samples per candidate (variance reduction)
ROLLOUT_CAP = 40      # forked steps to finish OUR own turn
# Board-value margin by which a candidate must beat the scorer's #1 pick before we deviate. The
# scorer is a strong prior; deviating on small rollout-eval differences was measured to hurt, so we
# stay on the prior unless search is clearly confident.
SWITCH_MARGIN = 900.0
_OPP_PLACEHOLDER = 1072   # Snorlax — a legal basic for face-down opponent active
_OPP_CARD = 1             # generic placeholder card id for opponent hidden zones

# value weights (prize race dominates)
_W_PRIZE = 1000.0
_W_ENERGY = 12.0
_W_OUR_HP = 1.0
_W_OPP_HP = 1.5
_W_HAND = 5.0
_TERMINAL = 100000.0


def _qualifies(select) -> bool:
    """Only single-select MAIN decisions with a real choice get the lookahead treatment."""
    return (select is not None
            and select.context == SelectContext.MAIN
            and select.maxCount == 1
            and select.minCount <= 1
            and len(select.option) > 1)


# ── scorer wrappers that operate on a forked Observation (not a dict) ─────────
def _score_options(obs):
    """Return (scores, ranked_indices) for obs.select using the scorer's heuristic.

    Mirrors scorer.best_options' scoring loop but takes an already-built Observation so we
    can score the engine's forked SearchState observations without round-tripping to JSON.
    """
    select = obs.select
    n = len(select.option)
    state = obs.current
    me_i = state.yourIndex
    opp_i = 1 - me_i
    me = state.players[me_i]
    opp = state.players[opp_i]
    ctx = select.context
    scores = []
    for o in select.option:
        try:
            if ctx == SelectContext.MAIN:
                scores.append(_score_main(obs, o, me, opp, me_i))
            else:
                scores.append(_score_sub(obs, o, ctx, me, opp, me_i, opp_i))
        except Exception:
            scores.append(0.0)
    ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)
    return scores, ranked


def _scorer_select(obs):
    """The scorer's chosen legal selection for a forked Observation (any context)."""
    select = obs.select
    if select is None or not select.option or select.maxCount <= 0:
        return []
    scores, ranked = _score_options(obs)
    n = len(select.option)
    minc = max(0, min(select.minCount, n))
    maxc = max(minc, min(select.maxCount, n))
    out = []
    for i in ranked:
        if scores[i] > 0 or len(out) < minc:
            out.append(i)
        if len(out) >= maxc:
            break
    for i in range(n):
        if len(out) >= minc:
            break
        if i not in out:
            out.append(i)
    return out[:maxc] if out else _fallback(select)


# ── determinization ───────────────────────────────────────────────────────────
def _a_basic(pool):
    """First basic Pokémon id in a decklist (for a face-down opponent active)."""
    for cid in pool:
        c = _scorer._CARD.get(cid)
        if c is not None and getattr(c, "basic", False) and c.cardType == 0:
            return cid
    return _OPP_PLACEHOLDER


def _determinize(obs, decklist, opp_model, rng):
    """Build (your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active).

    OUR hidden zones come from the belief-corrected hidden pool (visible cards subtracted), shuffled
    per sample. The OPPONENT's hidden zones: when `opp_model` is given they are determinized from it
    (a deck the opponent is assumed to play — exact for a mirror, a strong-generic assumption on the
    open ladder), used when a rollout is rolled *through* the opponent's reply. The shipped shallow
    rollout finishes only OUR turn and never simulates the opponent, so we pass opp_model=None and
    the opponent's hidden zones get legal Snorlax/placeholder fillers — fastest, and the opponent's
    real active/HP are preserved by the engine regardless. (Mirror-opponent terminal rollouts were
    measured to underperform; see the module docstring.)
    """
    st = obs.current
    yi = st.yourIndex
    me = st.players[yi]
    opp = st.players[1 - yi]
    deck_n = max(me.deckCount, 0)
    prize_n = len(me.prize)

    hidden = None
    if corrected_deck is not None:
        try:
            pool = list(corrected_deck(obs, decklist, None))
            if len(pool) >= deck_n + prize_n:
                hidden = pool
        except Exception:
            hidden = None
    if hidden is None:
        hidden = (list(decklist) * 2)[: deck_n + prize_n]

    hidden = list(hidden)
    rng.shuffle(hidden)
    your_prize = hidden[:prize_n]
    your_deck = hidden[prize_n: prize_n + deck_n]
    while len(your_deck) < deck_n:      # pad defensively if the belief pool came up short
        your_deck.append(decklist[0])
    while len(your_prize) < prize_n:
        your_prize.append(decklist[0])

    opp_deck_n = max(opp.deckCount, 0)
    opp_prize_n = len(opp.prize)
    opp_hand_n = max(opp.handCount, 0)
    if opp_model:
        om = list(opp_model)
        # a shuffled supply of the model deck, enough for every hidden opponent zone
        supply = (om * (1 + (opp_deck_n + opp_prize_n + opp_hand_n) // max(1, len(om))))
        rng.shuffle(supply)
        opp_deck = supply[:opp_deck_n]
        opp_prize = supply[opp_deck_n: opp_deck_n + opp_prize_n]
        opp_hand = supply[opp_deck_n + opp_prize_n: opp_deck_n + opp_prize_n + opp_hand_n]
        # guarantee the deck holds at least one basic so the engine accepts the world
        if opp_deck and not any(_scorer._CARD.get(c) and getattr(_scorer._CARD[c], "basic", False)
                                for c in opp_deck):
            opp_deck[0] = _a_basic(om)
        opp_active = [_a_basic(om)] if (opp.active and opp.active[0] is None) else []
    else:
        opp_deck = [_OPP_PLACEHOLDER] * opp_deck_n
        opp_prize = [_OPP_CARD] * opp_prize_n
        opp_hand = [_OPP_CARD] * opp_hand_n
        opp_active = [_OPP_PLACEHOLDER] if (opp.active and opp.active[0] is None) else []
    return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active


# ── rollout + evaluation ──────────────────────────────────────────────────────
def _terminal_value(o, our_index):
    r = o.current.result
    if r == our_index:
        return _TERMINAL
    if r == 1 - our_index:
        return -_TERMINAL
    return 0.0  # draw


def _board_energy(player):
    total = 0
    mons = list(player.active or []) + list(player.bench or [])
    for pk in mons:
        if pk is not None:
            total += len(getattr(pk, "energyCards", None) or [])
    return total


def _active_hp(player):
    a = player.active
    if a and a[0] is not None:
        return a[0].hp or 0
    return 0


def _evaluate(o, our_index):
    """Static value of a board from OUR perspective. Prize race dominates."""
    state = o.current
    if state.result is not None and state.result != -1:
        return _terminal_value(o, our_index)
    me = state.players[our_index]
    opp = state.players[1 - our_index]
    our_prizes = len(me.prize)
    opp_prizes = len(opp.prize)
    value = (opp_prizes - our_prizes) * _W_PRIZE
    value += _board_energy(me) * _W_ENERGY
    value += _active_hp(me) * _W_OUR_HP
    value -= _active_hp(opp) * _W_OPP_HP
    value += me.handCount * _W_HAND
    return value


def _rollout(ss, our_index):
    """Greedily complete OUR turn with the scorer until control passes / terminal / cap, then eval.

    Stops the instant control would pass to the opponent. A deeper scorer-vs-scorer rollout to
    terminal was tried and *hurt* — its determinized opponent draws inject more variance and
    clairvoyance bias than the extra plies add in signal. Evaluating the board at the end of our own
    fully completed turn is the sharpest, lowest-bias estimate the rollout can give.
    """
    cur = ss
    for _ in range(ROLLOUT_CAP):
        o = cur.observation
        if o.current is None or (o.current.result is not None and o.current.result != -1):
            return _evaluate(o, our_index)
        if o.select is None or o.current.yourIndex != our_index:
            return _evaluate(o, our_index)
        sel = _scorer_select(o)
        if not sel:
            return _evaluate(o, our_index)
        cur = search_step(cur.searchId, sel)
    return _evaluate(cur.observation, our_index)


def _rollout_candidate(obs, cand_index, our_index, det):
    """Apply cand_index on a GIVEN determinization, finish our turn, return the board value.

    Reusing a fixed determinization across candidates (common random numbers) makes the
    candidate-vs-candidate comparison paired and low-variance. Returns None on any engine error.
    """
    root = None
    try:
        root = search_begin(obs, *det)
        nxt = search_step(root.searchId, [cand_index])
        return _rollout(nxt, our_index)
    except Exception:
        return None
    finally:
        if root is not None:
            try:
                search_release(root.searchId)
            except Exception:
                pass


# ── entry point ───────────────────────────────────────────────────────────────
def best_options(obs_dict, decklist) -> list[int]:
    """Lookahead-improved selection; defers to the scorer for everything non-qualifying."""
    try:
        obs = to_observation_class(obs_dict)
        select = obs.select
        if not _qualifies(select):
            return _scorer.best_options(obs_dict)

        our_index = obs.current.yourIndex
        scores, ranked = _score_options(obs)
        scorer_pick = ranked[0]          # the pure scorer would play this — our default
        candidates = ranked[:K_CANDIDATES]
        if len(candidates) <= 1:
            return _scorer.best_options(obs_dict)

        # Pre-sample determinizations ONCE; every candidate is rolled out on the SAME worlds
        # (common random numbers) so the comparison is paired and low-variance. The rollout only
        # finishes OUR turn, so the opponent's hidden zones merely need to be legal — placeholder
        # fillers suffice (and are fastest); the opponent's real active/HP are preserved.
        rng = random.Random(0xC0FFEE)
        dets = [_determinize(obs, decklist, None, rng) for _ in range(N_SAMPLES)]

        means = {}  # candidate -> mean completed-turn board value
        try:
            for cand in candidates:
                total, hits = 0.0, 0
                for det in dets:
                    v = _rollout_candidate(obs, cand, our_index, det)
                    if v is not None:
                        total += v
                        hits += 1
                if hits:
                    means[cand] = total / hits
        finally:
            try:
                search_end()
            except Exception:
                pass

        if scorer_pick not in means:
            return _scorer.best_options(obs_dict)  # couldn't evaluate the baseline — defer

        # Pick the candidate whose completed turn reaches the best board. We require a margin over
        # the scorer's own pick before deviating: the scorer is a strong imperfect-information prior,
        # and a 1-ply determinized rollout's static eval is too weak/biased to override it on small
        # differences (measured: unmargined deviation underperforms). The margin keeps us on the
        # prior unless search is clearly confident — which, on this deck, is rare.
        baseline = means[scorer_pick]
        best_idx = max(means, key=lambda i: means[i])
        if best_idx != scorer_pick and means[best_idx] > baseline + SWITCH_MARGIN:
            return [best_idx]
        return [scorer_pick]
    except Exception:
        try:
            return _scorer.best_options(obs_dict)
        except Exception:
            return [0]

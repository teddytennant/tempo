"""tempo floor agent — deck-agnostic, robust option ranker.

Contract (see docs/plans/01-agent-contract.md):
  agent(obs_dict) -> list[int]
  - deck-selection (obs_dict["select"] is None): return the 60-card deck
  - otherwise: return indices into obs.select.option, satisfying min/maxCount
  - never raise (always a legal fallback); never exceed the 10-min game clock

This is the Stage-1 baseline: a generic heuristic that plays reasonably with ANY deck so we
have a non-trivial ladder floor and a proven pipeline. The learned policy (Stage 3) replaces
`Policy.score` with a trained net behind the same interface.
"""
from __future__ import annotations

import os
import sys

from cg.api import (
    AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext,
    all_attack, all_card_data, to_observation_class,
)


# ── deck loading ─────────────────────────────────────────────────────────────
def _resolve_deck_path() -> str:
    cands = []
    if "__file__" in globals():
        cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv"))
    cands += ["deck.csv", "/kaggle_simulations/agent/deck.csv"]
    cands += [os.path.join(p, "deck.csv") for p in sys.path if p]
    for p in cands:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("deck.csv not found")


with open(_resolve_deck_path()) as _f:
    my_deck = [int(x) for x in _f.read().splitlines() if x.strip()]
if len(my_deck) != 60:
    raise ValueError(f"deck.csv must have 60 ids, got {len(my_deck)}")

try:
    from prize_tracker import PrizeTracker
    from belief import corrected_deck
    from opp_detect import detect_opp
except Exception:
    PrizeTracker = None
    corrected_deck = None
    detect_opp = None
_tracker = None

# Card / attack tables (read-only engine views).
_card_table = {c.cardId: c for c in all_card_data()}
_attack_cost = {a.attackId: len(a.energies or []) for a in all_attack()}
_attack_dmg = {a.attackId: int(getattr(a, "damage", 0) or 0) for a in all_attack()}


# ── proven contract-handling scaffolding ─────────────────────────────────────
def normalize_selection(ranked, scores, select):
    """Pick a legal index set honoring min/maxCount: take positively-scored options in rank
    order up to maxCount, always fill to minCount, dedupe and bounds-check."""
    n = len(select.option)
    minc = max(0, min(select.minCount, n))
    maxc = max(minc, min(select.maxCount, n))
    out, seen = [], set()
    for i in ranked:
        if not (0 <= i < n) or i in seen:
            continue
        s = scores[i] if i < len(scores) else 0
        if s > 0 or len(out) < minc:
            out.append(i); seen.add(i)
        if len(out) >= maxc:
            break
    for i in range(n):
        if len(out) >= minc:
            break
        if i not in seen:
            out.append(i); seen.add(i)
    return out


def _legal_fallback(select):
    try:
        n = len(select.option)
        return list(range(min(max(0, select.minCount), n)))
    except Exception:
        return []


def _legal_fallback_from_dict(obs_dict):
    try:
        sel = (obs_dict or {}).get("select") or {}
        return list(range(min(max(0, sel.get("minCount", 0)), len(sel.get("option") or []))))
    except Exception:
        return []


def _safe_get(seq, i):
    try:
        if seq is None or i is None or i < 0 or i >= len(seq):
            return None
        return seq[i]
    except Exception:
        return None


# ── generic heuristic policy ─────────────────────────────────────────────────
class Policy:
    """Deck-agnostic ranking. Priorities: win > damage > develop board > end.
    Uses only generic engine/card-data facts, no hardcoded card IDs."""

    def __init__(self, obs):
        self.obs = obs
        self.state = obs.current
        self.select = obs.select
        self.ctx = self.select.context
        self.me_i = self.state.yourIndex
        self.op_i = 1 - self.me_i
        self.me = self.state.players[self.me_i]
        self.op = self.state.players[self.op_i]

    def _opp_active(self):
        return self.op.active[0] if self.op and self.op.active else None

    def _card_in(self, area, index, pi):
        try:
            player = self.state.players[pi]
            if area == AreaType.HAND:
                return _safe_get(player.hand, index)
            if area == AreaType.ACTIVE:
                return _safe_get(player.active, index)
            if area == AreaType.BENCH:
                return _safe_get(player.bench, index)
            if area == AreaType.DISCARD:
                return _safe_get(player.discard, index)
            if area == AreaType.DECK:
                return _safe_get(getattr(self.select, "deck", None), index)
            if area == AreaType.STADIUM:
                return _safe_get(self.state.stadium, index)
            if area == AreaType.LOOKING:
                return _safe_get(self.state.looking, index)
        except Exception:
            return None
        return None

    def rank(self):
        if not self.select.option or self.select.maxCount == 0:
            return [], []
        scores = [self._score(o) for o in self.select.option]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return ranked, scores

    def choose(self):
        ranked, scores = self.rank()
        return normalize_selection(ranked, scores, self.select)

    def _score(self, o):
        t = o.type
        if self.ctx == SelectContext.IS_FIRST:
            return 100 if t == OptionType.YES else 0
        if t == OptionType.ATTACK:
            return self._score_attack(o)
        if t == OptionType.NUMBER:
            return o.number if o.number is not None else 0
        if t == OptionType.EVOLVE:
            return 700
        if t == OptionType.ABILITY:
            return 650
        if t in (OptionType.ENERGY, OptionType.ATTACH):
            return self._score_attach(o)
        if t == OptionType.PLAY:
            return self._score_play(o)
        if t == OptionType.CARD:
            return self._score_card(o)
        if t == OptionType.RETREAT:
            return 50
        if t == OptionType.YES:
            return 60
        if t == OptionType.NO:
            return 40
        if t == OptionType.END:
            return 10
        return 30

    def _score_attack(self, o):
        opp = self._opp_active()
        dmg = _attack_dmg.get(o.attackId, 0)
        if opp is not None and dmg > 0 and getattr(opp, "hp", 0) <= dmg:
            return 90000  # lethal/KO — take it
        if dmg <= 0:
            return 500    # utility/zero-damage attack: above END, below real damage
        return 1000 + min(dmg, 320)

    def _score_attach(self, o):
        p = self._card_in(getattr(o, "inPlayArea", None), getattr(o, "inPlayIndex", None), self.me_i)
        if not isinstance(p, Pokemon):
            return 100
        # Fuel an attacker that can't yet pay: prefer active, prefer under-fueled bodies.
        need = 1
        c = _card_table.get(p.id)
        if c is not None and c.attacks:
            need = max((_attack_cost.get(a, 1) for a in c.attacks), default=1)
        if len(p.energies or []) >= need:
            return -1  # already payable — hold energy
        return 800 + (200 if getattr(o, "inPlayArea", None) == AreaType.ACTIVE else 0)

    def _score_play(self, o):
        card = self._card_in(AreaType.HAND, o.index, self.me_i)
        if card is None:
            return 100
        d = _card_table.get(card.id)
        if d is None:
            return 100
        if d.cardType == CardType.POKEMON:
            return 600          # develop the board
        if d.cardType == CardType.SUPPORTER:
            return 500 if not self.state.supporterPlayed else -1
        if d.cardType == CardType.ITEM:
            return 400
        if d.cardType == CardType.STADIUM:
            return 300 if not self.state.stadiumPlayed else -1
        if d.cardType == CardType.TOOL:
            return 250
        return 200

    def _score_card(self, o):
        card = self._card_in(o.area, o.index, getattr(o, "playerIndex", self.me_i))
        if card is None:
            return 0
        d = _card_table.get(card.id)
        # When searching/drawing, mildly prefer energy and evolution fuel.
        if d is not None and d.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
            return 120
        if isinstance(card, Pokemon) or (d is not None and d.cardType == CardType.POKEMON):
            return 110
        return 100


# ── floor heuristic entry (fallback / mock-test path) ────────────────────────
def floor_agent(obs_dict):
    try:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return my_deck
    except Exception:
        pass
    try:
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            return my_deck
        try:
            return Policy(obs).choose()
        except Exception:
            return _legal_fallback(obs.select)
    except Exception:
        return _legal_fallback_from_dict(obs_dict if isinstance(obs_dict, dict) else {})


def floor_select(obs):
    """Floor heuristic over an already-parsed Observation — used as an MCTS rollout policy.
    The floor pilots a consistent deck well (87.5% vs random on mega_lucario), so heuristic
    playouts give sharper value estimates than random ones."""
    try:
        if obs.select is None:
            return my_deck
        return Policy(obs).choose()
    except Exception:
        return _legal_fallback(obs.select)


# ── MCTS-backed entry (deploy) ───────────────────────────────────────────────
# Determinized search over the engine's native API, time-budgeted under the 10-min game clock,
# with the floor heuristic as a hard fallback. Import is defensive: under the mock engine (tests)
# the native search symbols are absent, so we degrade to the floor agent and stay contract-legal.
import time as _time  # noqa: E402

_GAME_BUDGET_S = 540.0   # 9 min — margin under the 10-min hard cap
_PER_MOVE_CAP_S = 8.0    # more search validated to win (scaling exp: 66.7%); clock-guard keeps it safe
_time_spent = 0.0
_last_turn = 0

def _load_ids(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()]


# Opponent model: the archetype we assume the field plays (for determinized search). Bundled as
# opp_model.csv; falls back to a mirror of our own deck if absent.
_opp_model = None
try:
    for _p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "opp_model.csv"),
               "opp_model.csv", "/kaggle_simulations/agent/opp_model.csv"]:
        if os.path.exists(_p):
            _opp_model = _load_ids(_p)
            break
except Exception:
    _opp_model = None

# Optional learned policy prior (numpy-only). Used iff a model.npz is bundled — so the safe
# vanilla-MCTS floor ships without it, and a proven net ships by bundling the file.
_pv = None
try:
    _here = os.path.dirname(os.path.abspath(__file__))
    for _p in [os.path.join(_here, "model.npz"), "model.npz", "/kaggle_simulations/agent/model.npz"]:
        if os.path.exists(_p):
            from net.infer_np import NetPVNumpy
            _pv = NetPVNumpy(_p)
            break
except Exception:
    _pv = None

try:
    from search.mcts import MctsAgent  # noqa: E402
    _mcts = MctsAgent(my_deck, iters=100000, rollout_cap=200, fallback=floor_agent,
                      time_budget_s=_PER_MOVE_CAP_S, opp_model=_opp_model, pv=_pv)
except Exception:
    _mcts = None

# Rust search core (~10× sims). Used for MAIN single-select decisions when the abi3 wheel loads;
# falls back to the Python MCTS / floor on any error. Bundled as a wheel + the cg/ engine.
import json as _json  # noqa: E402
_RUST = None
try:
    from cg.api import search_begin as _real_cg_marker  # real engine only (mock lacks it)
    _have_real_cg = True
except Exception:
    _have_real_cg = False
if _have_real_cg:
    try:
        import engine_rs as _er  # noqa: E402
        _h = os.path.dirname(os.path.abspath(__file__))
        for _lp in [os.path.join(_h, "cg", "libcg.so"), "cg/libcg.so", "/kaggle_simulations/agent/cg/libcg.so"]:
            if os.path.exists(_lp):
                _er.init(os.path.abspath(_lp))
                _RUST = _er
                break
        # Net-in-Rust: load the policy/value net so choose() uses PUCT (priors + value-at-leaf).
        if _RUST is not None:
            for _np in [os.path.join(_h, "model.npz"), "model.npz", "/kaggle_simulations/agent/model.npz"]:
                if os.path.exists(_np):
                    try:
                        _RUST.init_net(os.path.abspath(_np))
                    except Exception:
                        pass
                    break
    except Exception:
        _RUST = None


def _main_single(obs_dict):
    try:
        sel = obs_dict.get("select"); cur = obs_dict.get("current")
        if not sel or not cur:
            return False
        return (sel.get("context") == 0 and sel.get("maxCount") == 1
                and (sel.get("minCount") or 0) <= 1 and len(sel.get("option") or []) > 1)
    except Exception:
        return False


def agent(obs_dict):
    global _time_spent, _last_turn, _tracker
    try:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            _time_spent = 0.0   # new game: reset the per-game clock budget
            _last_turn = 0
            _tracker = PrizeTracker(my_deck) if PrizeTracker else None  # fresh prize tracker
            return my_deck
    except Exception:
        pass
    # Reset the clock if a new game started without a fresh import (turn went backwards).
    try:
        cur = obs_dict.get("current") if isinstance(obs_dict, dict) else None
        turn = cur.get("turn") if isinstance(cur, dict) else None
        if turn is not None:
            if turn < _last_turn:
                _time_spent = 0.0
            _last_turn = turn
    except Exception:
        pass
    o_obs = None
    if PrizeTracker is not None:
        if _tracker is None:
            _tracker = PrizeTracker(my_deck)   # lazy init if the deck-phase trigger was missed
        try:
            o_obs = to_observation_class(obs_dict)
            _tracker.update(o_obs, obs_dict)   # track prizes every frame
        except Exception:
            o_obs = None
    if _mcts is None:
        return floor_agent(obs_dict)
    t0 = _time.monotonic()
    remaining = _GAME_BUDGET_S - _time_spent
    try:
        if remaining <= 2.0:
            sel = floor_agent(obs_dict)            # out of clock — cheap heuristic
        elif _RUST is not None and _main_single(obs_dict):
            pm = min(_PER_MOVE_CAP_S, max(0.2, remaining * 0.05))
            cdeck = my_deck
            if corrected_deck is not None and o_obs is not None:
                try:
                    cd = corrected_deck(o_obs, my_deck, _tracker.prized_cards() if _tracker else None)
                    if cd:
                        cdeck = cd  # belief-corrected [prized..., remaining_deck...]
                except Exception:
                    cdeck = my_deck
            opp = _opp_model or my_deck
            if detect_opp is not None and o_obs is not None:
                try:
                    opp = detect_opp(o_obs, opp)   # match opponent's revealed cards to the right deck
                except Exception:
                    pass
            sel = _RUST.choose(_json.dumps(obs_dict), cdeck, opp, pm, 1000000000, 1.4, 0)
            if not (isinstance(sel, list) and len(sel) >= 1):
                sel = floor_agent(obs_dict)
        else:
            _mcts.time_budget_s = min(_PER_MOVE_CAP_S, max(0.1, remaining * 0.05))
            sel = _mcts(obs_dict)
    except Exception:
        sel = floor_agent(obs_dict)
    _time_spent += _time.monotonic() - t0
    return sel

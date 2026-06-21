"""Determinized UCT over the engine's native search API (docs/plans/02-forward-model.md).

Each iteration samples a determinization of hidden info, `search_begin`s that world, descends a
shared statistics tree over OUR main single-select decisions (UCB), expands a leaf, rolls out under
a random default policy to a terminal `result`, and backpropagates win-for-us. Non-searched
selections (opponent moves, chance, sub-selects, multi-selects) are advanced by the default policy.

This is the proof-of-signal MCTS: correct first. Hot-path/Rust and a learned rollout/prior come
later. The agent falls back to the floor heuristic for non-main decisions so every call is fast and
legal.
"""
from __future__ import annotations

import math
import os
import random
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import (  # noqa: E402
    all_attack, all_card_data, to_observation_class,
    search_begin, search_step, search_end,
)

_CARDS = {c.cardId: c for c in all_card_data()}
_ATK_DMG = {a.attackId: int(getattr(a, "damage", 0) or 0) for a in all_attack()}
MAIN_CTX = 0   # SelectContext.MAIN
ATTACK_OPT = 13  # OptionType.ATTACK


def _canon(opt):
    return (int(opt.type),
            None if opt.area is None else int(opt.area), opt.index,
            None if opt.inPlayArea is None else int(opt.inPlayArea), opt.inPlayIndex,
            opt.attackId, opt.playerIndex, opt.number)


def _terminal(o):
    return o.current is not None and o.current.result != -1


def _value_for(o, our_index):
    r = o.current.result
    return 1.0 if r == our_index else 0.5 if r == 2 else 0.0


def _a_basic_pokemon(deck):
    for cid in deck:
        c = _CARDS.get(cid)
        if c is not None and c.cardType == 0 and getattr(c, "basic", False):
            return cid
    return deck[0]


class _Node:
    __slots__ = ("children", "visits", "wins", "n", "P", "expanded")

    def __init__(self):
        self.children = {}   # key -> _Node
        self.visits = {}     # key -> int
        self.wins = {}       # key -> float (Q sum)
        self.n = 0           # times this decision node was traversed
        self.P = {}          # key -> prior probability (PUCT mode)
        self.expanded = False

    def ucb_pick(self, keys, c):
        logn = math.log(self.n + 1)
        best, best_v = None, -1e18
        for k in keys:
            v = self.visits.get(k, 0)
            if v == 0:
                return k  # try unvisited-but-known first
            q = self.wins[k] / v
            u = q + c * math.sqrt(logn / v)
            if u > best_v:
                best_v, best = u, k
        return best

    def expand(self, keys, priors):
        self.expanded = True
        for k, p in zip(keys, priors):
            self.P[k] = p
            self.visits.setdefault(k, 0)
            self.wins.setdefault(k, 0.0)

    def child(self, k):
        return self.children.setdefault(k, _Node())

    def puct_pick(self, keys, c):
        total = sum(self.visits.get(k, 0) for k in keys)
        sq = math.sqrt(total + 1)
        best, best_v = None, -1e18
        for k in keys:
            v = self.visits.get(k, 0)
            q = self.wins[k] / v if v > 0 else 0.0
            u = c * self.P.get(k, 1e-3) * sq / (1 + v)
            if q + u > best_v:
                best_v, best = q + u, k
        return best


class MctsAgent:
    def __init__(self, deck, iters=60, rollout_cap=200, c=1.4, seed=0,
                 fallback=None, search_contexts=(MAIN_CTX,), time_budget_s=None,
                 opp_model=None, rollout_policy=None, pv=None):
        self.deck = list(deck)
        self.pv = pv            # policy_value(obs)->(priors,value); enables AlphaZero-style PUCT
        self.last_policy = None  # visit-count distribution over the last root's options (self-play target)
        # Opponent model for determinization: the deck we ASSUME the opponent plays. On the
        # ladder the field is dominated by one archetype, so modelling that (not a mirror of our
        # own deck) makes the search realistic. Defaults to our deck (mirror) if unspecified.
        self.opp_pool = list(opp_model) if opp_model else list(deck)
        self.iters = iters
        self.rollout_cap = rollout_cap
        self.c = c
        self.rng = random.Random(seed)
        self.fallback = fallback        # callable(obs_dict)->selection for non-searched decisions
        self.search_contexts = set(search_contexts)
        self.time_budget_s = time_budget_s  # wall-clock cap per move; None = use fixed iters
        self.rollout_policy = rollout_policy  # callable(Observation)->selection; None = lethal+random

    # ---- determinization ----
    def _determinize(self, obs):
        st = obs.current
        yi = st.yourIndex
        me = st.players[yi]
        opp = st.players[1 - yi]
        mine = self.deck * 2
        theirs = self.opp_pool * 2
        your_deck = mine[: max(me.deckCount, 0)]
        your_prize = mine[: len(me.prize)]
        opp_deck = theirs[: max(opp.deckCount, 0)]
        opp_prize = theirs[: len(opp.prize)]
        opp_hand = theirs[: max(opp.handCount, 0)]
        opp_active = []
        if opp.active and opp.active[0] is None:
            opp_active = [_a_basic_pokemon(self.opp_pool)]
        return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active

    # ---- policies ----
    def _default_sel(self, o):
        n = len(o.select.option)
        k = o.select.maxCount
        if k <= 0 or n == 0:
            return []
        return self.rng.sample(range(n), min(k, n))

    def _rollout_sel(self, o):
        """Rollout policy: take a lethal KO attack if one is available, else random.
        Stronger-than-random playouts give sharper value estimates without the floor
        heuristic's pathologies (the floor itself loses to random)."""
        sel = o.select
        n = len(sel.option)
        if n == 0 or sel.maxCount <= 0:
            return []
        st = o.current
        if st is not None and sel.maxCount == 1:
            opp = st.players[1 - st.yourIndex].active
            opp_hp = opp[0].hp if (opp and opp[0] is not None) else 0
            if opp_hp > 0:
                for i, opt in enumerate(sel.option):
                    if int(opt.type) == ATTACK_OPT and opt.attackId is not None:
                        if _ATK_DMG.get(opt.attackId, 0) >= opp_hp:
                            return [i]
        return self.rng.sample(range(n), min(sel.maxCount, n))

    def _rollout(self, ss, our_index):
        cur = ss
        for _ in range(self.rollout_cap):
            o = cur.observation
            if _terminal(o):
                return _value_for(o, our_index)
            if o.select is None:
                return 0.5
            if self.rollout_policy is not None:
                try:
                    sel = self.rollout_policy(o)
                except Exception:
                    sel = self._rollout_sel(o)
            else:
                sel = self._rollout_sel(o)
            cur = search_step(cur.searchId, sel)
        # undecided after cap: neutral
        return 0.5

    def _searchable(self, o, our_index):
        sel = o.select
        return (o.current is not None and o.current.yourIndex == our_index
                and int(sel.context) in self.search_contexts
                and sel.maxCount == 1 and sel.minCount <= 1 and len(sel.option) > 1)

    # ---- AlphaZero-style determinized iteration (net priors + value, no rollout) ----
    def _iterate_puct(self, obs, our_index, root):
        ss = search_begin(obs, *self._determinize(obs))
        node = root
        path = []
        value = 0.0
        while True:
            o = ss.observation
            if _terminal(o):
                value = _value_for(o, our_index)   # [0,1]
                break
            if not self._searchable(o, our_index):
                ss = search_step(ss.searchId, self._default_sel(o))
                continue
            keys = [_canon(opt) for opt in o.select.option]
            if not node.expanded:
                # Net POLICY as the PUCT prior (strong); leaf value from a reliable rollout
                # (the weak value head misleads search until it's trained on far more data).
                priors, _ = self.pv(o)
                if not priors or len(priors) != len(keys):
                    priors = [1.0 / len(keys)] * len(keys)
                node.expand(keys, priors)
                value = self._rollout(ss, our_index)   # [0,1], lethal-aware
                break
            k = node.puct_pick(keys, self.c)
            i = keys.index(k)
            path.append((node, k))
            node = node.child(k)
            ss = search_step(ss.searchId, [i])
        for nd, k in path:
            nd.n += 1
            nd.visits[k] = nd.visits.get(k, 0) + 1
            nd.wins[k] = nd.wins.get(k, 0.0) + value
        return value

    # ---- one determinized iteration ----
    def _iterate(self, obs, our_index, root_stats):
        ss = search_begin(obs, *self._determinize(obs))
        node = root_stats
        path = []
        value = 0.5
        while True:
            o = ss.observation
            if _terminal(o):
                value = _value_for(o, our_index)
                break
            if not self._searchable(o, our_index):
                ss = search_step(ss.searchId, self._default_sel(o))
                continue
            opts = o.select.option
            keys = [_canon(opt) for opt in opts]
            untried = [i for i, k in enumerate(keys) if k not in node.children]
            if untried:
                i = self.rng.choice(untried)
                k = keys[i]
                node.children[k] = _Node()
                node.visits.setdefault(k, 0)
                node.wins.setdefault(k, 0.0)
                path.append((node, k))
                ss = search_step(ss.searchId, [i])
                value = self._rollout(ss, our_index)
                break
            # fully expanded -> UCB descend
            k = node.ucb_pick(keys, self.c)
            i = keys.index(k)
            path.append((node, k))
            node = node.children[k]
            ss = search_step(ss.searchId, [i])
        for nd, k in path:
            nd.n += 1
            nd.visits[k] = nd.visits.get(k, 0) + 1
            nd.wins[k] = nd.wins.get(k, 0.0) + value
        return value

    # ---- entry ----
    def __call__(self, obs_dict):
        self.last_policy = None
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            return self.deck
        if not self._searchable(obs, obs.current.yourIndex):
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)

        our_index = obs.current.yourIndex
        root = _Node()
        iterate = self._iterate_puct if self.pv is not None else self._iterate
        try:
            if self.time_budget_s is not None:
                deadline = time.monotonic() + self.time_budget_s
                done = 0
                while done < self.iters and time.monotonic() < deadline:
                    iterate(obs, our_index, root)
                    done += 1
            else:
                for _ in range(self.iters):
                    iterate(obs, our_index, root)
            search_end()
        except Exception:
            search_end()
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)

        # Best root move by visit count; map back to the real option order via canon key.
        real_keys = [_canon(opt) for opt in obs.select.option]
        if not root.visits:
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)
        tot = sum(root.visits.get(k, 0) for k in real_keys)
        if tot > 0:
            self.last_policy = [root.visits.get(k, 0) / tot for k in real_keys]
        best_key = max(root.visits, key=lambda kk: root.visits[kk])
        if best_key in real_keys:
            return [real_keys.index(best_key)]
        return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)

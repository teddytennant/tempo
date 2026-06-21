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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import (  # noqa: E402
    all_card_data, to_observation_class,
    search_begin, search_step, search_end,
)

_CARDS = {c.cardId: c for c in all_card_data()}
MAIN_CTX = 0  # SelectContext.MAIN


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
    __slots__ = ("children", "visits", "wins", "n")

    def __init__(self):
        self.children = {}   # key -> _Node
        self.visits = {}     # key -> int
        self.wins = {}       # key -> float
        self.n = 0           # times this decision node was traversed

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


class MctsAgent:
    def __init__(self, deck, iters=60, rollout_cap=200, c=1.4, seed=0,
                 fallback=None, search_contexts=(MAIN_CTX,)):
        self.deck = list(deck)
        self.iters = iters
        self.rollout_cap = rollout_cap
        self.c = c
        self.rng = random.Random(seed)
        self.fallback = fallback        # callable(obs_dict)->selection for non-searched decisions
        self.search_contexts = set(search_contexts)

    # ---- determinization ----
    def _determinize(self, obs):
        st = obs.current
        yi = st.yourIndex
        me = st.players[yi]
        opp = st.players[1 - yi]
        pool = self.deck * 2
        your_deck = pool[: max(me.deckCount, 0)]
        your_prize = pool[: len(me.prize)]
        opp_deck = pool[: max(opp.deckCount, 0)]
        opp_prize = pool[: len(opp.prize)]
        opp_hand = pool[: max(opp.handCount, 0)]
        opp_active = []
        if opp.active and opp.active[0] is None:
            opp_active = [_a_basic_pokemon(self.deck)]
        return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active

    # ---- policies ----
    def _default_sel(self, o):
        n = len(o.select.option)
        k = o.select.maxCount
        if k <= 0 or n == 0:
            return []
        return self.rng.sample(range(n), min(k, n))

    def _rollout(self, ss, our_index):
        cur = ss
        for _ in range(self.rollout_cap):
            o = cur.observation
            if _terminal(o):
                return _value_for(o, our_index)
            if o.select is None:
                return 0.5
            cur = search_step(cur.searchId, self._default_sel(o))
        # undecided after cap: neutral
        return 0.5

    def _searchable(self, o, our_index):
        sel = o.select
        return (o.current is not None and o.current.yourIndex == our_index
                and int(sel.context) in self.search_contexts
                and sel.maxCount == 1 and sel.minCount <= 1 and len(sel.option) > 1)

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
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            return self.deck
        if not self._searchable(obs, obs.current.yourIndex):
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)

        our_index = obs.current.yourIndex
        root = _Node()
        try:
            for _ in range(self.iters):
                self._iterate(obs, our_index, root)
            search_end()
        except Exception:
            search_end()
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)

        # Best root move by visit count; map back to the real option order via canon key.
        real_keys = [_canon(opt) for opt in obs.select.option]
        if not root.visits:
            return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)
        best_key = max(root.visits, key=lambda kk: root.visits[kk])
        if best_key in real_keys:
            return [real_keys.index(best_key)]
        return self.fallback(obs_dict) if self.fallback else self._default_sel(obs)
